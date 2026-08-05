"""BiSubscription 调度与执行服务。

职责：
- ``validate_cron_expr`` —— 校验 cron 表达式，返回下次触发时间（UTC）
- ``execute_subscription`` —— 执行单个订阅：刷新仪表盘 + 写消息记录
- ``dispatch_subscriptions`` —— PeriodicTask handler，扫描到期订阅并串行执行

设计要点：
- 复用 ``refresh_dashboard`` 内部的 Semaphore 限并发，不额外引入并发控制
- ``execute_subscription`` 内部 try/except 兜底，失败写 failed 消息，不抛出
- ``next_run_at`` 在执行结束时由 croniter 重新计算
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from croniter import croniter

from app.business.bi.config import BIZ_SETTINGS
from app.business.bi.models import BiDashboard, BiNotifyRecord, BiSubscription
from app.business.bi.services_dashboard import refresh_dashboard
from app.core.exceptions import BizError
from app.core.log import log
from app.utils import Code, StatusType, decode_id


def validate_cron_expr(expr: str, now: datetime | None = None) -> datetime:
    """校验 cron 表达式，返回下次触发时间（UTC）。

    Args:
        expr: cron 表达式（5 字段：分 时 日 月 周）
        now: 基准时间，默认当前 UTC

    Raises:
        BizError(4132): cron 表达式非法
    """
    if not expr or not expr.strip():
        raise BizError(Code.BI_SUBSCRIPTION_CRON_INVALID, "cron 表达式不能为空")
    now = now or datetime.now(timezone.utc)
    try:
        cron = croniter(expr, now)
        return cron.get_next(datetime)
    except (ValueError, KeyError) as e:
        raise BizError(Code.BI_SUBSCRIPTION_CRON_INVALID, f"cron 表达式非法: {e}") from e


async def execute_subscription(sub: BiSubscription) -> None:
    """执行单个订阅：刷新仪表盘 + 写消息记录。

    单订阅超时 ``BI_SUBSCRIPTION_EXECUTE_TIMEOUT`` 秒，失败不抛出（写 failed 消息）。
    """
    now = datetime.now(timezone.utc)
    try:
        # 检查仪表盘是否存在（未软删）
        dashboard = await BiDashboard.filter(id=sub.dashboard_id, deleted_at__isnull=True).first()
        if not dashboard:
            raise BizError(Code.BI_SUBSCRIPTION_DASHBOARD_NOT_FOUND, f"仪表盘 {sub.dashboard_id} 不存在")

        # 同步刷新仪表盘（复用 refresh_dashboard 的 Semaphore 限并发）
        result = await asyncio.wait_for(
            refresh_dashboard(sub.dashboard_id, sub.tenant_id),
            timeout=BIZ_SETTINGS.BI_SUBSCRIPTION_EXECUTE_TIMEOUT,
        )

        # 构造成功消息
        items = result.get("items", [])
        success_count = sum(1 for i in items if i.get("status") == "success")
        failed_count = sum(1 for i in items if i.get("status") == "failed")
        total_elapsed = result.get("totalElapsedMs", 0)

        content = json.dumps(
            {
                "dashboardId": str(sub.dashboard_id),
                "dashboardName": dashboard.name,
                "successCount": success_count,
                "failedCount": failed_count,
                "totalElapsedMs": total_elapsed,
                "refreshedAt": now.isoformat(),
            },
            ensure_ascii=False,
        )

        await BiNotifyRecord.create(
            subscription_id=sub.id,
            user_id=sub.user_id,
            tenant_id=sub.tenant_id,
            title=f"订阅「{sub.name}」刷新成功",
            content=content,
            status="success",
            is_read=False,
            created_by=str(sub.user_id),
            updated_by=str(sub.user_id),
        )

        sub.last_run_at = now
        sub.last_status = "success"

    except Exception as e:
        # 失败写消息
        error_msg = str(e)[:500]
        content = json.dumps(
            {
                "dashboardId": str(sub.dashboard_id),
                "error": error_msg,
                "refreshedAt": now.isoformat(),
            },
            ensure_ascii=False,
        )

        await BiNotifyRecord.create(
            subscription_id=sub.id,
            user_id=sub.user_id,
            tenant_id=sub.tenant_id,
            title=f"订阅「{sub.name}」刷新失败",
            content=content,
            status="failed",
            is_read=False,
            created_by=str(sub.user_id),
            updated_by=str(sub.user_id),
        )

        sub.last_run_at = now
        sub.last_status = "failed"
        log.warning("bi.subscription.execute_failed id={} error={}", sub.id, error_msg)

    finally:
        # 更新下次触发时间
        sub.next_run_at = croniter(sub.cron_expr, now).get_next(datetime)
        await sub.save(update_fields=["last_run_at", "last_status", "next_run_at"])


async def dispatch_subscriptions() -> None:
    """PeriodicTask handler：扫描到期订阅并执行。

    每 60s leader_only 触发，查所有 ``status_type=enable AND next_run_at <= now`` 的订阅。
    串行执行（``refresh_dashboard`` 内部已有 Semaphore 限并发）。
    """
    now = datetime.now(timezone.utc)
    due_subs = await BiSubscription.filter(
        status_type=StatusType.enable,
        next_run_at__lte=now,
        deleted_at__isnull=True,
    ).all()

    if not due_subs:
        return

    log.info("bi.subscription.dispatch count={}", len(due_subs))

    for sub in due_subs:
        try:
            await execute_subscription(sub)
        except Exception as e:
            # execute_subscription 内部已 try/except，这里兜底防止 PeriodicTask 崩溃
            log.error("bi.subscription.dispatch.unexpected id={} error={}", sub.id, str(e))


def decode_dashboard_id(dashboard_id: str | int) -> int:
    """解码前端传入的 dashboardId（sqid 字符串）为 int。

    与 ``decode_id`` 一致，但单独暴露便于 API 层调用。
    """
    if isinstance(dashboard_id, int):
        return dashboard_id
    return decode_id(dashboard_id)
