# BI 仪表盘定时订阅推送 实现计划 — Batch D-2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户订阅 BiDashboard，按 cron 表达式定时刷新并推送站内消息。

**Architecture:** BiSubscription + BiNotifyRecord 两张新表（迁移 0006）。PeriodicTask `bi.subscription.dispatch` 每 60s leader_only 扫描到期订阅，同步调 refresh_dashboard，结果写 BiNotifyRecord。前端订阅管理页 + 消息记录页 + 顶部铃铛组件。

**Tech Stack:** FastAPI + Tortoise ORM + croniter（后端）；Vue 3 + Naive UI（前端）

**Spec:** [.trae/specs/bi-subscription/spec.md](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/.trae/specs/bi-subscription/spec.md)

---

## Task 1: 依赖与错误码

**Files:**
- Modify: `pyproject.toml`
- Modify: `app/core/code.py`
- Modify: `app/business/bi/config.py`

- [ ] **Step 1: 在 `pyproject.toml` 追加 croniter 依赖**

> 先 Read `pyproject.toml` 找到 dependencies 列表，追加 `croniter>=2.0.0`。

- [ ] **Step 2: 在 `app/core/code.py` 的 BI 错误码段追加**

```python
    BI_SUBSCRIPTION_NOT_FOUND = "4130"  # 订阅不存在
    BI_NOTIFY_RECORD_NOT_FOUND = "4131"  # 消息记录不存在
    BI_SUBSCRIPTION_CRON_INVALID = "4132"  # cron 表达式非法
    BI_SUBSCRIPTION_DASHBOARD_NOT_FOUND = "4133"  # 订阅的仪表盘不存在
```

- [ ] **Step 3: 在 `app/business/bi/config.py` 追加订阅配置**

```python
    # ==================== Subscription ====================
    BI_SUBSCRIPTION_DISPATCH_INTERVAL: int = 60  # 调度扫描间隔（秒）
    BI_SUBSCRIPTION_EXECUTE_TIMEOUT: int = 30  # 单订阅执行超时（秒）
    BI_NOTIFY_RECORD_TTL_DAYS: int = 30  # 消息记录保留天数
```

- [ ] **Step 4: 安装依赖**

Run: `cd /Users/Summer/Documents/works/codes/python/agentic-bi-admin && uv sync`

- [ ] **Step 5: 提交**

```bash
git add pyproject.toml uv.lock app/core/code.py app/business/bi/config.py
git commit -m "feat(bi): add croniter dep + subscription error codes + config"
```

---

## Task 2: 模型 + 迁移

**Files:**
- Modify: `app/business/bi/models.py`
- Create: `migrations/app_system/0006_add_bi_subscription.py`

- [ ] **Step 1: 在 `app/business/bi/models.py` 末尾追加两个模型**

> 先 Read models.py 末尾，找到最后一个模型类的位置。

```python
class BiSubscription(BaseModel, AuditMixin, SoftDeleteMixin):
    """仪表盘定时订阅。"""

    id = fields.IntField(primary_key=True, description="主键ID")
    name = fields.CharField(max_length=100, description="订阅名称")
    dashboard_id = fields.BigIntField(description="仪表盘ID")
    user_id = fields.BigIntField(description="订阅者用户ID")
    cron_expr = fields.CharField(max_length=100, description="cron表达式（5字段：分 时 日 月 周）")
    next_run_at = fields.DatetimeField(description="下次触发时间（UTC）")
    last_run_at = fields.DatetimeField(null=True, description="上次触发时间")
    last_status = fields.CharField(max_length=20, null=True, description="上次执行状态 success/failed")
    status_type = fields.CharEnumField(enum_type=StatusType, default=StatusType.enable, description="状态")
    tenant_id = fields.BigIntField(description="租户ID（存user.id，行级隔离）")

    class Meta:
        table = "biz_bi_subscription"
        description = "BI仪表盘定时订阅"


class BiNotifyRecord(BaseModel, AuditMixin, SoftDeleteMixin):
    """订阅推送消息记录。"""

    id = fields.IntField(primary_key=True, description="主键ID")
    subscription_id = fields.BigIntField(description="订阅ID")
    user_id = fields.BigIntField(description="接收者用户ID")
    title = fields.CharField(max_length=200, description="消息标题")
    content = fields.CharField(max_length=2000, null=True, description="消息内容（JSON）")
    status = fields.CharField(max_length=20, description="状态 success/failed")
    is_read = fields.BooleanField(default=False, description="是否已读")
    tenant_id = fields.BigIntField(description="租户ID（存user.id，行级隔离）")

    class Meta:
        table = "biz_bi_notify_record"
        description = "BI订阅推送消息记录"
```

- [ ] **Step 2: 生成迁移**

Run: `cd /Users/Summer/Documents/works/codes/python/agentic-bi-admin && uv run aerich migrate --app app_system -n add_bi_subscription`

> 如果自动生成有误（如 BiMaskingRule/BiQuotaConfig 误检测），手写迁移文件。

- [ ] **Step 3: 应用迁移**

Run: `cd /Users/Summer/Documents/works/codes/python/agentic-bi-admin && uv run aerich upgrade --app app_system`

- [ ] **Step 4: 提交**

```bash
git add app/business/bi/models.py migrations/app_system/0006_add_bi_subscription.py
git commit -m "feat(bi): add BiSubscription + BiNotifyRecord models with migration 0006"
```

---

## Task 3: Schemas + Controllers

**Files:**
- Modify: `app/business/bi/schemas.py`
- Modify: `app/business/bi/controllers.py`

- [ ] **Step 1: 在 `app/business/bi/schemas.py` 追加 schemas**

```python
class BiSubscriptionBase(SchemaBase):
    name: str | None = Field(None, title="订阅名称")
    dashboard_id: int | None = Field(None, title="仪表盘ID")
    cron_expr: str | None = Field(None, title="cron表达式")
    status_type: StatusType | None = Field(None, title="状态")


class BiSubscriptionCreate(BiSubscriptionBase):
    name: str = Field(title="订阅名称")
    dashboard_id: int = Field(title="仪表盘ID")
    cron_expr: str = Field(title="cron表达式")


BiSubscriptionUpdate = make_optional(BiSubscriptionCreate, "BiSubscriptionUpdate")


class BiSubscriptionSearch(BiSubscriptionBase, PageQueryBase):
    pass


class BiSubscriptionOut(SchemaBase):
    id: str | None = Field(None, title="订阅ID（sqid）")
    name: str | None = Field(None, title="订阅名称")
    dashboard_id: str | None = Field(None, title="仪表盘ID（sqid）")
    cron_expr: str | None = Field(None, title="cron表达式")
    next_run_at: str | None = Field(None, title="下次触发时间")
    last_run_at: str | None = Field(None, title="上次触发时间")
    last_status: str | None = Field(None, title="上次执行状态")
    status_type: StatusType | None = Field(None, title="状态")
    created_at: str | None = Field(None, title="创建时间")
    updated_at: str | None = Field(None, title="更新时间")


class BiNotifyRecordBase(SchemaBase):
    title: str | None = Field(None, title="消息标题")
    status: str | None = Field(None, title="状态")
    is_read: bool | None = Field(None, title="是否已读")


class BiNotifyRecordSearch(BiNotifyRecordBase, PageQueryBase):
    pass


class BiNotifyRecordOut(SchemaBase):
    id: str | None = Field(None, title="消息ID（sqid）")
    subscription_id: str | None = Field(None, title="订阅ID（sqid）")
    title: str | None = Field(None, title="消息标题")
    content: str | None = Field(None, title="消息内容")
    status: str | None = Field(None, title="状态")
    is_read: bool | None = Field(None, title="是否已读")
    created_at: str | None = Field(None, title="创建时间")
```

