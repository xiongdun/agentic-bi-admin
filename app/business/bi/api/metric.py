"""BI 指标管理路由 — CRUD + 测试执行。

按钮码：
- ``B_BI_METRIC_VIEW`` —— 查看（list / get）
- ``B_BI_METRIC_CREATE`` —— 创建
- ``B_BI_METRIC_EDIT`` —— 编辑
- ``B_BI_METRIC_DELETE`` —— 删除（含批量）
- ``B_BI_METRIC_TEST`` —— 测试执行

指标绑定数据源 + SQL 模板（可含 ``{xxx}`` 占位符），测试时在绑定的数据源上
执行 SQL 模板并返回结果。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.business.bi.controllers import bi_metric_controller
from app.business.bi.schemas import (
    BiMetricCreate,
    BiMetricSearch,
    BiMetricUpdate,
)
from app.business.bi.services import test_metric
from app.utils import (
    CRUDRouter,
    DependAuth,
    SearchFieldConfig,
    SqidPath,
    Success,
    require_buttons,
)

metric_crud = CRUDRouter(
    prefix="/metrics",
    controller=bi_metric_controller,
    create_schema=BiMetricCreate,
    update_schema=BiMetricUpdate,
    list_schema=BiMetricSearch,
    search_fields=SearchFieldConfig(
        contains_fields=["name", "code"],
        exact_fields=["status_type"],
    ),
    summary_prefix="指标",
    enable_routes={"list", "get", "create", "update", "delete", "batch_delete"},
    route_key_prefix="bi.metrics",
    action_dependencies={
        "list": [require_buttons("B_BI_METRIC_VIEW")],
        "get": [require_buttons("B_BI_METRIC_VIEW")],
        "create": [require_buttons("B_BI_METRIC_CREATE")],
        "update": [require_buttons("B_BI_METRIC_EDIT")],
        "delete": [require_buttons("B_BI_METRIC_DELETE")],
        "batch_delete": [require_buttons("B_BI_METRIC_DELETE")],
    },
)


router = APIRouter()
router.include_router(metric_crud.router)


@router.post(
    "/metrics/{metric_id}/test",
    summary="测试指标",
    name="bi.metrics.test",
    dependencies=[DependAuth, require_buttons("B_BI_METRIC_TEST")],
)
async def test_metric_endpoint(metric_id: SqidPath):
    """测试指标 SQL 模板，在绑定的数据源上执行。"""
    result = await test_metric(metric_id)
    return Success(data=result)
