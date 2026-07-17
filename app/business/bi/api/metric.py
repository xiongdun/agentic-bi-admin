"""AgenticBI Metric API — CRUD + 模板校验。"""

from __future__ import annotations

from fastapi import APIRouter

from app.business.bi.schemas.semantic import (
    MetricCreate,
    MetricOut,
    MetricPageQuery,
    MetricUpdate,
)
from app.business.bi.services.metric import (
    create_metric,
    delete_metric,
    list_metrics,
    update_metric,
    validate_template,
)
from app.core.base_schema import Success, SuccessExtra
from app.core.ctx import get_current_user_id
from app.core.dependency import require_buttons
from app.core.sqids import decode_id, encode_id
from app.core.types import SqidPath

router = APIRouter(prefix="/metrics")


def _to_out(m) -> dict:
    """把 Tortoise Metric 序列化为 camelCase dict(sqid 编码)。"""
    return {
        "id": encode_id(m.id),
        "name": m.name,
        "displayName": m.display_name,
        "description": m.description,
        "sqlTemplate": m.sql_template,
        "datasourceId": encode_id(m.datasource_id) if m.datasource_id else "",
        "unit": m.unit,
        "ownerId": m.owner_id,
        "statusType": m.status_type.value if hasattr(m.status_type, "value") else str(m.status_type),
        "createdAt": m.created_at.isoformat() if getattr(m, "created_at", None) else "",
        "updatedAt": m.updated_at.isoformat() if getattr(m, "updated_at", None) else "",
    }


@router.post(
    "/search",
    name="bi.metrics.search",
    summary="搜索指标",
    dependencies=[require_buttons("B_BI_METRIC_VIEW")],
)
async def search_metrics(obj_in: MetricPageQuery) -> SuccessExtra:
    """分页搜索 metric。"""
    ds_int = decode_id(obj_in.datasource_id) if obj_in.datasource_id else None
    total, rows = await list_metrics(
        datasource_id=ds_int,
        name=obj_in.name,
        status_type=obj_in.status_type,
        page=obj_in.current,
        size=obj_in.size,
    )
    return SuccessExtra(
        data={"records": [_to_out(m) for m in rows]},
        total=total,
        current=obj_in.current,
        size=obj_in.size,
    )


@router.post(
    "",
    name="bi.metrics.create",
    summary="创建指标",
    dependencies=[require_buttons("B_BI_METRIC_MANAGE")],
)
async def create_metric_route(obj_in: MetricCreate) -> Success:
    """新建 metric。"""
    user_id = get_current_user_id()
    ds_int = decode_id(obj_in.datasource_id)
    m = await create_metric(
        name=obj_in.name,
        display_name=obj_in.display_name,
        sql_template=obj_in.sql_template,
        datasource_id=ds_int,
        owner_id=user_id,
        description=obj_in.description,
        unit=obj_in.unit,
    )
    return Success(msg="创建成功", data={"createdId": encode_id(m.id)})


@router.patch(
    "/{item_id}",
    name="bi.metrics.update",
    summary="更新指标",
    dependencies=[require_buttons("B_BI_METRIC_MANAGE")],
)
async def update_metric_route(
    item_id: SqidPath,  # type: ignore[valid-type]
    obj_in: MetricUpdate,
) -> Success:
    """更新 metric(name/datasource_id 不可改)。"""
    m = await update_metric(item_id, **obj_in.model_dump(exclude_unset=True))
    return Success(msg="更新成功", data={"updatedId": encode_id(m.id)})


@router.delete(
    "/{item_id}",
    name="bi.metrics.delete",
    summary="删除指标",
    dependencies=[require_buttons("B_BI_METRIC_MANAGE")],
)
async def delete_metric_route(item_id: SqidPath) -> Success:  # type: ignore[valid-type]
    """删除 metric。"""
    await delete_metric(item_id)
    return Success(msg="删除成功")


@router.post(
    "/{item_id}/test",
    name="bi.metrics.test",
    summary="测试指标 SQL 模板",
    dependencies=[require_buttons("B_BI_METRIC_MANAGE")],
)
async def test_metric_template_route(item_id: SqidPath) -> Success:  # type: ignore[valid-type]
    """校验 sql_template 占位符 + sqlglot 解析 + 沙箱白名单。"""
    result = await validate_template(item_id)
    return Success(data=result)


__all__ = ["router"]
