"""BiDashboard API 路由 — 仪表盘 CRUD + 全量刷新 + 预览。

按钮码：
- ``B_BI_DASHBOARD_VIEW`` —— 查看（list / get / refresh / preview）
- ``B_BI_DASHBOARD_CREATE`` —— 创建
- ``B_BI_DASHBOARD_EDIT`` —— 编辑
- ``B_BI_DASHBOARD_DELETE`` —— 删除（软删）

接口列表：
- ``POST /dashboards`` —— 创建仪表盘
- ``POST /dashboards/search`` —— 分页查询当前用户的仪表盘
- ``GET /dashboards/{dashboard_id}`` —— 查看仪表盘详情（含 layout）
- ``PUT /dashboards/{dashboard_id}`` —— 更新名称/说明/layout
- ``DELETE /dashboards/{dashboard_id}`` —— 删除（软删）
- ``POST /dashboards/{dashboard_id}/refresh`` —— 全量刷新所有图表数据
- ``GET /dashboards/{dashboard_id}/preview`` —— 预览（不刷新，编辑模式用）

行级隔离：所有查询带 ``tenant_id=user_id``，用户只能查看/操作自己的仪表盘。

项目历史教训：
- ``/dashboards/search`` 必须声明在 ``/dashboards/{dashboard_id}`` 之前，避免
  ``search`` 被当作 sqid 路径参数解析而报错
"""

from __future__ import annotations

from fastapi import APIRouter

from app.business.bi.models import BiDashboard
from app.business.bi.schemas_dashboard import (
    BiDashboardCreateSchema,
    BiDashboardSearchSchema,
    BiDashboardUpdateSchema,
)
from app.business.bi.services_dashboard import (
    create_dashboard,
    delete_dashboard,
    get_dashboard,
    preview_dashboard,
    refresh_dashboard,
    update_dashboard,
)
from app.utils import (
    DependAuth,
    SqidPath,
    Success,
    SuccessExtra,
    encode_id,
    get_current_user_id,
    require_buttons,
)

router = APIRouter()


def _dashboard_brief(d: BiDashboard) -> dict:
    """列表页简要信息。"""
    items = d.layout.get("items", []) if d.layout else []
    return {
        "id": encode_id(d.id),
        "name": d.name,
        "description": d.description,
        "itemCount": len(items),
        "createdAt": d.created_at.isoformat() if d.created_at else None,
        "updatedAt": d.updated_at.isoformat() if d.updated_at else None,
    }


def _dashboard_detail(d: BiDashboard) -> dict:
    """详情（含完整 layout）。"""
    return {
        "id": encode_id(d.id),
        "name": d.name,
        "description": d.description,
        "layout": d.layout,
        "tenantId": d.tenant_id,
        "createdAt": d.created_at.isoformat() if d.created_at else None,
        "updatedAt": d.updated_at.isoformat() if d.updated_at else None,
    }


@router.post(
    "/dashboards",
    summary="创建仪表盘",
    name="bi.dashboards.create",
    dependencies=[DependAuth, require_buttons("B_BI_DASHBOARD_CREATE")],
)
async def create_dashboard_endpoint(obj_in: BiDashboardCreateSchema):
    """创建仪表盘（layout 中的 chartId 会校验归属当前租户）。"""
    user_id = get_current_user_id()
    dashboard = await create_dashboard(obj_in, tenant_id=user_id, user_id=user_id)
    sqid = encode_id(dashboard.id)
    return Success(msg="创建成功", data={"createdId": sqid, "created_id": sqid})


