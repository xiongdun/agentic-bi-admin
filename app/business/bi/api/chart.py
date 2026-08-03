"""BI 图表保存路由 — CRUD + 刷新 + 分享 + 免登录查看。

按钮码：
- ``B_BI_CHART_VIEW`` —— 查看（list / get / tags）
- ``B_BI_CHART_CREATE`` —— 创建（保存图表）
- ``B_BI_CHART_EDIT`` —— 编辑
- ``B_BI_CHART_DELETE`` —— 删除（含批量）
- ``B_BI_CHART_REFRESH`` —— 刷新数据（重跑 SQL）
- ``B_BI_CHART_SHARE`` —— 开启/关闭外部分享

接口列表：
- ``POST /charts`` —— 保存图表
- ``POST /charts/search`` —— 分页查询当前用户的图表
- ``GET /charts/tags`` —— 获取当前用户图表的所有标签（自动补全）
- ``GET /charts/{chart_id}`` —— 查看图表详情
- ``PATCH /charts/{chart_id}`` —— 更新图表（名称/说明/标签等）
- ``DELETE /charts/{chart_id}`` —— 删除图表（软删）
- ``POST /charts/batch_delete`` —— 批量删除
- ``POST /charts/{chart_id}/refresh`` —— 重跑 SQL 刷新结果快照
- ``POST /charts/{chart_id}/share/enable`` —— 开启分享，返回 share_token
- ``POST /charts/{chart_id}/share/disable`` —— 关闭分享
- ``GET /charts/shared/{share_token}`` —— 免登录查看分享图表（不含 sql_text）

行级隔离：BiChart.tenant_id 字段存 user_id（与 BI 模块 chat session 一致，
BI 模块的行级 scope_id 就是 user.id）。用户只能查看/操作自己的图表。

项目历史教训：
- ``/charts/tags`` 必须声明在 ``/charts/{chart_id}`` 之前，否则 ``tags`` 会被
  当作 sqid 路径参数解析而报错
- ``build_search`` 返回 ``Q`` 对象，追加条件用 ``q &= Q(...)``
"""

from __future__ import annotations

from fastapi import APIRouter
from tortoise.expressions import Q

