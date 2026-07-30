"""BI 数据源管理路由 — CRUDRouter + /test + /sync。

按钮码：
- ``B_BI_DS_CREATE`` / ``B_BI_DS_EDIT`` / ``B_BI_DS_DELETE`` — CRUD
- ``B_BI_DS_TEST`` — 测试连接
- ``B_BI_DS_SYNC`` — 同步元数据
"""

from __future__ import annotations

from fastapi import APIRouter

from app.business.bi.controllers import bi_datasource_controller
from app.business.bi.schemas import (
    BiDatasourceCreate,
    BiDatasourceSearch,
    BiDatasourceUpdate,
)
from app.business.bi.services import (
    create_datasource,
    datasource_record,
    sync_datasource_metadata,
    test_datasource,
    update_datasource,
)
from app.utils import (
    CRUDRouter,
    DependAuth,
    SearchFieldConfig,
    SqidPath,
    Success,
    SuccessExtra,
    require_buttons,
)

# ---- CRUDRouter 生成 6 路由（list / get / create / update / delete / batch_delete）----
datasource_crud = CRUDRouter(
    prefix="/datasources",
    controller=bi_datasource_controller,
    create_schema=BiDatasourceCreate,
    update_schema=BiDatasourceUpdate,
    list_schema=BiDatasourceSearch,
    search_fields=SearchFieldConfig(
        contains_fields=["name", "host", "database"],
        exact_fields=["db_type", "status_type", "tenant_id"],
    ),
    summary_prefix="数据源",
    soft_delete=True,
    enable_routes={"list", "get", "create", "update", "delete", "batch_delete"},
    route_key_prefix="bi.datasources",
    action_dependencies={
        "create": [require_buttons("B_BI_DS_CREATE")],
        "update": [require_buttons("B_BI_DS_EDIT")],
        "delete": [require_buttons("B_BI_DS_DELETE")],
        "batch_delete": [require_buttons("B_BI_DS_DELETE")],
    },
)


# ---- override: list / get / create / update — 加密 / 脱敏钩子 ----


@datasource_crud.override("list")
async def _list_datasources(obj_in: BiDatasourceSearch):
    q = bi_datasource_controller.build_search(
        obj_in,
        contains_fields=["name", "host", "database"],
        exact_fields=["db_type", "status_type", "tenant_id"],
    )
    total, datasources = await bi_datasource_controller.list(
        page=obj_in.current,
        page_size=obj_in.size,
        search=q,
        order=["-id"],
    )
    records = [await datasource_record(ds) for ds in datasources]
    return SuccessExtra(data={"records": records}, total=total, current=obj_in.current, size=obj_in.size)


@datasource_crud.override("get")
async def _get_datasource(item_id: SqidPath):
    ds = await bi_datasource_controller.get(id=item_id)
    return Success(data=await datasource_record(ds))


@datasource_crud.override("create")
async def _create_datasource(obj_in: BiDatasourceCreate):
    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    ds = await create_datasource(data)
    return Success(
        msg="创建成功",
        data={"createdId": ds.id, "created_id": ds.id},
    )


@datasource_crud.override("update")
async def _update_datasource(item_id: SqidPath, obj_in: BiDatasourceUpdate):  # type: ignore[invalidTypeForm]
    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    await update_datasource(item_id, data)
    return Success(msg="更新成功", data={"updatedId": item_id, "updated_id": item_id})


# ---- 自定义 /test 与 /sync ----


router = APIRouter()
router.include_router(datasource_crud.router)


@router.post(
    "/datasources/{datasource_id}/test",
    summary="测试数据源连接",
    name="bi.datasources.test",
    dependencies=[DependAuth, require_buttons("B_BI_DS_TEST")],
)
async def test_datasource_endpoint(datasource_id: SqidPath):
    """测试数据源连接，返回 success/message/elapsed_ms。"""
    result = await test_datasource(datasource_id)
    return Success(data=result)


@router.post(
    "/datasources/{datasource_id}/sync",
    summary="同步数据源元数据",
    name="bi.datasources.sync",
    dependencies=[DependAuth, require_buttons("B_BI_DS_SYNC")],
)
async def sync_datasource_endpoint(datasource_id: SqidPath):
    """同步数据源元数据（表/列/索引/外键）。"""
    result = await sync_datasource_metadata(datasource_id)
    return Success(msg="同步成功", data=result)
