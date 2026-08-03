"""BiMaskingRule API 路由 — CRUDRouter + 缓存失效钩子。

按钮码：
- ``B_BI_MASKING_VIEW`` —— 查看（list / get）
- ``B_BI_MASKING_CREATE`` —— 创建
- ``B_BI_MASKING_EDIT`` —— 编辑
- ``B_BI_MASKING_DELETE`` —— 删除（含批量）

create / update / delete / batch_delete 后主动失效脱敏规则缓存，确保 60s TTL 内变更立即生效。
"""
from __future__ import annotations

from fastapi import APIRouter

from app.business.bi.controllers import bi_masking_rule_controller
from app.business.bi.schemas import (
    BiMaskingRuleCreate,
    BiMaskingRuleSearch,
    BiMaskingRuleUpdate,
)
from app.business.bi.services_masking import invalidate_masking_cache
from app.utils import (
    CRUDRouter,
    SearchFieldConfig,
    Success,
    require_buttons,
)

masking_crud = CRUDRouter(
    prefix="/masking",
    controller=bi_masking_rule_controller,
    create_schema=BiMaskingRuleCreate,
    update_schema=BiMaskingRuleUpdate,
    list_schema=BiMaskingRuleSearch,
    search_fields=SearchFieldConfig(
        contains_fields=["name"],
        exact_fields=["mask_type", "status_type"],
    ),
    summary_prefix="脱敏规则",
    enable_routes={"list", "get", "create", "update", "delete", "batch_delete"},
    route_key_prefix="bi.masking",
    action_dependencies={
        "list": [require_buttons("B_BI_MASKING_VIEW")],
        "get": [require_buttons("B_BI_MASKING_VIEW")],
        "create": [require_buttons("B_BI_MASKING_CREATE")],
        "update": [require_buttons("B_BI_MASKING_EDIT")],
        "delete": [require_buttons("B_BI_MASKING_DELETE")],
        "batch_delete": [require_buttons("B_BI_MASKING_DELETE")],
    },
)


@masking_crud.override("create")
async def _create_masking(obj_in: BiMaskingRuleCreate):
    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    item = await bi_masking_rule_controller.create(data)
    await invalidate_masking_cache()
    return Success(
        msg="创建成功",
        data={"createdId": item.id, "created_id": item.id},
    )


@masking_crud.override("update")
async def _update_masking(item_id: int, obj_in: BiMaskingRuleUpdate):  # type: ignore[invalidTypeForm]
    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    await bi_masking_rule_controller.update(item_id, data)
    await invalidate_masking_cache()
    return Success(msg="更新成功", data={"updatedId": item_id, "updated_id": item_id})


@masking_crud.override("delete")
async def _delete_masking(item_id: int):
    await bi_masking_rule_controller.remove(item_id)
    await invalidate_masking_cache()
    return Success(msg="删除成功")


@masking_crud.override("batch_delete")
async def _batch_delete_masking(obj_in):
    ids = obj_in.ids if hasattr(obj_in, "ids") else obj_in.get("ids", [])
    for rid in ids:
        await bi_masking_rule_controller.remove(rid)
    await invalidate_masking_cache()
    return Success(msg="批量删除成功")


router = APIRouter()
router.include_router(masking_crud.router)