@router.post(
    "/dashboards/search",
    summary="仪表盘分页列表",
    name="bi.dashboards.list",
    dependencies=[DependAuth, require_buttons("B_BI_DASHBOARD_VIEW")],
)
async def list_dashboards_endpoint(obj_in: BiDashboardSearchSchema):
    """分页查询当前用户的仪表盘（按 id 倒序，含图表数量）。"""
    user_id = get_current_user_id()
    qs = BiDashboard.filter(tenant_id=user_id, deleted_at__isnull=True)
    if obj_in.name:
        qs = qs.filter(name__icontains=obj_in.name)

    total = await qs.count()
    dashboards = await qs.order_by("-id").offset((obj_in.current - 1) * obj_in.size).limit(obj_in.size)
    records = [_dashboard_brief(d) for d in dashboards]
    return SuccessExtra(
        data={"records": records},
        total=total,
        current=obj_in.current,
        size=obj_in.size,
    )


@router.get(
    "/dashboards/{dashboard_id}",
    summary="仪表盘详情",
    name="bi.dashboards.get",
    dependencies=[DependAuth, require_buttons("B_BI_DASHBOARD_VIEW")],
)
async def get_dashboard_endpoint(dashboard_id: SqidPath):
    """查看仪表盘详情（含完整 layout）。"""
    user_id = get_current_user_id()
    dashboard = await get_dashboard(dashboard_id, tenant_id=user_id)
    return Success(data=_dashboard_detail(dashboard))


@router.put(
    "/dashboards/{dashboard_id}",
    summary="更新仪表盘",
    name="bi.dashboards.update",
    dependencies=[DependAuth, require_buttons("B_BI_DASHBOARD_EDIT")],
)
async def update_dashboard_endpoint(
    dashboard_id: SqidPath,
    obj_in: BiDashboardUpdateSchema,  # type: ignore[valid-type]
):
    """更新仪表盘（仅更新 schema 中显式传入的字段）。"""
    user_id = get_current_user_id()
    dashboard = await update_dashboard(dashboard_id, obj_in, tenant_id=user_id, user_id=user_id)
    sqid = encode_id(dashboard.id)
    return Success(msg="更新成功", data={"updatedId": sqid, "updated_id": sqid})


@router.delete(
    "/dashboards/{dashboard_id}",
    summary="删除仪表盘",
    name="bi.dashboards.delete",
    dependencies=[DependAuth, require_buttons("B_BI_DASHBOARD_DELETE")],
)
async def delete_dashboard_endpoint(dashboard_id: SqidPath):
    """删除仪表盘（软删）。"""
    user_id = get_current_user_id()
    await delete_dashboard(dashboard_id, tenant_id=user_id)
    return Success(msg="删除成功", data={"deletedId": dashboard_id, "deleted_id": dashboard_id})


@router.post(
    "/dashboards/{dashboard_id}/refresh",
    summary="全量刷新仪表盘图表数据",
    name="bi.dashboards.refresh",
    dependencies=[DependAuth, require_buttons("B_BI_DASHBOARD_VIEW")],
)
async def refresh_dashboard_endpoint(dashboard_id: SqidPath):
    """全量刷新仪表盘所有图表数据。

    - 并发上限 ``BI_DASHBOARD_REFRESH_CONCURRENCY``
    - 单图表超时 ``BI_DASHBOARD_REFRESH_TIMEOUT``
    - 失败不降级，返回 ``status=failed`` + ``errorMessage``
    - 引用的 BiChart 已软删时返回 ``status=deleted``
    """
    user_id = get_current_user_id()
    result = await refresh_dashboard(dashboard_id, tenant_id=user_id)
    return Success(msg="刷新完成", data=result)


@router.get(
    "/dashboards/{dashboard_id}/preview",
    summary="预览仪表盘（不刷新）",
    name="bi.dashboards.preview",
    dependencies=[DependAuth, require_buttons("B_BI_DASHBOARD_VIEW")],
)
async def preview_dashboard_endpoint(dashboard_id: SqidPath):
    """预览仪表盘（不刷新，用 BiChart 已有快照，编辑模式用）。"""
    user_id = get_current_user_id()
    result = await preview_dashboard(dashboard_id, tenant_id=user_id)
    return Success(data=result)