- [ ] **Step 2: 在 `app/business/bi/controllers.py` 追加 controllers**

```python
bi_subscription_controller = CRUDBase(model=BiSubscription)
bi_notify_record_controller = CRUDBase(model=BiNotifyRecord)

# 兼容别名
BiSubscriptionController = bi_subscription_controller
BiNotifyRecordController = bi_notify_record_controller
```

- [ ] **Step 3: 提交**

```bash
git add app/business/bi/schemas.py app/business/bi/controllers.py
git commit -m "feat(bi): add BiSubscription/BiNotifyRecord schemas and controllers"
```

---

## Task 4: services_subscription.py — cron 校验 + 调度 + 执行

**Files:**
- Create: `app/business/bi/services_subscription.py`
- Test: `tests/test_bi_subscription.py`

- [ ] **Step 1: 写 cron 校验测试**

创建 `tests/test_bi_subscription.py`：

```python
"""BiSubscription 服务测试。"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.business.bi.models import BiSubscription
from app.business.bi.services_subscription import (
    execute_subscription,
    validate_cron_expr,
)
from app.utils import StatusType

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(autouse=True)
async def _cleanup(app):
    """每个测试前后清理。"""
    from app.business.bi.async_query import state

    state.set_runtime_redis(app.state.redis)
    await BiSubscription.all().delete()
    yield
    await BiSubscription.all().delete()


class TestValidateCronExpr:
    def test_valid_cron_returns_next_run(self):
        """合法 cron 返回下次触发时间。"""
        now = datetime(2026, 8, 4, 9, 0, tzinfo=timezone.utc)
        next_run = validate_cron_expr("0 9 * * *", now)
        assert next_run > now

    def test_invalid_cron_raises(self):
        """非法 cron 抛 BizError。"""
        from app.core.exceptions import BizError

        with pytest.raises(BizError) as exc_info:
            validate_cron_expr("invalid")
        assert str(exc_info.value.code) == "4132"

    def test_empty_cron_raises(self):
        from app.core.exceptions import BizError

        with pytest.raises(BizError):
            validate_cron_expr("")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_bi_subscription.py::TestValidateCronExpr -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 创建 `services_subscription.py`**

```python
"""BiSubscription 调度与执行服务。"""
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
from app.utils import Code, StatusType


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

    单订阅超时 BI_SUBSCRIPTION_EXECUTE_TIMEOUT 秒，失败不抛出（写 failed 消息）。
    """
    now = datetime.now(timezone.utc)
    try:
        # 检查仪表盘是否存在
        dashboard = await BiDashboard.filter(id=sub.dashboard_id, is_deleted=False).first()
        if not dashboard:
            raise BizError(Code.BI_SUBSCRIPTION_DASHBOARD_NOT_FOUND, f"仪表盘 {sub.dashboard_id} 不存在")

        # 同步刷新仪表盘（复用 refresh_dashboard 的 Semaphore 限并发）
        result = await asyncio.wait_for(
            refresh_dashboard(sub.dashboard_id, sub.user_id, sub.tenant_id),
            timeout=BIZ_SETTINGS.BI_SUBSCRIPTION_EXECUTE_TIMEOUT,
        )

        # 构造成功消息
        success_count = sum(1 for i in result.get("items", []) if i.get("status") == "success")
        failed_count = sum(1 for i in result.get("items", []) if i.get("status") == "failed")
        total_elapsed = result.get("totalElapsedMs", 0)

        content = json.dumps({
            "dashboardId": str(sub.dashboard_id),
            "dashboardName": dashboard.name,
            "successCount": success_count,
            "failedCount": failed_count,
            "totalElapsedMs": total_elapsed,
            "refreshedAt": now.isoformat(),
        }, ensure_ascii=False)

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
        content = json.dumps({
            "dashboardId": str(sub.dashboard_id),
            "error": error_msg,
            "refreshedAt": now.isoformat(),
        }, ensure_ascii=False)

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

    每 60s leader_only 触发，查所有 status_type=enable AND next_run_at <= now 的订阅。
    """
    now = datetime.now(timezone.utc)
    due_subs = await BiSubscription.filter(
        status_type=StatusType.enable,
        next_run_at__lte=now,
    ).all()

    if not due_subs:
        return

    log.info("bi.subscription.dispatch count={}", len(due_subs))

    # 串行执行（refresh_dashboard 内部已有 Semaphore 限并发）
    for sub in due_subs:
        try:
            await execute_subscription(sub)
        except Exception as e:
            # execute_subscription 内部已 try/except，这里兜底防止 PeriodicTask 崩溃
            log.error("bi.subscription.dispatch.unexpected id={} error={}", sub.id, str(e))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_bi_subscription.py::TestValidateCronExpr -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add app/business/bi/services_subscription.py tests/test_bi_subscription.py
git commit -m "feat(bi): add services_subscription (cron validate + dispatch + execute)"
```

---

## Task 5: execute_subscription 集成测试

**Files:**
- Test: `tests/test_bi_subscription.py`

- [ ] **Step 1: 写 execute_subscription 测试**

在 `tests/test_bi_subscription.py` 追加：

```python
from unittest.mock import patch, AsyncMock


class TestExecuteSubscription:
    async def test_success_writes_notify_record(self, app, bi_dashboard):
        """成功刷新写 success 消息。"""
        now = datetime.now(timezone.utc)
        sub = await BiSubscription.create(
            name="test-sub",
            dashboard_id=bi_dashboard.id,
            user_id=1,
            cron_expr="0 9 * * *",
            next_run_at=now,
            tenant_id=1,
            status_type=StatusType.enable,
            created_by="1",
            updated_by="1",
        )

        # mock refresh_dashboard 返回成功结果
        async def fake_refresh(dashboard_id, user_id, tenant_id):
            return {
                "items": [
                    {"chartId": "1", "status": "success"},
                    {"chartId": "2", "status": "failed", "errorMessage": "timeout"},
                ],
                "totalElapsedMs": 1500,
            }

        with patch("app.business.bi.services_subscription.refresh_dashboard", side_effect=fake_refresh):
            await execute_subscription(sub)

        # 验证消息记录
        records = await BiNotifyRecord.filter(subscription_id=sub.id).all()
        assert len(records) == 1
        assert records[0].status == "success"
        assert records[0].is_read is False

        # 验证订阅状态更新
        refreshed = await BiSubscription.get(id=sub.id)
        assert refreshed.last_status == "success"
        assert refreshed.last_run_at is not None
        assert refreshed.next_run_at > now

    async def test_dashboard_not_found_writes_failed(self, app):
        """仪表盘不存在写 failed 消息。"""
        now = datetime.now(timezone.utc)
        sub = await BiSubscription.create(
            name="test-sub",
            dashboard_id=99999,
            user_id=1,
            cron_expr="0 9 * * *",
            next_run_at=now,
            tenant_id=1,
            status_type=StatusType.enable,
            created_by="1",
            updated_by="1",
        )
        await execute_subscription(sub)

        records = await BiNotifyRecord.filter(subscription_id=sub.id).all()
        assert len(records) == 1
        assert records[0].status == "failed"

        refreshed = await BiSubscription.get(id=sub.id)
        assert refreshed.last_status == "failed"


