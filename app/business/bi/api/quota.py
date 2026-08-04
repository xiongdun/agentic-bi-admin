"""BiQuotaConfig API 路由 — CRUDRouter + 缓存失效钩子。

按钮码：
- ``B_BI_QUOTA_VIEW`` —— 查看（list / get）
- ``B_BI_QUOTA_CREATE`` —— 创建
- ``B_BI_QUOTA_EDIT`` —— 编辑
- ``B_BI_QUOTA_DELETE`` —— 删除（含批量）

create / update / delete / batch_delete 后主动失效配额配置缓存。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.business.bi.controllers import bi_quota_config_controller
from app.business.bi.schemas import (
    BiQuotaConfigCreate,
    BiQuotaConfigSearch,
    BiQuotaConfigUpdate,
)
from app.business.bi.services_quota import invalidate_quota_cache
from app.utils import (
    CRUDRouter,
    SearchFieldConfig,
    Success,
    require_buttons,
)

quota_crud = CRUDRouter(
    prefix="/quota",
    controller=bi_quota_config_controller,
    create_schema=BiQuotaConfigCreate,
    update_schema=BiQuotaConfigUpdate,
    list_schema=BiQuotaConfigSearch,
    search_fields=SearchFieldConfig(
        contains_fields=["name"],
        exact_fields=["scope_type", "status_type"],
    ),
    summary_prefix="配额配置",
    enable_routes={"list", "get", "create", "update", "delete", "batch_delete"},
    route_key_prefix="bi.quota",
    action_dependencies={
        "list": [require_buttons("B_BI_QUOTA_VIEW")],
        "get": [require_buttons("B_BI_QUOTA_VIEW")],
        "create": [require_buttons("B_BI_QUOTA_CREATE")],
        "update": [require_buttons("B_BI_QUOTA_EDIT")],
        "delete": [require_buttons("B_BI_QUOTA_DELETE")],
        "batch_delete": [require_buttons("B_BI_QUOTA_DELETE")],
    },
)


@quota_crud.override("create")
async def _create_quota(obj_in: BiQuotaConfigCreate):
    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    item = await bi_quota_config_controller.create(data)
    await invalidate_quota_cache()
    return Success(
        msg="创建成功",
        data={"createdId": item.id, "created_id": item.id},
    )


@quota_crud.override("update")
async def _update_quota(item_id: int, obj_in: BiQuotaConfigUpdate):  # type: ignore[invalidTypeForm]
    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    await bi_quota_config_controller.update(item_id, data)
    await invalidate_quota_cache()
    return Success(msg="更新成功", data={"updatedId": item_id, "updated_id": item_id})


@quota_crud.override("delete")
async def _delete_quota(item_id: int):
    await bi_quota_config_controller.remove(item_id)
    await invalidate_quota_cache()
    return Success(msg="删除成功")


@quota_crud.override("batch_delete")
async def _batch_delete_quota(obj_in):
    ids = obj_in.ids if hasattr(obj_in, "ids") else obj_in.get("ids", [])
    for rid in ids:
        await bi_quota_config_controller.remove(rid)
    await invalidate_quota_cache()
    return Success(msg="批量删除成功")


router = APIRouter()
router.include_router(quota_crud.router)
