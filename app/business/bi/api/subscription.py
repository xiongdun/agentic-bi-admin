"""BiSubscription API 路由 — 仪表盘定时订阅 CRUD。

按钮码：
- ``B_BI_SUBSCRIPTION_VIEW`` —— 查看（list / get）
- ``B_BI_SUBSCRIPTION_CREATE`` —— 创建
- ``B_BI_SUBSCRIPTION_EDIT`` —— 编辑
- ``B_BI_SUBSCRIPTION_DELETE`` —— 删除（含批量）

接口列表：
- ``POST /subscriptions`` —— 创建订阅（校验 cron + 解码 dashboardId + 设置 next_run_at）
- ``POST /subscriptions/search`` —— 分页查询当前用户的订阅
- ``GET /subscriptions/{subscription_id}`` —— 查看订阅详情
- ``PUT /subscriptions/{subscription_id}`` —— 更新订阅（cron 变更时重算 next_run_at）
- ``DELETE /subscriptions/{subscription_id}`` —— 删除（软删）
- ``DELETE /subscriptions/batch_delete`` —— 批量删除

行级隔离：所有查询带 ``tenant_id=user_id``，用户只能查看/操作自己的订阅。

项目历史教训：
- ``/subscriptions/search`` 和 ``/subscriptions/batch_delete`` 必须声明在
  ``/subscriptions/{subscription_id}`` 之前，避免 ``search`` / ``batch_delete``
  被当作 sqid 路径参数解析
"""

from __future__ import annotations

from datetime import datetime, timezone

from croniter import croniter
from fastapi import APIRouter

from app.business.bi.models import BiSubscription
from app.business.bi.schemas import (
    BiSubscriptionCreate,
    BiSubscriptionSearch,
    BiSubscriptionUpdate,
)
from app.business.bi.services_subscription import validate_cron_expr
from app.core.exceptions import BizError
from app.utils import (
    Code,
    DependAuth,
    SqidPath,
    Success,
    SuccessExtra,
    decode_id,
    encode_id,
    get_current_user_id,
    require_buttons,
)

router = APIRouter()


def _subscription_brief(s: BiSubscription) -> dict:
    """列表/详情共用序列化。"""
    return {
        "id": encode_id(s.id),
        "name": s.name,
        "dashboardId": encode_id(s.dashboard_id),
        "cronExpr": s.cron_expr,
        "nextRunAt": s.next_run_at.isoformat() if s.next_run_at else None,
        "lastRunAt": s.last_run_at.isoformat() if s.last_run_at else None,
        "lastStatus": s.last_status,
        "statusType": s.status_type,
        "createdAt": s.created_at.isoformat() if s.created_at else None,
        "updatedAt": s.updated_at.isoformat() if s.updated_at else None,
    }


@router.post(
    "/subscriptions",
    summary="创建订阅",
    name="bi.subscription.create",
    dependencies=[DependAuth, require_buttons("B_BI_SUBSCRIPTION_CREATE")],
)
async def create_subscription_endpoint(obj_in: BiSubscriptionCreate):
    """创建订阅：校验 cron + 解码 dashboardId + 设置 next_run_at + tenant_id。"""
    user_id = get_current_user_id()
    now = datetime.now(timezone.utc)
    next_run_at = validate_cron_expr(obj_in.cron_expr, now)
    dashboard_id = decode_id(obj_in.dashboard_id)

    sub = await BiSubscription.create(
        name=obj_in.name,
        dashboard_id=dashboard_id,
        user_id=user_id,
        cron_expr=obj_in.cron_expr,
        next_run_at=next_run_at,
        tenant_id=user_id,
        status_type=obj_in.status_type,
        created_by=str(user_id),
        updated_by=str(user_id),
    )
    sqid = encode_id(sub.id)
    return Success(msg="创建成功", data={"createdId": sqid, "created_id": sqid})