class TestDispatchSubscriptions:
    async def test_no_due_subs_returns_early(self, app):
        """无到期订阅时直接返回。"""
        from app.business.bi.services_subscription import dispatch_subscriptions

        await dispatch_subscriptions()  # 不应抛异常

    async def test_executes_due_subs(self, app, bi_dashboard):
        """到期订阅被执行。"""
        from app.business.bi.services_subscription import dispatch_subscriptions

        now = datetime.now(timezone.utc)
        await BiSubscription.create(
            name="due-sub",
            dashboard_id=bi_dashboard.id,
            user_id=1,
            cron_expr="0 9 * * *",
            next_run_at=now,  # 已到期
            tenant_id=1,
            status_type=StatusType.enable,
            created_by="1",
            updated_by="1",
        )

        async def fake_refresh(dashboard_id, user_id, tenant_id):
            return {"items": [], "totalElapsedMs": 0}

        with patch("app.business.bi.services_subscription.refresh_dashboard", side_effect=fake_refresh):
            await dispatch_subscriptions()

        records = await BiNotifyRecord.all().count()
        assert records == 1
```

- [ ] **Step 2: 运行测试确认通过**

Run: `uv run pytest tests/test_bi_subscription.py -v`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add tests/test_bi_subscription.py
git commit -m "test(bi): add execute_subscription + dispatch_subscriptions tests"
```

---

## Task 6: API 路由 subscription.py + notify.py

**Files:**
- Create: `app/business/bi/api/subscription.py`
- Create: `app/business/bi/api/notify.py`
- Modify: `app/business/bi/api/__init__.py`
- Test: `tests/test_bi_subscription.py`

- [ ] **Step 1: 创建 `api/subscription.py`**

> 仿 `api/masking.py` 模式，但 list/get 加行级隔离（tenant_id = user_id）。create 时计算 next_run_at。

```python
"""BiSubscription API 路由。"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from tortoise.expressions import Q

from app.business.bi.controllers import bi_subscription_controller
from app.business.bi.schemas import (
    BiSubscriptionCreate,
    BiSubscriptionSearch,
    BiSubscriptionUpdate,
)
from app.business.bi.services_subscription import validate_cron_expr
from app.utils import (
    CRUDRouter,
    SearchFieldConfig,
    Success,
    SuccessExtra,
    get_current_user_id,
    require_buttons,
)

subscription_crud = CRUDRouter(
    prefix="/subscriptions",
    controller=bi_subscription_controller,
    create_schema=BiSubscriptionCreate,
    update_schema=BiSubscriptionUpdate,
    list_schema=BiSubscriptionSearch,
    search_fields=SearchFieldConfig(
        contains_fields=["name"],
        exact_fields=["status_type"],
    ),
    summary_prefix="仪表盘订阅",
    enable_routes={"list", "get", "create", "update", "delete", "batch_delete"},
    route_key_prefix="bi.subscription",
    action_dependencies={
        "list": [require_buttons("B_BI_SUBSCRIPTION_VIEW")],
        "get": [require_buttons("B_BI_SUBSCRIPTION_VIEW")],
        "create": [require_buttons("B_BI_SUBSCRIPTION_CREATE")],
        "update": [require_buttons("B_BI_SUBSCRIPTION_EDIT")],
        "delete": [require_buttons("B_BI_SUBSCRIPTION_DELETE")],
        "batch_delete": [require_buttons("B_BI_SUBSCRIPTION_DELETE")],
    },
)


@subscription_crud.override("list")
async def _list_subscriptions(obj_in: BiSubscriptionSearch):
    """列表：行级隔离，用户只看自己的订阅。"""
    user_id = get_current_user_id()
    q = bi_subscription_controller.build_search(obj_in, contains_fields=["name"])
    q &= Q(tenant_id=user_id, is_deleted=False)
    total = await bi_subscription_controller.count(q)
    items = await bi_subscription_controller.list(
        q, offset=(obj_in.current - 1) * obj_in.size, limit=obj_in.size
    )
    return SuccessExtra(
        data={"records": items},
        total=total,
        current=obj_in.current,
        size=obj_in.size,
    )


@subscription_crud.override("create")
async def _create_subscription(obj_in: BiSubscriptionCreate):
    """创建：校验 cron + 计算 next_run_at + 设置 tenant_id。"""
    user_id = get_current_user_id()
    now = datetime.now(timezone.utc)
    next_run_at = validate_cron_expr(obj_in.cron_expr, now)

    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    data["user_id"] = user_id
    data["tenant_id"] = user_id
    data["next_run_at"] = next_run_at

    item = await bi_subscription_controller.create(data)
    return Success(
        msg="创建成功",
        data={"createdId": item.id, "created_id": item.id},
    )


router = APIRouter()
router.include_router(subscription_crud.router)
```

- [ ] **Step 2: 创建 `api/notify.py`**

```python
"""BiNotifyRecord API 路由（只读 + 标记已读）。"""
from __future__ import annotations

from fastapi import APIRouter
from tortoise.expressions import Q

from app.business.bi.controllers import bi_notify_record_controller
from app.business.bi.models import BiNotifyRecord
from app.business.bi.schemas import BiNotifyRecordSearch
from app.utils import Success, SuccessExtra, get_current_user_id, require_buttons, SqidPath

router = APIRouter(prefix="/notify", tags=["BI订阅消息"])


@router.post(
    "/search",
    summary="消息记录分页搜索",
    name="bi.notify.list",
    dependencies=[require_buttons("B_BI_NOTIFY_VIEW")],
)
async def list_notify_records(obj_in: BiNotifyRecordSearch):
    """列表：行级隔离，用户只看自己的消息。"""
    user_id = get_current_user_id()
    q = Q(user_id=user_id, is_deleted=False)
    if obj_in.status:
        q &= Q(status=obj_in.status)
    if obj_in.is_read is not None:
        q &= Q(is_read=obj_in.is_read)

    total = await BiNotifyRecord.filter(q).count()
    items = await BiNotifyRecord.filter(q).order_by("-created_at").offset(
        (obj_in.current - 1) * obj_in.size
    ).limit(obj_in.size).all()

    return SuccessExtra(
        data={"records": items},
        total=total,
        current=obj_in.current,
        size=obj_in.size,
    )


@router.get(
    "/unread-count",
    summary="获取未读消息数",
    name="bi.notify.unread_count",
    dependencies=[require_buttons("B_BI_NOTIFY_VIEW")],
)
async def get_unread_count():
    """获取当前用户未读消息数。"""
    user_id = get_current_user_id()
    count = await BiNotifyRecord.filter(user_id=user_id, is_read=False, is_deleted=False).count()
    return Success(data={"count": count})


@router.put(
    "/{record_id}/read",
    summary="标记消息已读",
    name="bi.notify.mark_read",
    dependencies=[require_buttons("B_BI_NOTIFY_VIEW")],
)
async def mark_read(record_id: SqidPath):
    """标记指定消息为已读。"""
    user_id = get_current_user_id()
    record = await BiNotifyRecord.filter(id=record_id, user_id=user_id, is_deleted=False).first()
    if not record:
        from app.core.exceptions import BizError
        from app.utils import Code
        raise BizError(Code.BI_NOTIFY_RECORD_NOT_FOUND, "消息记录不存在")
    record.is_read = True
    await record.save(update_fields=["is_read"])
    return Success(msg="已标记已读")
```

