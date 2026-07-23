"""AgenticBI LLM 模型管理 API — 提供商 / 模型 CRUD + 测试连通。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.business.bi.schemas.llm import (
    BiModelCreate,
    BiModelSearch,
    BiModelUpdate,
    ModelProviderCreate,
    ModelProviderSearch,
    ModelProviderTestResponse,
    ModelProviderUpdate,
)
from app.business.bi.services import llm_api as llm_service
from app.core.base_schema import Fail, Success, SuccessExtra
from app.core.ctx import get_current_user_id
from app.core.dependency import require_buttons
from app.core.sqids import decode_id, encode_id
from app.core.types import SqidPath

router = APIRouter(prefix="/llm")


# ==================== Provider ====================


@router.post(
    "/providers/search",
    name="bi.providers.search",
    summary="搜索 LLM 提供商",
)
async def search_providers(obj_in: ModelProviderSearch):
    """分页搜索提供商。"""
    items, total = await llm_service.search_providers(
        current=obj_in.current,
        size=obj_in.size,
        name=obj_in.name,
        code=obj_in.code,
        type_=obj_in.type,
        is_enabled=obj_in.is_enabled,
    )
    return SuccessExtra(
        data={"records": items},
        total=total,
        current=obj_in.current,
        size=obj_in.size,
    )


@router.post(
    "/providers",
    name="bi.providers.create",
    summary="创建 LLM 提供商",
    dependencies=[require_buttons("B_BI_MODEL_PROVIDER_CREATE")],
)
async def create_provider(obj_in: ModelProviderCreate, request: Request):
    """创建提供商。"""
    user_id = get_current_user_id()
    if user_id is None:
        return Fail(msg="无法识别当前用户")
    try:
        p = await llm_service.create_provider(user_id=user_id, **obj_in.model_dump())
    except ValueError as exc:
        return Fail(msg=str(exc))
    return Success(msg="创建成功", data={"createdId": encode_id(p.id)})


@router.patch(
    "/providers/{item_id}",
    name="bi.providers.update",
    summary="更新 LLM 提供商",
    dependencies=[require_buttons("B_BI_MODEL_PROVIDER_UPDATE")],
)
async def update_provider(item_id: SqidPath, obj_in: ModelProviderUpdate):  # type: ignore[valid-type]
    """更新提供商。"""
    try:
        p = await llm_service.update_provider(item_id, **obj_in.model_dump(exclude_unset=True))
    except (ValueError, Exception) as exc:  # noqa: BLE001
        return Fail(msg=str(exc))
    return Success(msg="更新成功", data={"updatedId": encode_id(p.id)})


@router.delete(
    "/providers/{item_id}",
    name="bi.providers.delete",
    summary="删除 LLM 提供商",
    dependencies=[require_buttons("B_BI_MODEL_PROVIDER_DELETE")],
)
async def delete_provider(item_id: SqidPath):  # type: ignore[valid-type]
    """删除提供商（级联 model）。"""
    try:
        await llm_service.delete_provider(item_id)
    except Exception as exc:  # noqa: BLE001
        return Fail(msg=str(exc))
    return Success(msg="删除成功")


@router.post(
    "/providers/{item_id}/test",
    name="bi.providers.test",
    summary="测试提供商连通性",
    dependencies=[require_buttons("B_BI_MODEL_PROVIDER_TEST")],
)
async def test_provider(item_id: SqidPath):  # type: ignore[valid-type]
    """轻量测试 provider 连通性。"""
    try:
        ok, error, used_model = await llm_service.test_provider_connection(item_id)
    except Exception as exc:  # noqa: BLE001
        return Fail(msg=str(exc))
    payload = ModelProviderTestResponse(ok=ok, error=error, model=used_model)
    if ok:
        return Success(msg="连通成功", data=payload.model_dump())
    return Success(data=payload.model_dump())


# ==================== Model ====================


@router.post(
    "/models/search",
    name="bi.models.search",
    summary="搜索模型",
)
async def search_models(obj_in: BiModelSearch):
    """分页搜索模型（带 provider 信息）。"""
    # provider_id 是 sqid,decode 后再传 service
    provider_pk: int | None = None
    if obj_in.provider_id:
        try:
            provider_pk = decode_id(obj_in.provider_id)
        except (ValueError, TypeError):
            return Fail(msg=f"providerId 无效: {obj_in.provider_id!r}")
    items, total = await llm_service.search_models(
        current=obj_in.current,
        size=obj_in.size,
        provider_id=provider_pk,
        code=obj_in.code,
        type_=obj_in.type,
        is_enabled=obj_in.is_enabled,
    )
    return SuccessExtra(
        data={"records": items},
        total=total,
        current=obj_in.current,
        size=obj_in.size,
    )


@router.post(
    "/models",
    name="bi.models.create",
    summary="创建模型",
    dependencies=[require_buttons("B_BI_MODEL_CREATE")],
)
async def create_model(obj_in: BiModelCreate, request: Request):
    """创建模型。"""
    user_id = get_current_user_id()
    if user_id is None:
        return Fail(msg="无法识别当前用户")
    try:
        provider_pk = decode_id(obj_in.provider_id)
    except (ValueError, TypeError) as exc:
        return Fail(msg=f"provider_id 无效: {exc}")
    try:
        m = await llm_service.create_model(
            user_id=user_id,
            provider_id=provider_pk,
            code=obj_in.code,
            display_name=obj_in.display_name,
            type=obj_in.type,
            context_window=obj_in.context_window,
            input_price=obj_in.input_price,
            output_price=obj_in.output_price,
            default_params=obj_in.default_params,
            capabilities=obj_in.capabilities,
            is_enabled=obj_in.is_enabled,
            is_default=obj_in.is_default,
            order=obj_in.order,
            remark=obj_in.remark,
        )
    except ValueError as exc:
        return Fail(msg=str(exc))
    return Success(msg="创建成功", data={"createdId": encode_id(m.id)})


@router.patch(
    "/models/{item_id}",
    name="bi.models.update",
    summary="更新模型",
    dependencies=[require_buttons("B_BI_MODEL_UPDATE")],
)
async def update_model(item_id: SqidPath, obj_in: BiModelUpdate):  # type: ignore[valid-type]
    """更新模型。"""
    fields = obj_in.model_dump(exclude_unset=True)
    if "provider_id" in fields:
        try:
            fields["provider_id"] = decode_id(fields["provider_id"])
        except (ValueError, TypeError) as exc:
            return Fail(msg=f"provider_id 无效: {exc}")
    try:
        m = await llm_service.update_model(item_id, **fields)
    except Exception as exc:  # noqa: BLE001
        return Fail(msg=str(exc))
    return Success(msg="更新成功", data={"updatedId": encode_id(m.id)})


@router.delete(
    "/models/{item_id}",
    name="bi.models.delete",
    summary="删除模型",
    dependencies=[require_buttons("B_BI_MODEL_DELETE")],
)
async def delete_model(item_id: SqidPath):  # type: ignore[valid-type]
    """删除模型。"""
    try:
        await llm_service.delete_model(item_id)
    except Exception as exc:  # noqa: BLE001
        return Fail(msg=str(exc))
    return Success(msg="删除成功")
