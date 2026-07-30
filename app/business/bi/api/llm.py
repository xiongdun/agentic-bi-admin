"""BI LLM Provider / Model 管理路由 — CRUD + Provider 测试。

按钮码（统一用 ``B_BI_MODEL_PROVIDER_*``，模型 CRUD 复用 Provider 按钮码）：
- ``B_BI_MODEL_PROVIDER_VIEW`` —— 查看（list / get，含 Model）
- ``B_BI_MODEL_PROVIDER_CREATE`` —— 创建
- ``B_BI_MODEL_PROVIDER_EDIT`` —— 编辑
- ``B_BI_MODEL_PROVIDER_DELETE`` —— 删除（含批量）
- ``B_BI_MODEL_PROVIDER_TEST`` —— 测试 Provider 连接

Provider 的 ``api_key`` 在创建 / 更新时由 service 层 Fernet 加密存储；
响应中 ``api_key`` 返回脱敏占位符 ``***``。
"""

from __future__ import annotations

from fastapi import APIRouter
from tortoise.expressions import Q

from app.business.bi.controllers import bi_llm_model_controller, bi_llm_provider_controller
from app.business.bi.schemas import (
    BiLLMModelCreate,
    BiLLMModelSearch,
    BiLLMModelUpdate,
    BiLLMProviderCreate,
    BiLLMProviderSearch,
    BiLLMProviderUpdate,
)
from app.business.bi.services import (
    create_llm_provider,
    llm_provider_record,
    test_llm_provider,
    update_llm_provider,
)
from app.utils import (
    CRUDRouter,
    DependAuth,
    SearchFieldConfig,
    SqidPath,
    Success,
    SuccessExtra,
    decode_id,
    require_buttons,
)

# ---- Provider CRUD ----
provider_crud = CRUDRouter(
    prefix="/providers",
    controller=bi_llm_provider_controller,
    create_schema=BiLLMProviderCreate,
    update_schema=BiLLMProviderUpdate,
    list_schema=BiLLMProviderSearch,
    search_fields=SearchFieldConfig(
        contains_fields=["name"],
        exact_fields=["provider_type", "status_type", "is_default"],
    ),
    summary_prefix="LLM Provider",
    enable_routes={"list", "get", "create", "update", "delete", "batch_delete"},
    route_key_prefix="bi.providers",
    action_dependencies={
        "list": [require_buttons("B_BI_MODEL_PROVIDER_VIEW")],
        "get": [require_buttons("B_BI_MODEL_PROVIDER_VIEW")],
        "create": [require_buttons("B_BI_MODEL_PROVIDER_CREATE")],
        "update": [require_buttons("B_BI_MODEL_PROVIDER_EDIT")],
        "delete": [require_buttons("B_BI_MODEL_PROVIDER_DELETE")],
        "batch_delete": [require_buttons("B_BI_MODEL_PROVIDER_DELETE")],
    },
)


@provider_crud.override("list")
async def _list_providers(obj_in: BiLLMProviderSearch):
    """列出 Provider（API Key 脱敏）。"""
    q = bi_llm_provider_controller.build_search(
        obj_in,
        contains_fields=["name"],
        exact_fields=["provider_type", "status_type", "is_default"],
    )
    total, providers = await bi_llm_provider_controller.list(
        page=obj_in.current,
        page_size=obj_in.size,
        search=q,
        order=["-is_default", "-id"],
    )
    records = [await llm_provider_record(p) for p in providers]
    return SuccessExtra(data={"records": records}, total=total, current=obj_in.current, size=obj_in.size)


@provider_crud.override("get")
async def _get_provider(item_id: SqidPath):
    """查看 Provider 详情（API Key 脱敏）。"""
    provider = await bi_llm_provider_controller.get(id=item_id)
    return Success(data=await llm_provider_record(provider))


@provider_crud.override("create")
async def _create_provider(obj_in: BiLLMProviderCreate):
    """创建 Provider — 加密 API Key。"""
    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    provider = await create_llm_provider(data)
    return Success(msg="创建成功", data={"createdId": provider.id, "created_id": provider.id})