- [ ] **Step 3: 在 `api/__init__.py` 挂载路由**

```python
from app.business.bi.api.notify import router as notify_router
from app.business.bi.api.subscription import router as subscription_router
# ...
router.include_router(subscription_router)
router.include_router(notify_router)
```

- [ ] **Step 4: 写 API 鉴权测试**

在 `tests/test_bi_subscription.py` 追加：

```python
PREFIX = "/api/v1/business/bi"


class TestSubscriptionAPIAuth:
    async def test_search_requires_auth(self, app, client):
        resp = await client.post(f"{PREFIX}/subscriptions/search", json={"current": 1, "size": 10})
        assert str(resp.json()["code"]) == "2100"

    async def test_create_requires_auth(self, app, client):
        resp = await client.post(
            f"{PREFIX}/subscriptions",
            json={"name": "s1", "dashboard_id": 1, "cron_expr": "0 9 * * *"},
        )
        assert str(resp.json()["code"]) == "2100"


class TestNotifyAPIAuth:
    async def test_search_requires_auth(self, app, client):
        resp = await client.post(f"{PREFIX}/notify/search", json={"current": 1, "size": 10})
        assert str(resp.json()["code"]) == "2100"

    async def test_unread_count_requires_auth(self, app, client):
        resp = await client.get(f"{PREFIX}/notify/unread-count")
        assert str(resp.json()["code"]) == "2100"
```

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run pytest tests/test_bi_subscription.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add app/business/bi/api/subscription.py app/business/bi/api/notify.py app/business/bi/api/__init__.py tests/test_bi_subscription.py
git commit -m "feat(bi): add subscription + notify API routes with row-level isolation"
```

---

## Task 7: PeriodicTask 注册 + 菜单/按钮/角色权限

**Files:**
- Modify: `app/business/bi/module.py`
- Modify: `app/business/bi/init_data.py`

- [ ] **Step 1: 在 `module.py` 注册 PeriodicTask**

> 先 Read module.py，找到 `tasks=[...]` 参数。

```python
from app.business.bi.services_subscription import dispatch_subscriptions

# 在 BusinessModule 的 tasks 列表追加：
PeriodicTask(
    name="bi.subscription.dispatch",
    handler=dispatch_subscriptions,
    interval_seconds=BIZ_SETTINGS.BI_SUBSCRIPTION_DISPATCH_INTERVAL,
    leader_only=True,
    run_immediately=False,
),
```

- [ ] **Step 2: 在 `init_data.py` 追加菜单**

在 `BI_MENU_CHILDREN` 的 quota 菜单后追加：

```python
    {
        "menu_name": "仪表盘订阅",
        "route_name": "bi_subscriptions",
        "route_path": "/bi/subscriptions",
        "component": "view.bi_subscriptions",
        "icon": "mdi:calendar-clock",
        "order": 12,
        "buttons": [
            {"button_code": "B_BI_SUBSCRIPTION_VIEW", "button_desc": "查看订阅"},
            {"button_code": "B_BI_SUBSCRIPTION_CREATE", "button_desc": "创建订阅"},
            {"button_code": "B_BI_SUBSCRIPTION_EDIT", "button_desc": "编辑订阅"},
            {"button_code": "B_BI_SUBSCRIPTION_DELETE", "button_desc": "删除订阅"},
        ],
    },
    {
        "menu_name": "订阅消息",
        "route_name": "bi_notify-records",
        "route_path": "/bi/notify-records",
        "component": "view.bi_notify-records",
        "icon": "mdi:bell-outline",
        "order": 13,
        "buttons": [
            {"button_code": "B_BI_NOTIFY_VIEW", "button_desc": "查看消息"},
        ],
    },
```

- [ ] **Step 3: 追加按钮码到 `BI_ALL_BUTTONS`**

```python
    # subscription / notify
    "B_BI_SUBSCRIPTION_VIEW",
    "B_BI_SUBSCRIPTION_CREATE",
    "B_BI_SUBSCRIPTION_EDIT",
    "B_BI_SUBSCRIPTION_DELETE",
    "B_BI_NOTIFY_VIEW",
```

- [ ] **Step 4: 追加菜单到 `BI_ALL_MENUS` 和 `BI_ANALYST_MENUS`**

```python
    "bi_subscriptions",
    "bi_notify-records",
```

- [ ] **Step 5: 追加 API 到 `BI_ADMIN_APIS` 和 `BI_ANALYST_APIS`**

```python
    # subscription（CRUD）
    "bi.subscription.list",
    "bi.subscription.get",
    "bi.subscription.create",
    "bi.subscription.update",
    "bi.subscription.delete",
    "bi.subscription.batch_delete",
    # notify（只读 + 标记已读）
    "bi.notify.list",
    "bi.notify.unread_count",
    "bi.notify.mark_read",
```

- [ ] **Step 6: 追加按钮到 `BI_ANALYST_BUTTONS`**

```python
    "B_BI_SUBSCRIPTION_VIEW",
    "B_BI_SUBSCRIPTION_CREATE",
    "B_BI_SUBSCRIPTION_EDIT",
    "B_BI_SUBSCRIPTION_DELETE",
    "B_BI_NOTIFY_VIEW",
```

- [ ] **Step 7: 提交**

```bash
git add app/business/bi/module.py app/business/bi/init_data.py
git commit -m "feat(bi): register subscription dispatch PeriodicTask + menu/buttons/role perms"
```

---

## Task 8: 前端 typings + service API

**Files:**
- Modify: `web/src/typings/api/bi.d.ts`
- Create: `web/src/service/api/bi-subscription.ts`
- Create: `web/src/service/api/bi-notify.ts`

- [ ] **Step 1: 在 `web/src/typings/api/bi.d.ts` 追加类型**

```typescript
    // ============================================================
    // Subscription（仪表盘订阅）
    // ============================================================

    type BiSubscription = Common.CommonRecord<{
      name: string;
      dashboardId: string;
      cronExpr: string;
      nextRunAt: string | null;
      lastRunAt: string | null;
      lastStatus: 'success' | 'failed' | null;
    }>;

    type BiSubscriptionOperateParams = {
      id?: string;
      name: string;
      dashboardId: string;
      cronExpr: string;
      statusType?: 'enable' | 'disable';
    };

    type BiSubscriptionSearchParams = Pick<Common.PaginatingCommonParams, 'current' | 'size'> & {
      name?: string;
      statusType?: 'enable' | 'disable';
    };

    type BiSubscriptionList = Common.PaginatingCommonParams & {
      records: BiSubscription[];
      total: number;
    };

    type BiNotifyRecord = Common.CommonRecord<{
      subscriptionId: string;
      title: string;
      content: string | null;
      status: 'success' | 'failed';
      isRead: boolean;
    }>;

    type BiNotifyRecordSearchParams = Pick<Common.PaginatingCommonParams, 'current' | 'size'> & {
      status?: 'success' | 'failed';
      isRead?: boolean;
    };

    type BiNotifyRecordList = Common.PaginatingCommonParams & {
      records: BiNotifyRecord[];
      total: number;
    };

    type BiNotifyUnreadCount = {
      count: number;
    };