@router.post(
    "/subscriptions/search",
    summary="订阅分页列表",
    name="bi.subscription.list",
    dependencies=[DependAuth, require_buttons("B_BI_SUBSCRIPTION_VIEW")],
)
async def list_subscriptions_endpoint(obj_in: BiSubscriptionSearch):
    """分页查询当前用户的订阅（按 id 倒序）。"""
    user_id = get_current_user_id()
    qs = BiSubscription.filter(tenant_id=user_id)
    if obj_in.name:
        qs = qs.filter(name__icontains=obj_in.name)
    if obj_in.status_type:
        qs = qs.filter(status_type=obj_in.status_type)

    total = await qs.count()
    subs = await qs.order_by("-id").offset((obj_in.current - 1) * obj_in.size).limit(obj_in.size)
    records = [_subscription_brief(s) for s in subs]
    return SuccessExtra(
        data={"records": records},
        total=total,
        current=obj_in.current,
        size=obj_in.size,
    )


@router.delete(
    "/subscriptions/batch_delete",
    summary="批量删除订阅",
    name="bi.subscription.batch_delete",
    dependencies=[DependAuth, require_buttons("B_BI_SUBSCRIPTION_DELETE")],
)
async def batch_delete_subscriptions_endpoint(obj_in):
    """批量软删订阅（仅能删除当前用户自己的）。"""
    user_id = get_current_user_id()
    ids = obj_in.ids if hasattr(obj_in, "ids") else obj_in.get("ids", [])
    deleted = 0
    for sid in ids:
        sub = await BiSubscription.get_or_none(id=sid, tenant_id=user_id)
        if sub:
            await sub.delete()  # SoftDeleteManager 设置 deleted_at
            deleted += 1
    return Success(msg="批量删除成功", data={"deletedCount": deleted})


@router.get(
    "/subscriptions/{subscription_id}",
    summary="订阅详情",
    name="bi.subscription.get",
    dependencies=[DependAuth, require_buttons("B_BI_SUBSCRIPTION_VIEW")],
)
async def get_subscription_endpoint(subscription_id: SqidPath):
    """查看订阅详情。"""
    user_id = get_current_user_id()
    sub = await BiSubscription.get_or_none(id=subscription_id, tenant_id=user_id)
    if not sub:
        raise BizError(Code.BI_SUBSCRIPTION_NOT_FOUND, "订阅不存在")
    return Success(data=_subscription_brief(sub))


@router.put(
    "/subscriptions/{subscription_id}",
    summary="更新订阅",
    name="bi.subscription.update",
    dependencies=[DependAuth, require_buttons("B_BI_SUBSCRIPTION_EDIT")],
)
async def update_subscription_endpoint(
    subscription_id: SqidPath,
    obj_in: BiSubscriptionUpdate,  # type: ignore[valid-type]
):
    """更新订阅（仅更新 schema 中显式传入的字段，cron 变更时重算 next_run_at）。"""
    user_id = get_current_user_id()
    sub = await BiSubscription.get_or_none(id=subscription_id, tenant_id=user_id)
    if not sub:
        raise BizError(Code.BI_SUBSCRIPTION_NOT_FOUND, "订阅不存在")

    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    if "name" in data:
        sub.name = data["name"]
    if "dashboard_id" in data:
        sub.dashboard_id = decode_id(data["dashboard_id"])
    if "cron_expr" in data:
        # cron 变更时重算 next_run_at
        now = datetime.now(timezone.utc)
        validate_cron_expr(data["cron_expr"], now)
        sub.cron_expr = data["cron_expr"]
        sub.next_run_at = croniter(data["cron_expr"], now).get_next(datetime)
    if "status_type" in data:
        sub.status_type = data["status_type"]

    sub.updated_by = str(user_id)
    await sub.save()
    return Success(msg="更新成功", data={"updatedId": subscription_id, "updated_id": subscription_id})


@router.delete(
    "/subscriptions/{subscription_id}",
    summary="删除订阅",
    name="bi.subscription.delete",
    dependencies=[DependAuth, require_buttons("B_BI_SUBSCRIPTION_DELETE")],
)
async def delete_subscription_endpoint(subscription_id: SqidPath):
    """删除订阅（软删）。"""
    user_id = get_current_user_id()
    sub = await BiSubscription.get_or_none(id=subscription_id, tenant_id=user_id)
    if not sub:
        raise BizError(Code.BI_SUBSCRIPTION_NOT_FOUND, "订阅不存在")
    await sub.delete()  # SoftDeleteManager 设置 deleted_at
    return Success(msg="删除成功", data={"deletedId": subscription_id, "deleted_id": subscription_id})