@provider_crud.override("update")
async def _update_provider(item_id: SqidPath, obj_in: BiLLMProviderUpdate):  # type: ignore[invalidTypeForm]
    """更新 Provider — 按需加密 API Key（不传则保留原密文）。"""
    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    await update_llm_provider(item_id, data)
    return Success(msg="更新成功", data={"updatedId": item_id, "updated_id": item_id})


# ---- Model CRUD ----
model_crud = CRUDRouter(
    prefix="/models",
    controller=bi_llm_model_controller,
    create_schema=BiLLMModelCreate,
    update_schema=BiLLMModelUpdate,
    list_schema=BiLLMModelSearch,
    search_fields=SearchFieldConfig(
        contains_fields=["name", "display_name"],
        exact_fields=["is_active"],
    ),
    summary_prefix="LLM 模型",
    enable_routes={"list", "get", "create", "update", "delete", "batch_delete"},
    route_key_prefix="bi.models",
    action_dependencies={
        "list": [require_buttons("B_BI_MODEL_PROVIDER_VIEW")],
        "get": [require_buttons("B_BI_MODEL_PROVIDER_VIEW")],
        "create": [require_buttons("B_BI_MODEL_PROVIDER_CREATE")],
        "update": [require_buttons("B_BI_MODEL_PROVIDER_EDIT")],
        "delete": [require_buttons("B_BI_MODEL_PROVIDER_DELETE")],
        "batch_delete": [require_buttons("B_BI_MODEL_PROVIDER_DELETE")],
    },
)


@model_crud.override("list")
async def _list_models(obj_in: BiLLMModelSearch):
    """列出 LLM 模型（``provider_id`` 为 sqid 字符串，需解码后精确匹配）。"""
    q = bi_llm_model_controller.build_search(
        obj_in,
        contains_fields=["name", "display_name"],
        exact_fields=["is_active"],
    )
    if obj_in.provider_id:
        try:
            q &= Q(provider_id=decode_id(obj_in.provider_id))
        except (ValueError, TypeError):
            pass
    total, models = await bi_llm_model_controller.list(
        page=obj_in.current,
        page_size=obj_in.size,
        search=q,
        order=["provider_id", "order", "id"],
    )
    records = [await m.to_dict() for m in models]
    return SuccessExtra(data={"records": records}, total=total, current=obj_in.current, size=obj_in.size)


@model_crud.override("create")
async def _create_model(obj_in: BiLLMModelCreate):
    """创建 LLM 模型 — ``provider_id`` 为 sqid 字符串，需解码为 int。"""
    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    if "provider_id" in data:
        data["provider_id"] = decode_id(data["provider_id"])
    obj = await bi_llm_model_controller.create(obj_in=data)
    return Success(msg="创建成功", data={"createdId": obj.id, "created_id": obj.id})


@model_crud.override("update")
async def _update_model(item_id: SqidPath, obj_in: BiLLMModelUpdate):  # type: ignore[invalidTypeForm]
    """更新 LLM 模型 — ``provider_id`` 为 sqid 字符串，需解码为 int。"""
    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    if "provider_id" in data:
        data["provider_id"] = decode_id(data["provider_id"])
    await bi_llm_model_controller.update(id=item_id, obj_in=data)
    return Success(msg="更新成功", data={"updatedId": item_id, "updated_id": item_id})


# ---- 聚合 router + 自定义 /test ----
router = APIRouter()
router.include_router(provider_crud.router)
router.include_router(model_crud.router)


@router.post(
    "/providers/{provider_id}/test",
    summary="测试 LLM Provider 连接",
    name="bi.providers.test",
    dependencies=[DependAuth, require_buttons("B_BI_MODEL_PROVIDER_TEST")],
)
async def test_provider_endpoint(provider_id: SqidPath):
    """测试 Provider 连接，发送测试 prompt 并返回响应 + 耗时。"""
    result = await test_llm_provider(provider_id)
    return Success(data=result)