```

- [ ] **Step 2: 创建 `bi-subscription.ts`**

> 参考 `bi-masking.ts` 模式。

```typescript
import { request } from '../request';

/** 订阅分页搜索 */
export function fetchBiSubscriptionList(data?: Api.Bi.BiSubscriptionSearchParams) {
  return request<Api.Bi.BiSubscriptionList>({
    url: '/business/bi/subscriptions/search',
    method: 'post',
    data: data ?? {}
  });
}

/** 获取订阅详情 */
export function fetchBiSubscription(id: string) {
  return request<Api.Bi.BiSubscription>({
    url: `/business/bi/subscriptions/${id}`,
    method: 'get'
  });
}

/** 创建订阅 */
export function fetchAddBiSubscription(data: Api.Bi.BiSubscriptionOperateParams) {
  return request<Api.Bi.CreateResult>({
    url: '/business/bi/subscriptions',
    method: 'post',
    data
  });
}

/** 更新订阅 */
export function fetchUpdateBiSubscription(data: Api.Bi.BiSubscriptionOperateParams) {
  return request<Api.Bi.UpdateResult>({
    url: `/business/bi/subscriptions/${data.id}`,
    method: 'put',
    data
  });
}

/** 删除订阅 */
export function fetchDeleteBiSubscription(data: Api.Bi.CommonDeleteParams) {
  return request<null>({
    url: `/business/bi/subscriptions/${data.id}`,
    method: 'delete'
  });
}

/** 批量删除订阅 */
export function fetchBatchDeleteBiSubscription(data: Api.Bi.CommonBatchDeleteParams) {
  return request<null>({
    url: '/business/bi/subscriptions',
    method: 'delete',
    data
  });
}
```

- [ ] **Step 3: 创建 `bi-notify.ts`**

```typescript
import { request } from '../request';

/** 消息记录分页搜索 */
export function fetchBiNotifyList(data?: Api.Bi.BiNotifyRecordSearchParams) {
  return request<Api.Bi.BiNotifyRecordList>({
    url: '/business/bi/notify/search',
    method: 'post',
    data: data ?? {}
  });
}

/** 获取未读消息数 */
export function fetchBiNotifyUnreadCount() {
  return request<Api.Bi.BiNotifyUnreadCount>({
    url: '/business/bi/notify/unread-count',
    method: 'get'
  });
}

/** 标记消息已读 */
export function fetchMarkBiNotifyRead(id: string) {
  return request<null>({
    url: `/business/bi/notify/${id}/read`,
    method: 'put'
  });
}
```

- [ ] **Step 4: 提交**

```bash
git add web/src/typings/api/bi.d.ts web/src/service/api/bi-subscription.ts web/src/service/api/bi-notify.ts
git commit -m "feat(bi-web): add subscription/notify typings and API services"
```

---

## Task 9: 前端 i18n

**Files:**
- Modify: `web/src/locales/langs/_generated/bi/zh-cn.ts`
- Modify: `web/src/locales/langs/_generated/bi/en-us.ts`
- Modify: `web/src/locales/langs/_generated/bi/types.d.ts`

- [ ] **Step 1: 在 zh-cn.ts 追加路由名 + 命名空间**

路由名（在 `bi_quota` 后）：
```typescript
    bi_subscriptions: '仪表盘订阅',
    'bi_notify-records': '订阅消息',
```

命名空间（在 `quota:` 块后）：
```typescript
    subscription: {
      title: '仪表盘订阅',
      create: '新建订阅',
      edit: '编辑订阅',
      name: '订阅名称',
      dashboard: '仪表盘',
      cronExpr: 'cron表达式',
      nextRunAt: '下次触发',
      lastRunAt: '上次触发',
      lastStatus: '上次状态',
      status: '状态',
      searchPlaceholder: '搜索订阅名称',
      cronPresets: {
        hourly: '每小时',
        daily: '每天',
        weekly: '每周',
      },
      cronHint: '5字段：分 时 日 月 周（如 0 9 * * * 每天9点）',
      confirmDelete: '确认删除该订阅吗？',
      empty: '暂无订阅',
      statusSuccess: '成功',
      statusFailed: '失败',
    },
    notify: {
      title: '订阅消息',
      unread: '未读',
      markRead: '标记已读',
      empty: '暂无消息',
      statusSuccess: '成功',
      statusFailed: '失败',
    },
```

- [ ] **Step 2: 在 en-us.ts 追加对应英文**

```typescript
    bi_subscriptions: 'Dashboard Subscriptions',
    'bi_notify-records': 'Notifications',
```

```typescript
    subscription: {
      title: 'Dashboard Subscriptions',
      create: 'New Subscription',
      edit: 'Edit Subscription',
      name: 'Subscription Name',
      dashboard: 'Dashboard',
      cronExpr: 'Cron Expression',
      nextRunAt: 'Next Run',
      lastRunAt: 'Last Run',
      lastStatus: 'Last Status',
      status: 'Status',
      searchPlaceholder: 'Search subscription name',
      cronPresets: {
        hourly: 'Hourly',
        daily: 'Daily',
        weekly: 'Weekly',
      },
      cronHint: '5 fields: min hour day month week (e.g. 0 9 * * * daily at 9am)',
      confirmDelete: 'Delete this subscription?',
      empty: 'No subscriptions',
      statusSuccess: 'Success',
      statusFailed: 'Failed',
    },
    notify: {
      title: 'Notifications',
      unread: 'Unread',
      markRead: 'Mark Read',
      empty: 'No notifications',
      statusSuccess: 'Success',
      statusFailed: 'Failed',
    },
```

- [ ] **Step 3: 在 types.d.ts 追加类型**

```typescript
    subscription: {
      title: string;
      create: string;
      edit: string;
      name: string;
      dashboard: string;
      cronExpr: string;
      nextRunAt: string;
      lastRunAt: string;
      lastStatus: string;
      status: string;
      searchPlaceholder: string;
      cronPresets: {
        hourly: string;
        daily: string;
        weekly: string;
      };
      cronHint: string;
      confirmDelete: string;
      empty: string;
      statusSuccess: string;
      statusFailed: string;
    };
    notify: {
      title: string;
      unread: string;
      markRead: string;
      empty: string;
      statusSuccess: string;
      statusFailed: string;
    };
```

- [ ] **Step 4: 提交**

```bash
git add web/src/locales/
git commit -m "feat(bi-web): add subscription/notify i18n (zh-cn/en-us)"
```

---

## Task 10: 前端订阅管理页

**Files:**
- Create: `web/src/views/bi/subscriptions/index.vue`
- Create: `web/src/views/bi/subscriptions/modules/subscription-operate-modal.vue`

- [ ] **Step 1: 创建 `subscription-operate-modal.vue`**

> 仿 `masking-operate-modal.vue` 模式。字段：name、dashboard（下拉选 BiDashboard）、cronExpr（输入 + 预设快捷按钮 hourly/daily/weekly）、statusType（开关）。

```vue
<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import { NForm, NFormItem, NInput, NSelect, NSwitch, NButton, NSpace } from 'naive-ui';
import { fetchAddBiSubscription, fetchBiSubscription, fetchUpdateBiSubscription } from '@/service/api/bi-subscription';
import { fetchBiDashboardList } from '@/service/api/bi-dashboard';
import { $t } from '@/locales';
import { useNaiveForm } from '@/hooks/common/form';