from app.business.bi.controllers import bi_chart_controller
from app.business.bi.models import BiChart
from app.business.bi.schemas import (
    BiChartCreateSchema,
    BiChartSearchSchema,
    BiChartSharedOutSchema,
    BiChartUpdateSchema,
)
from app.business.bi.services_chart import (
    create_chart,
    disable_share,
    enable_share,
    get_all_tags,
    get_shared_chart_by_token,
    refresh_chart,
)
from app.utils import (
    BizError,
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

# 公开路由（免登录查看分享图表）—— 单独挂载到 module.py 的 auth="public" BusinessRouter，
# 避免 /charts/shared/{token} 走 DependPermission 被拦截。
public_router = APIRouter()


def _chart_record(chart: BiChart) -> dict:
    """序列化图表为响应 dict（sqid 自动编码，datetime 转 ISO 字符串）。"""
    return {
        "id": chart.id,
        "name": chart.name,
        "description": chart.description,
        "datasource_id": chart.datasource_id,
        "chart_type": chart.chart_type,
        "x_col": chart.x_col,
        "y_col": chart.y_col,
        "sql_text": chart.sql_text,
        "result_snapshot": chart.result_snapshot,
        "tags": chart.tags,
        "is_public": chart.is_public,
        "share_token": chart.share_token,
        "snapshot_at": chart.snapshot_at.isoformat() if chart.snapshot_at else None,
        "created_at": chart.created_at.isoformat() if chart.created_at else None,
        "updated_at": chart.updated_at.isoformat() if chart.updated_at else None,
    }


@router.post(
    "/charts",
    summary="保存图表",
    name="bi.charts.create",
    dependencies=[DependAuth, require_buttons("B_BI_CHART_CREATE")],
)
async def create_chart_endpoint(obj_in: BiChartCreateSchema):
    """保存图表（来源：智能对话 / SQL 工作台）。

    - 校验数据源归属当前用户
    - 校验 SQL 走白名单（防止保存恶意 SQL）
    - 截断结果快照到 ``BI_CHART_SNAPSHOT_MAX_ROWS`` 行
    """
    user_id = get_current_user_id()
    chart = await create_chart(obj_in, tenant_id=user_id, user_id=user_id)
    sqid = encode_id(chart.id)
    return Success(msg="保存成功", data={"createdId": sqid, "created_id": sqid})


@router.post(
    "/charts/search",
    summary="查询当前用户的图表列表",
    name="bi.charts.list",
    dependencies=[DependAuth, require_buttons("B_BI_CHART_VIEW")],
)
async def list_charts_endpoint(obj_in: BiChartSearchSchema):
    """分页查询当前用户的图表（按 id 倒序）。

    支持按名称模糊搜索、标签包含匹配、数据源筛选。
    """
    user_id = get_current_user_id()
    q = bi_chart_controller.build_search(
        obj_in,
        contains_fields=["name"],
    )
    # 强制按当前用户隔离
    q &= Q(tenant_id=user_id)

    # tags 包含匹配：BiChartSearchSchema.tags 表示"包含某个标签"
    if obj_in.tags:
        q &= Q(tags__contains=obj_in.tags)

    # datasource_id 是 sqid 字符串，解码后精确过滤
    if obj_in.datasource_id:
        try:
            q &= Q(datasource_id=decode_id(obj_in.datasource_id))
        except (ValueError, TypeError):
            pass

    total, charts = await bi_chart_controller.list(
        page=obj_in.current,
        page_size=obj_in.size,
        search=q,
        order=["-id"],
    )
    records = [_chart_record(c) for c in charts]
    return SuccessExtra(data={"records": records}, total=total, current=obj_in.current, size=obj_in.size)


# 注意：/charts/tags 必须在 /charts/{chart_id} 之前声明，否则 tags 会被当作 sqid
@router.get(
    "/charts/tags",
    summary="获取图表标签列表",
    name="bi.charts.tags",
    dependencies=[DependAuth, require_buttons("B_BI_CHART_VIEW")],
)
async def list_tags_endpoint():
    """获取当前用户图表的所有标签（用于前端自动补全）。"""
    user_id = get_current_user_id()
    tags = await get_all_tags(tenant_id=user_id)
    return Success(data={"tags": tags})


@router.get(
    "/charts/{chart_id}",
    summary="查看图表详情",
    name="bi.charts.get",
    dependencies=[DependAuth, require_buttons("B_BI_CHART_VIEW")],
)
async def get_chart_endpoint(chart_id: SqidPath):
    """查看图表详情（含 sql_text / result_snapshot）。"""
    user_id = get_current_user_id()
    chart = await bi_chart_controller.get_or_none(id=chart_id, tenant_id=user_id, deleted_at__isnull=True)
    if chart is None:
        raise BizError(Code.BI_CHART_NOT_FOUND, "图表不存在")
    return Success(data=_chart_record(chart))


@router.patch(
    "/charts/{chart_id}",
    summary="更新图表",
    name="bi.charts.update",
    dependencies=[DependAuth, require_buttons("B_BI_CHART_EDIT")],
)
async def update_chart_endpoint(chart_id: SqidPath, obj_in: BiChartUpdateSchema):  # type: ignore[invalidTypeForm]
    """更新图表（名称/说明/标签/图表类型/轴字段；不允许改 sql_text/datasource_id）。"""
    user_id = get_current_user_id()
    chart = await bi_chart_controller.get_or_none(id=chart_id, tenant_id=user_id, deleted_at__isnull=True)
    if chart is None:
        raise BizError(Code.BI_CHART_NOT_FOUND, "图表不存在")

    # 只允许更新展示相关字段，sql_text / datasource_id / result_snapshot 不在此列
    allowed = {"name", "description", "chart_type", "x_col", "y_col", "tags"}
    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    update_data = {k: v for k, v in data.items() if k in allowed}
    if update_data:
        update_data["updated_by"] = str(user_id)
        await chart.update_from_dict(update_data).save()
    return Success(msg="更新成功", data={"updatedId": chart_id, "updated_id": chart_id})


@router.delete(
    "/charts/{chart_id}",
    summary="删除图表",
    name="bi.charts.delete",
    dependencies=[DependAuth, require_buttons("B_BI_CHART_DELETE")],
)
async def delete_chart_endpoint(chart_id: SqidPath):
    """删除图表（软删）。"""
    user_id = get_current_user_id()
    chart = await bi_chart_controller.get_or_none(id=chart_id, tenant_id=user_id, deleted_at__isnull=True)
    if chart is None:
        raise BizError(Code.BI_CHART_NOT_FOUND, "图表不存在")
    await chart.delete()
    return Success(msg="删除成功", data={"deletedId": chart_id, "deleted_id": chart_id})


@router.post(
    "/charts/batch_delete",
    summary="批量删除图表",
    name="bi.charts.batch_delete",
    dependencies=[DependAuth, require_buttons("B_BI_CHART_DELETE")],
)
async def batch_delete_charts_endpoint(ids: list[str]):
    """批量删除图表（软删）。ids 为 sqid 字符串列表。"""
    user_id = get_current_user_id()
    int_ids = [decode_id(i) for i in ids]
    charts = await BiChart.filter(id__in=int_ids, tenant_id=user_id, deleted_at__isnull=True)
    for c in charts:
        await c.delete()
    return Success(msg="批量删除成功", data={"deletedCount": len(charts), "deleted_count": len(charts)})


@router.post(
    "/charts/{chart_id}/refresh",
    summary="刷新图表数据",
    name="bi.charts.refresh",
    dependencies=[DependAuth, require_buttons("B_BI_CHART_REFRESH")],
)
async def refresh_chart_endpoint(chart_id: SqidPath):
    """重跑 SQL 刷新结果快照。

    - 数据源不可用时抛 ``BI_DATASOURCE_UNAVAILABLE``，前端可降级显示快照
    - 重跑走完整校验链：白名单 → 行级注入 → 执行
    """
    user_id = get_current_user_id()
    chart = await refresh_chart(chart_id, tenant_id=user_id, user_id=user_id)
    return Success(msg="刷新成功", data=_chart_record(chart))


@router.post(
    "/charts/{chart_id}/share/enable",
    summary="开启外部分享",
    name="bi.charts.share_enable",
    dependencies=[DependAuth, require_buttons("B_BI_CHART_SHARE")],
)
async def enable_share_endpoint(chart_id: SqidPath):
    """开启分享，返回 share_token（sqid 编码）。"""
    user_id = get_current_user_id()
    token = await enable_share(chart_id, tenant_id=user_id)
    return Success(msg="分享已开启", data={"shareToken": token, "share_token": token})


@router.post(
    "/charts/{chart_id}/share/disable",
    summary="关闭外部分享",
    name="bi.charts.share_disable",
    dependencies=[DependAuth, require_buttons("B_BI_CHART_SHARE")],
)
async def disable_share_endpoint(chart_id: SqidPath):
    """关闭分享，清除 share_token。"""
    user_id = get_current_user_id()
    await disable_share(chart_id, tenant_id=user_id)
    return Success(msg="分享已关闭")


@public_router.get(
    "/charts/shared/{share_token}",
    summary="免登录查看分享图表",
    name="bi.charts.shared",
)
async def view_shared_chart_endpoint(share_token: str):
    """免登录查看分享图表（不返回 sql_text，避免泄露 SQL）。

    路由挂载在 ``public_router``（``auth="public"``），不走 ``DependPermission``，
    前端分享页独立部署，无登录态。
    """
    chart = await get_shared_chart_by_token(share_token)
    data = BiChartSharedOutSchema(
        name=chart.name,
        chart_type=chart.chart_type,
        x_col=chart.x_col,
        y_col=chart.y_col,
        result_snapshot=chart.result_snapshot,
        snapshot_at=chart.snapshot_at,
    ).model_dump(mode="json")
    return Success(data=data)
