"""BiSubscription 服务与 API 测试。

覆盖：
- ``validate_cron_expr`` —— 合法/非法/空表达式
- ``execute_subscription`` —— 成功刷新写 success 消息 / 仪表盘不存在写 failed 消息
- ``dispatch_subscriptions`` —— 无到期订阅 / 到期订阅被执行
- API 鉴权：未登录访问 subscription / notify 端点返回 2100
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.business.bi.models import BiDashboard, BiNotifyRecord, BiSubscription
from app.business.bi.services_subscription import (
    dispatch_subscriptions,
    execute_subscription,
    validate_cron_expr,
)
from app.core.code import Code
from app.core.exceptions import BizError
from app.utils import StatusType

pytestmark = pytest.mark.asyncio(loop_scope="session")

PREFIX = "/api/v1/business/bi"


# ===================== validate_cron_expr =====================


class TestValidateCronExpr:
    async def test_valid_cron_returns_next_run(self):
        """合法 cron 返回下次触发时间。"""
        now = datetime(2026, 8, 4, 9, 0, tzinfo=timezone.utc)
        next_run = validate_cron_expr("0 9 * * *", now)
        assert next_run > now

    async def test_invalid_cron_raises(self):
        """非法 cron 抛 BizError(4132)。"""
        with pytest.raises(BizError) as exc_info:
            validate_cron_expr("invalid")
        assert str(exc_info.value.code) == Code.BI_SUBSCRIPTION_CRON_INVALID

    async def test_empty_cron_raises(self):
        """空 cron 抛 BizError。"""
        with pytest.raises(BizError):
            validate_cron_expr("")
        with pytest.raises(BizError):
            validate_cron_expr("   ")

    async def test_cron_with_too_many_fields_raises(self):
        """6 字段 cron 抛错（croniter 默认 5 字段）。"""
        with pytest.raises(BizError):
            validate_cron_expr("0 9 * * * foo")


# ===================== execute_subscription =====================


async def _make_subscription(
    bi_datasource,
    dashboard_id: int | None = None,
    name: str = "test-sub",
) -> BiSubscription:
    """工具：创建一个 BiSubscription。"""
    user_id = bi_datasource.tenant_id
    now = datetime.now(timezone.utc)
    return await BiSubscription.create(
        name=name,
        dashboard_id=dashboard_id if dashboard_id is not None else 99999,
        user_id=user_id,
        cron_expr="0 9 * * *",
        next_run_at=now,
        tenant_id=user_id,
        status_type=StatusType.enable,
        created_by=str(user_id),
        updated_by=str(user_id),
    )


class TestExecuteSubscription:
    async def test_success_writes_notify_record(self, app, bi_datasource):
        """成功刷新写 success 消息。"""
        # 先创建一个 BiDashboard
        dashboard = await BiDashboard.create(
            name="订阅测试仪表盘",
            tenant_id=bi_datasource.tenant_id,
            layout={"items": []},
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )
        sub = await _make_subscription(bi_datasource, dashboard_id=dashboard.id)
        now = datetime.now(timezone.utc)

        # mock refresh_dashboard 返回成功结果
        async def fake_refresh(dashboard_id, tenant_id):
            return {
                "items": [
                    {"chartId": "1", "status": "success"},
                    {"chartId": "2", "status": "failed", "errorMessage": "timeout"},
                ],
                "totalElapsedMs": 1500,
            }

        with patch(
            "app.business.bi.services_subscription.refresh_dashboard",
            side_effect=fake_refresh,
        ):
            await execute_subscription(sub)

        # 验证消息记录
        records = await BiNotifyRecord.filter(subscription_id=sub.id).all()
        assert len(records) == 1
        assert records[0].status == "success"
        assert records[0].is_read is False
        assert "订阅测试仪表盘" in records[0].title or sub.name in records[0].title

        # 验证订阅状态更新
        refreshed = await BiSubscription.get(id=sub.id)
        assert refreshed.last_status == "success"
        assert refreshed.last_run_at is not None
        # 测试 DB use_tz=False，从 DB 读出的 datetime 是 naive 的
        # next_run_at 应晚于 now（去掉 tzinfo 后比较）
        assert refreshed.next_run_at.replace(tzinfo=None) > now.replace(tzinfo=None)

    async def test_dashboard_not_found_writes_failed(self, app, bi_datasource):
        """仪表盘不存在写 failed 消息。"""
        sub = await _make_subscription(bi_datasource, dashboard_id=99999)
        await execute_subscription(sub)

        records = await BiNotifyRecord.filter(subscription_id=sub.id).all()
        assert len(records) == 1
        assert records[0].status == "failed"

        refreshed = await BiSubscription.get(id=sub.id)
        assert refreshed.last_status == "failed"
        assert refreshed.last_run_at is not None

    async def test_refresh_exception_writes_failed(self, app, bi_datasource):
        """refresh_dashboard 抛异常时写 failed 消息。"""
        dashboard = await BiDashboard.create(
            name="异常测试仪表盘",
            tenant_id=bi_datasource.tenant_id,
            layout={"items": []},
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )
        sub = await _make_subscription(bi_datasource, dashboard_id=dashboard.id)

        async def failing_refresh(dashboard_id, tenant_id):
            raise Exception("数据源连接失败")

        with patch(
            "app.business.bi.services_subscription.refresh_dashboard",
            side_effect=failing_refresh,
        ):
            await execute_subscription(sub)

        records = await BiNotifyRecord.filter(subscription_id=sub.id).all()
        assert len(records) == 1
        assert records[0].status == "failed"

        refreshed = await BiSubscription.get(id=sub.id)
        assert refreshed.last_status == "failed"


# ===================== dispatch_subscriptions =====================


class TestDispatchSubscriptions:
    async def test_no_due_subs_returns_early(self, app, bi_datasource):
        """无到期订阅时直接返回，不抛异常。"""
        # 清理可能残留的订阅
        await BiSubscription.all().delete()
        await dispatch_subscriptions()

    async def test_executes_due_subs(self, app, bi_datasource):
        """到期订阅被执行。"""
        await BiSubscription.all().delete()
        await BiNotifyRecord.all().delete()

        dashboard = await BiDashboard.create(
            name="dispatch 测试仪表盘",
            tenant_id=bi_datasource.tenant_id,
            layout={"items": []},
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )
        # next_run_at 设为过去时间，确保到期
        past = datetime(2020, 1, 1, tzinfo=timezone.utc)
        await BiSubscription.create(
            name="due-sub",
            dashboard_id=dashboard.id,
            user_id=bi_datasource.tenant_id,
            cron_expr="0 9 * * *",
            next_run_at=past,
            tenant_id=bi_datasource.tenant_id,
            status_type=StatusType.enable,
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )

        async def fake_refresh(dashboard_id, tenant_id):
            return {"items": [], "totalElapsedMs": 0}

        with patch(
            "app.business.bi.services_subscription.refresh_dashboard",
            side_effect=fake_refresh,
        ):
            await dispatch_subscriptions()

        count = await BiNotifyRecord.all().count()
        assert count == 1

    async def test_skips_disabled_subs(self, app, bi_datasource):
        """status_type=disable 的订阅不被执行。"""
        await BiSubscription.all().delete()
        await BiNotifyRecord.all().delete()

        dashboard = await BiDashboard.create(
            name="disabled 测试仪表盘",
            tenant_id=bi_datasource.tenant_id,
            layout={"items": []},
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )
        past = datetime(2020, 1, 1, tzinfo=timezone.utc)
        await BiSubscription.create(
            name="disabled-sub",
            dashboard_id=dashboard.id,
            user_id=bi_datasource.tenant_id,
            cron_expr="0 9 * * *",
            next_run_at=past,
            tenant_id=bi_datasource.tenant_id,
            status_type=StatusType.disable,
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )

        await dispatch_subscriptions()

        count = await BiNotifyRecord.all().count()
        assert count == 0


# ===================== API 鉴权 =====================


from httpx import AsyncClient  # noqa: E402


class TestSubscriptionAPIAuth:
    async def test_search_requires_auth(self, app, client: AsyncClient):
        """未登录访问 /subscriptions/search 返回 2100。"""
        resp = await client.post(
            f"{PREFIX}/subscriptions/search", json={"current": 1, "size": 10}
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == Code.INVALID_TOKEN

    async def test_create_requires_auth(self, app, client: AsyncClient):
        resp = await client.post(
            f"{PREFIX}/subscriptions",
            json={"name": "s1", "dashboardId": "abc", "cronExpr": "0 9 * * *"},
        )
        assert resp.json()["code"] == Code.INVALID_TOKEN


class TestNotifyAPIAuth:
    async def test_search_requires_auth(self, app, client: AsyncClient):
        resp = await client.post(
            f"{PREFIX}/notify/search", json={"current": 1, "size": 10}
        )
        assert resp.json()["code"] == Code.INVALID_TOKEN

    async def test_unread_count_requires_auth(self, app, client: AsyncClient):
        resp = await client.get(f"{PREFIX}/notify/unread-count")
        assert resp.json()["code"] == Code.INVALID_TOKEN