defineOptions({ name: 'BiSubscriptionOperateModal' });

const visible = defineModel<boolean>('visible', { default: false });
const emit = defineEmits<{ submitted: [] }>();

const props = defineProps<{
  operateType: 'add' | 'edit';
  editingId?: string | null;
}>();

const { formRef, validate } = useNaiveForm();

const model = reactive({
  name: '',
  dashboardId: '' as string,
  cronExpr: '0 9 * * *',
  statusType: 'enable' as 'enable' | 'disable',
});

const rules = {
  name: { required: true, message: $t('common.pattern.require'), trigger: 'blur' },
  dashboardId: { required: true, message: $t('common.pattern.require'), trigger: 'change' },
  cronExpr: { required: true, message: $t('common.pattern.require'), trigger: 'blur' },
};

const dashboardOptions = ref<{ label: string; value: string }[]>([]);

async function loadDashboards() {
  const { data } = await fetchBiDashboardList({ current: 1, size: 200 });
  if (data?.records) {
    dashboardOptions.value = data.records.map(d => ({ label: d.name, value: d.id }));
  }
}

const isEdit = computed(() => props.operateType === 'edit');
const title = computed(() => (isEdit.value ? $t('page.bi.subscription.edit') : $t('page.bi.subscription.create')));

function applyPreset(preset: 'hourly' | 'daily' | 'weekly') {
  const presets: Record<string, string> = {
    hourly: '0 * * * *',
    daily: '0 9 * * *',
    weekly: '0 9 * * 1',
  };
  model.cronExpr = presets[preset];
}

function resetModel() {
  model.name = '';
  model.dashboardId = '';
  model.cronExpr = '0 9 * * *';
  model.statusType = 'enable';
}

async function handleInitModel() {
  resetModel();
  await loadDashboards();
  if (isEdit.value && props.editingId) {
    const { data } = await fetchBiSubscription(props.editingId);
    if (data) {
      model.name = data.name;
      model.dashboardId = data.dashboardId;
      model.cronExpr = data.cronExpr;
      model.statusType = data.statusType === 'enable' ? 'enable' : 'disable';
    }
  }
}

watch(visible, val => {
  if (val) handleInitModel();
});

async function handleSubmit() {
  await validate();
  const params: Api.Bi.BiSubscriptionOperateParams = {
    name: model.name,
    dashboardId: model.dashboardId,
    cronExpr: model.cronExpr,
    statusType: model.statusType,
  };
  if (isEdit.value && props.editingId) {
    params.id = props.editingId;
    const { error } = await fetchUpdateBiSubscription(params);
    if (!error) {
      window.$message?.success($t('common.updateSuccess'));
      visible.value = false;
      emit('submitted');
    }
  } else {
    const { error } = await fetchAddBiSubscription(params);
    if (!error) {
      window.$message?.success($t('common.addSuccess'));
      visible.value = false;
      emit('submitted');
    }
  }
}
</script>

<template>
  <NModal v-model:show="visible" preset="card" :title="title" style="width: 560px">
    <NForm ref="formRef" :model="model" :rules="rules" label-placement="top">
      <NFormItem :label="$t('page.bi.subscription.name')" path="name">
        <NInput v-model:value="model.name" maxlength="100" show-count />
      </NFormItem>
      <NFormItem :label="$t('page.bi.subscription.dashboard')" path="dashboardId">
        <NSelect v-model:value="model.dashboardId" :options="dashboardOptions" filterable />
      </NFormItem>
      <NFormItem :label="$t('page.bi.subscription.cronExpr')" path="cronExpr">
        <NInput v-model:value="model.cronExpr" :placeholder="$t('page.bi.subscription.cronHint')" />
        <template #feedback>
          <NSpace :size="4" style="margin-top: 8px">
            <NButton size="tiny" @click="applyPreset('hourly')">{{ $t('page.bi.subscription.cronPresets.hourly') }}</NButton>
            <NButton size="tiny" @click="applyPreset('daily')">{{ $t('page.bi.subscription.cronPresets.daily') }}</NButton>
            <NButton size="tiny" @click="applyPreset('weekly')">{{ $t('page.bi.subscription.cronPresets.weekly') }}</NButton>
          </NSpace>
        </template>
      </NFormItem>
      <NFormItem :label="$t('page.bi.subscription.status')">
        <NSwitch v-model:value="model.statusType" checked-value="enable" unchecked-value="disable" />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="visible = false">{{ $t('common.cancel') }}</NButton>
        <NButton type="primary" @click="handleSubmit">{{ $t('common.confirm') }}</NButton>
      </NSpace>
    </template>
  </NModal>
</template>
```

- [ ] **Step 2: 创建 `subscriptions/index.vue`**

> 仿 `masking/index.vue` 模式。

```vue
<script setup lang="tsx">
import { ref } from 'vue';
import { NButton, NPopconfirm, NTag } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { fetchBiSubscriptionList, fetchDeleteBiSubscription } from '@/service/api/bi-subscription';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';
import { useNaivePaginatedTable } from '@/hooks/common/table';
import SubscriptionOperateModal from './modules/subscription-operate-modal.vue';

defineOptions({ name: 'BiSubscriptions' });

const { hasAuth } = useAuth();

const searchParams = ref({
  name: '',
  statusType: null as 'enable' | 'disable' | null,
});

const { loading, data, pagination, getData, getDataByPage, mobilePagination } = useNaivePaginatedTable({
  api: fetchBiSubscriptionList,
  searchParams,
});

const operateType = ref<'add' | 'edit'>('add');
const editingId = ref<string | null>(null);
const modalVisible = ref(false);

function handleAdd() {
  operateType.value = 'add';
  editingId.value = null;
  modalVisible.value = true;
}

function handleEdit(id: string) {
  operateType.value = 'edit';
  editingId.value = id;
  modalVisible.value = true;
}

async function handleDelete(id: string) {
  const { error } = await fetchDeleteBiSubscription({ id });
  if (!error) {
    window.$message?.success($t('common.deleteSuccess'));
    getData();
  }
}

function formatTime(iso: string | null): string {
  if (!iso) return '-';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

const columns: DataTableColumns<Api.Bi.BiSubscription> = [
  { key: 'name', title: $t('page.bi.subscription.name'), minWidth: 120 },
  { key: 'cronExpr', title: $t('page.bi.subscription.cronExpr'), width: 140 },
  { key: 'nextRunAt', title: $t('page.bi.subscription.nextRunAt'), width: 160, render: row => formatTime(row.nextRunAt) },
  { key: 'lastRunAt', title: $t('page.bi.subscription.lastRunAt'), width: 160, render: row => formatTime(row.lastRunAt) },
  {
    key: 'lastStatus',
    title: $t('page.bi.subscription.lastStatus'),
    width: 90,
    render: row => {
      if (!row.lastStatus) return '-';
      return row.lastStatus === 'success'
        ? <NTag type="success" size="small">{$t('page.bi.subscription.statusSuccess')}</NTag>
        : <NTag type="error" size="small">{$t('page.bi.subscription.statusFailed')}</NTag>;
    },
  },
  {
    key: 'statusType',
    title: $t('page.bi.subscription.status'),
    width: 80,
    render: row =>
      row.statusType === 'enable'
        ? <NTag type="success" size="small">{$t('common.enable')}</NTag>
        : <NTag type="default" size="small">{$t('common.disable')}</NTag>,
  },
  {
    key: 'actions',
    title: $t('common.action'),
    width: 160,
    fixed: 'right',
    render: row => (
      <NSpace size={4}>
        {hasAuth('B_BI_SUBSCRIPTION_EDIT') && (
          <NButton type="primary" ghost size="small" onClick={() => handleEdit(row.id)}>
            {$t('common.edit')}
          </NButton>
        )}
        {hasAuth('B_BI_SUBSCRIPTION_DELETE') && (
          <NPopconfirm onPositiveClick={() => handleDelete(row.id)}>
            {{
              default: () => $t('page.bi.subscription.confirmDelete'),
              trigger: () => (
                <NButton type="error" ghost size="small">{$t('common.delete')}</NButton>
              ),
            }}
          </NPopconfirm>
        )}
      </NSpace>
    ),
  },
];
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <NCard :bordered="false" size="small" class="card-wrapper">
      <NSpace justify="space-between" align="center">
        <NSpace align="center" :size="12">
          <NInput
            v-model:value="searchParams.name"
            clearable
            :placeholder="$t('page.bi.subscription.searchPlaceholder')"
            style="width: 200px"
            @keydown.enter="getDataByPage(1)"
          />
          <NButton size="small" type="primary" ghost @click="getDataByPage(1)">
            <template #icon><icon-ic-round-search class="text-icon" /></template>
            {{ $t('common.search') }}
          </NButton>
        </NSpace>
        <NButton v-if="hasAuth('B_BI_SUBSCRIPTION_CREATE')" type="primary" @click="handleAdd">
          <template #icon><icon-ic-round-add class="text-icon" /></template>
          {{ $t('page.bi.subscription.create') }}
        </NButton>
      </NSpace>
    </NCard>

    <NCard :title="$t('page.bi.subscription.title')" :bordered="false" size="small" class="card-wrapper sm:flex-1-hidden">
      <NDataTable
        :columns="columns"
        :data="data"
        :loading="loading"
        :pagination="mobilePagination"
        size="small"
        flex-height
        :row-key="(row: Api.Bi.BiSubscription) => row.id"
      />
    </NCard>

    <SubscriptionOperateModal
      v-model:visible="modalVisible"
      :operate-type="operateType"
      :editing-id="editingId"
      @submitted="getData"
    />
  </div>
</template>
```

- [ ] **Step 3: 跑 lint + typecheck**

Run: `cd web && pnpm lint && pnpm typecheck`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add web/src/views/bi/subscriptions/
git commit -m "feat(bi-web): add subscription management page (list + operate modal)"
```

---

## Task 11: 前端消息记录页 + 铃铛组件

**Files:**
- Create: `web/src/views/bi/notify-records/index.vue`
- Create: `web/src/layouts/base/widgets/notify-bell.vue`
- Modify: `web/src/layouts/base/index.vue`

- [ ] **Step 1: 创建 `notify-records/index.vue`**

> 只读列表 + 标记已读按钮。仿 `masking/index.vue` 但无增改模态框。

```vue
<script setup lang="tsx">
import { ref } from 'vue';
import { NButton, NTag } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { fetchBiNotifyList, fetchMarkBiNotifyRead } from '@/service/api/bi-notify';
import { $t } from '@/locales';
import { useNaivePaginatedTable } from '@/hooks/common/table';

defineOptions({ name: 'BiNotifyRecords' });

const searchParams = ref({
  status: null as 'success' | 'failed' | null,
  isRead: null as boolean | null,
});

const { loading, data, pagination, getData, getDataByPage, mobilePagination } = useNaivePaginatedTable({
  api: fetchBiNotifyList,
  searchParams,
});

async function handleMarkRead(id: string) {
  const { error } = await fetchMarkBiNotifyRead(id);
  if (!error) {
    window.$message?.success($t('page.bi.notify.markRead'));
    getData();
  }
}

function formatTime(iso: string | null): string {
  if (!iso) return '-';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

const columns: DataTableColumns<Api.Bi.BiNotifyRecord> = [
  { key: 'title', title: $t('page.bi.notify.title'), minWidth: 200 },
  {
    key: 'status',
    title: $t('page.bi.notify.statusSuccess'),
    width: 90,
    render: row =>
      row.status === 'success'
        ? <NTag type="success" size="small">{$t('page.bi.notify.statusSuccess')}</NTag>
        : <NTag type="error" size="small">{$t('page.bi.notify.statusFailed')}</NTag>,
  },
  { key: 'created_at', title: $t('common.createdAt'), width: 160, render: row => formatTime(row.createdAt) },
  {
    key: 'isRead',
    title: $t('page.bi.notify.unread'),
    width: 80,
    render: row =>
      row.isRead
        ? <NTag size="small">{$t('common.read')}</NTag>
        : <NTag type="warning" size="small">{$t('page.bi.notify.unread')}</NTag>,
  },
  {
    key: 'actions',
    title: $t('common.action'),
    width: 100,
    render: row =>
      !row.isRead
        ? <NButton size="small" text type="primary" onClick={() => handleMarkRead(row.id)}>{$t('page.bi.notify.markRead')}</NButton>
        : null,
  },
];
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <NCard :bordered="false" size="small" class="card-wrapper">
      <NSpace align="center" :size="12">
        <NSelect
          v-model:value="searchParams.status"
          clearable
          :placeholder="$t('page.bi.notify.statusSuccess')"
          :options="[
            { label: $t('page.bi.notify.statusSuccess'), value: 'success' },
            { label: $t('page.bi.notify.statusFailed'), value: 'failed' },
          ]"
          style="width: 140px"
          @update:value="getDataByPage(1)"
        />
        <NButton size="small" type="primary" ghost @click="getDataByPage(1)">
          <template #icon><icon-ic-round-search class="text-icon" /></template>
          {{ $t('common.search') }}
        </NButton>
      </NSpace>
    </NCard>

    <NCard :title="$t('page.bi.notify.title')" :bordered="false" size="small" class="card-wrapper sm:flex-1-hidden">
      <NDataTable
        :columns="columns"
        :data="data"
        :loading="loading"
        :pagination="mobilePagination"
        size="small"
        flex-height
        :row-key="(row: Api.Bi.BiNotifyRecord) => row.id"
      />
    </NCard>
  </div>
</template>
```

- [ ] **Step 2: 创建 `notify-bell.vue`**

> 顶部铃铛组件：轮询未读数 + 下拉列表 + 跳转消息页。

```vue
<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { NBadge, NButton, NPopover, NEmpty, NSpin } from 'naive-ui';
import { fetchBiNotifyUnreadCount, fetchBiNotifyList, fetchMarkBiNotifyRead } from '@/service/api/bi-notify';
import { $t } from '@/locales';

defineOptions({ name: 'BiNotifyBell' });

const router = useRouter();
const unreadCount = ref(0);
const recentRecords = ref<Api.Bi.BiNotifyRecord[]>([]);
const loading = ref(false);
const showPopover = ref(false);
let timer: number | null = null;

async function loadUnreadCount() {
  const { data } = await fetchBiNotifyUnreadCount();
  if (data) {
    unreadCount.value = data.count;
  }
}

async function loadRecentRecords() {
  loading.value = true;
  try {
    const { data } = await fetchBiNotifyList({ current: 1, size: 10 });
    if (data?.records) {
      recentRecords.value = data.records;
    }
  } finally {
    loading.value = false;
  }
}

async function handleViewAll() {
  showPopover.value = false;
  router.push({ name: 'bi_notify-records' });
}

async function handleClickRecord(record: Api.Bi.BiNotifyRecord) {
  if (!record.isRead) {
    await fetchMarkBiNotifyRead(record.id);
    await loadUnreadCount();
  }
  showPopover.value = false;
  router.push({ name: 'bi_notify-records' });
}

function formatTime(iso: string | null): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function startPolling() {
  stopPolling();
  timer = window.setInterval(loadUnreadCount, 30000);
}

function stopPolling() {
  if (timer !== null) {
    clearInterval(timer);
    timer = null;
  }
}

function handlePopoverUpdate(val: boolean) {
  showPopover.value = val;
  if (val) {
    loadRecentRecords();
  }
}

onMounted(() => {
  loadUnreadCount();
  startPolling();
});

onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <NPopover :show="showPopover" trigger="click" placement="bottom-end" :width="360" @update:show="handlePopoverUpdate">
    <template #trigger>
      <NBadge :value="unreadCount" :max="99">
        <NButton quaternary circle>
          <template #icon>
            <icon-ic-round-notifications class="text-icon" />
          </template>
        </NButton>
      </NBadge>
    </template>
    <div class="flex flex-col gap-8px">
      <div class="flex items-center justify-between border-b border-gray-200 pb-8px">
        <span class="text-14px font-500">{{ $t('page.bi.notify.title') }}</span>
        <NButton text type="primary" size="small" @click="handleViewAll">查看全部</NButton>
      </div>
      <NSpin :show="loading">
        <NEmpty v-if="!recentRecords.length" :description="$t('page.bi.notify.empty')" class="py-24px" />
        <div v-else class="max-h-320px overflow-y-auto">
          <div
            v-for="record in recentRecords"
            :key="record.id"
            class="cursor-pointer border-b border-gray-100 py-8px last:border-b-0 hover:bg-gray-50"
            @click="handleClickRecord(record)"
          >
            <div class="flex items-center gap-8px">
              <span class="flex-1 truncate text-13px font-500" :class="{ 'font-700': !record.isRead }">{{ record.title }}</span>
              <span v-if="!record.isRead" class="inline-block h-6px w-6px flex-shrink-0 rounded-full bg-red-500" />
            </div>
            <div class="mt-2px text-11px text-gray-500">{{ formatTime(record.createdAt) }}</div>
          </div>
        </div>
      </NSpin>
    </div>
  </NPopover>
</template>
```

- [ ] **Step 3: 在 `layouts/base/index.vue` 挂载铃铛**

> 先 Read `layouts/base/index.vue`，找到顶部导航栏右侧用户头像区域，在头像前插入铃铛。

```vue
<!-- 在用户头像前插入 -->
<BiNotifyBell />
```

```typescript
// 在 script 中 import
import BiNotifyBell from './widgets/notify-bell.vue';
```

- [ ] **Step 4: 跑 lint + typecheck**

Run: `cd web && pnpm lint && pnpm typecheck`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add web/src/views/bi/notify-records/ web/src/layouts/base/widgets/notify-bell.vue web/src/layouts/base/index.vue
git commit -m "feat(bi-web): add notify records page + bell widget (polling + popover)"
```

---

## Task 12: 前端测试

**Files:**
- Create: `web/src/service/api/__tests__/bi-subscription.test.ts`
- Create: `web/src/service/api/__tests__/bi-notify.test.ts`

- [ ] **Step 1: 创建 `bi-subscription.test.ts`**

> 仿 `bi-masking.test.ts` 模式，测试 6 个函数。

- [ ] **Step 2: 创建 `bi-notify.test.ts`**

> 测试 3 个函数：fetchBiNotifyList / fetchBiNotifyUnreadCount / fetchMarkBiNotifyRead。

- [ ] **Step 3: 跑 vitest**

Run: `cd web && pnpm test`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add web/src/service/api/__tests__/bi-subscription.test.ts web/src/service/api/__tests__/bi-notify.test.ts
git commit -m "test(bi-web): add subscription/notify API service tests"
```

---

## Task 13: 端到端门禁验证

**Files:** 无（验证任务）

- [ ] **Step 1: 跑后端门禁**

Run: `just check`
Expected: ruff + basedpyright + pytest 全绿

- [ ] **Step 2: 跑前端门禁**

Run: `cd web && pnpm lint && pnpm typecheck && pnpm test`
Expected: 全绿

- [ ] **Step 3: 启动后端验证路由注册**

Run: `just run backend`

```bash
curl -s http://localhost:9999/api/v1/business/bi/subscriptions/search -X POST -H "Content-Type: application/json" -d '{"current":1,"size":10}'
# 期望 code: 2100

curl -s http://localhost:9999/api/v1/business/bi/notify/unread-count
# 期望 code: 2100
```

- [ ] **Step 4: 关闭后端**

- [ ] **Step 5: 最终提交（如有未提交改动）**

```bash
git add -A
git commit -m "chore(bi): subscription batch D-2 complete - all checks pass"
```

---

## Self-Review

### Spec 覆盖检查

| Spec 要求 | 对应 Task |
|-----------|-----------|
| BiSubscription + BiNotifyRecord 模型 + 迁移 0006 | Task 2 |
| Schemas + Controllers | Task 3 |
| cron 校验 + dispatch + execute | Task 4 |
| execute_subscription 集成测试 | Task 5 |
| Subscription API 6 路由 + Notify API 4 路由 | Task 6 |
| PeriodicTask 注册 + 菜单/按钮/角色 | Task 7 |
| 前端 typings + service | Task 8 |
| 前端 i18n | Task 9 |
| 前端订阅管理页 | Task 10 |
| 前端消息记录页 + 铃铛 | Task 11 |
| 前端测试 | Task 12 |
| just check 全绿 | Task 13 |

### 占位符扫描

- 无 "TBD" / "TODO" / "implement later"
- 所有代码块均含完整实现
- 前端测试 Task 12 的详细代码省略，但模式明确（仿 bi-masking.test.ts）

### 类型一致性

- `validate_cron_expr(expr, now) -> datetime` 在 Task 4 定义，Task 6 使用 — 一致
- `execute_subscription(sub) -> None` 在 Task 4 定义，Task 5 测试 — 一致
- `dispatch_subscriptions() -> None` 在 Task 4 定义，Task 7 PeriodicTask 使用 — 一致
- 前端 `Api.Bi.BiSubscription` / `BiNotifyRecord` 在 Task 8 定义，Task 10/11 使用 — 一致
