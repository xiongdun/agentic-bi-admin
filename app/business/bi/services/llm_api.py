"""LLM 提供商 / 模型 service — CRUD + 默认值切换 + 测试连通。

业务规则：
- provider.code 全局唯一；model.(provider_id, code) 联合唯一
- ``is_default`` 至多 1 条 True（service 层在事务内切换）
- 删除 provider 时级联 model
- ``is_default`` 切换不级联：用户可单独切换 provider/model 的默认
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
from tortoise.exceptions import DoesNotExist
from tortoise.queryset import QuerySet
from tortoise.transactions import in_transaction

from app.business.bi.llm.router import refresh_router
from app.business.bi.models import (
    DEFAULT_BASE_URLS,
    BiModel,
    BiModelProvider,
    ModelProviderType,
)
from app.core.sqids import encode_id

# ---------- helpers ----------


async def _refresh_llm_router() -> None:
    """provider / model 变更后同步刷新 router。失败不抛业务异常。"""
    try:
        await refresh_router()
    except Exception:  # noqa: BLE001
        # 路由刷新失败不应阻塞 DB 写入；启动时也会自动 reload
        pass


def _now_naive() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


def _mask_api_key(api_key: str | None) -> str | None:
    """脱敏：保留前 4 后 4，中间用 **** 替代。"""
    if not api_key:
        return None
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}{'*' * (len(api_key) - 8)}{api_key[-4:]}"


def _provider_to_dict(p: BiModelProvider, *, model_count: int = 0, mask_key: bool = True) -> dict:
    return {
        "id": encode_id(p.id),
        "name": p.name,
        "code": p.code,
        "type": p.type.value if hasattr(p.type, "value") else str(p.type),
        "displayName": p.display_name,
        "baseUrl": p.base_url,
        "apiKeyMasked": _mask_api_key(p.api_key) if mask_key else p.api_key,
        "extra": p.extra,
        "isEnabled": p.is_enabled,
        "isDefault": p.is_default,
        "order": p.order,
        "lastTestedAt": p.last_tested_at.isoformat() if p.last_tested_at else None,
        "lastTestOk": p.last_test_ok,
        "statusType": p.status_type.value if hasattr(p.status_type, "value") else str(p.status_type),
        "remark": p.remark,
        "modelCount": model_count,
    }


def _model_to_dict(m: BiModel, *, provider: BiModelProvider | None = None) -> dict:
    caps = m.capabilities
    if caps is None:
        capabilities: list[str] = []
    elif isinstance(caps, list):
        capabilities = [str(c) for c in caps if c]
    elif isinstance(caps, str):
        # 兼容历史数据：DB 中可能存了带 '|' 分隔符的字符串（DelimitedListField）
        # 也可能存了带 ',' 分隔符的字符串（早期版本）
        if caps.startswith("|") and caps.endswith("|"):
            capabilities = [c for c in caps.strip("|").split("|") if c]
        else:
            capabilities = [c for c in caps.split(",") if c]
    else:
        capabilities = []
    return {
        "id": encode_id(m.id),
        "providerId": encode_id(m.provider_id),
        "providerCode": provider.code if provider else None,
        "providerName": provider.name if provider else None,
        "code": m.code,
        "displayName": m.display_name,
        "type": m.type.value if hasattr(m.type, "value") else str(m.type),
        "contextWindow": m.context_window,
        "inputPrice": float(m.input_price) if m.input_price is not None else None,
        "outputPrice": float(m.output_price) if m.output_price is not None else None,
        "defaultParams": m.default_params,
        "capabilities": capabilities,
        "isEnabled": m.is_enabled,
        "isDefault": m.is_default,
        "order": m.order,
        "statusType": m.status_type.value if hasattr(m.status_type, "value") else str(m.status_type),
        "remark": m.remark,
    }


# ---------- provider ----------


def list_providers(
    *,
    name: str | None = None,
    code: str | None = None,
    type_: str | None = None,
    is_enabled: bool | None = None,
) -> QuerySet[BiModelProvider]:
    qs = BiModelProvider.all()
    if name:
        qs = qs.filter(name__icontains=name)
    if code:
        qs = qs.filter(code__icontains=code)
    if type_:
        qs = qs.filter(type=ModelProviderType(type_))
    if is_enabled is not None:
        qs = qs.filter(is_enabled=is_enabled)
    return qs.order_by("order", "-id")


async def search_providers(
    *,
    current: int,
    size: int,
    name: str | None = None,
    code: str | None = None,
    type_: str | None = None,
    is_enabled: bool | None = None,
) -> tuple[list[dict], int]:
    qs = list_providers(name=name, code=code, type_=type_, is_enabled=is_enabled)
    total = await qs.count()
    items: list[BiModelProvider] = await qs.offset((current - 1) * size).limit(size)
    # 计算每个 provider 下的 model 数（朴素 N+1，量少可接受）
    counts: dict[int, int] = {}
    for p in items:
        counts[p.id] = await BiModel.filter(provider_id=p.id).count()
    out = [_provider_to_dict(p, model_count=counts.get(p.id, 0)) for p in items]
    return out, total


async def get_provider(provider_id: int) -> BiModelProvider | None:
    return await BiModelProvider.filter(id=provider_id).first()


async def create_provider(
    *,
    user_id: int,
    name: str,
    code: str,
    type: str,
    display_name: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    extra: dict | None = None,
    is_enabled: bool = True,
    is_default: bool = False,
    order: int = 0,
    remark: str | None = None,
) -> BiModelProvider:
    # type 校验
    pt = ModelProviderType(type)
    # base_url 缺省时按 type 预填
    if not base_url and pt in DEFAULT_BASE_URLS:
        base_url = DEFAULT_BASE_URLS[pt] or None
    # 校验 code 唯一
    if await BiModelProvider.filter(code=code).exists():
        raise ValueError(f"code '{code}' 已存在")
    if await BiModelProvider.filter(name=name).exists():
        raise ValueError(f"name '{name}' 已存在")
    async with in_transaction():
        if is_default:
            await BiModelProvider.filter(is_default=True).update(is_default=False)
        p = await BiModelProvider.create(
            name=name,
            code=code,
            type=pt,
            display_name=display_name,
            base_url=base_url,
            api_key=api_key,
            extra=extra,
            is_enabled=is_enabled,
            is_default=is_default,
            order=order,
            remark=remark,
            created_by=user_id,
            updated_by=user_id,
        )
    await _refresh_llm_router()
    return p


async def update_provider(provider_id: int, **fields: Any) -> BiModelProvider:
    """按 id 更新 provider 字段。

    - ``type`` 为字符串时转换为 enum
    - ``is_default`` 切换为 True 时，事务内把其他 True 改 False
    """
    p = await get_provider(provider_id)
    if p is None:
        raise DoesNotExist(f"BiModelProvider<{provider_id}> not found")
    if "type" in fields and isinstance(fields["type"], str):
        fields["type"] = ModelProviderType(fields["type"])
    async with in_transaction():
        if fields.get("is_default") is True:
            await BiModelProvider.filter(is_default=True).exclude(id=provider_id).update(is_default=False)
        # 空字符串视作 None（前端清空时）
        for k, v in list(fields.items()):
            if v == "":
                fields[k] = None
        for k, v in fields.items():
            setattr(p, k, v)
        await p.save()
    await _refresh_llm_router()
    return p


async def delete_provider(provider_id: int) -> None:
    p = await get_provider(provider_id)
    if p is None:
        return
    await p.delete()  # on_delete=CASCADE 自动清掉关联 model
    await _refresh_llm_router()


# ---------- model ----------


def list_models(
    *,
    provider_id: int | None = None,
    code: str | None = None,
    type_: str | None = None,
    is_enabled: bool | None = None,
) -> QuerySet[BiModel]:
    qs = BiModel.all().prefetch_related("provider")
    if provider_id is not None:
        qs = qs.filter(provider_id=provider_id)
    if code:
        qs = qs.filter(code__icontains=code)
    if type_:
        qs = qs.filter(type=type_)
    if is_enabled is not None:
        qs = qs.filter(is_enabled=is_enabled)
    return qs.order_by("order", "-id")


async def search_models(
    *,
    current: int,
    size: int,
    provider_id: int | None = None,
    code: str | None = None,
    type_: str | None = None,
    is_enabled: bool | None = None,
) -> tuple[list[dict], int]:
    qs = list_models(provider_id=provider_id, code=code, type_=type_, is_enabled=is_enabled)
    total = await qs.count()
    items: list[BiModel] = await qs.offset((current - 1) * size).limit(size)
    out = [_model_to_dict(m, provider=m.provider) for m in items]
    return out, total


async def get_model(model_id: int) -> BiModel | None:
    return await BiModel.filter(id=model_id).first().prefetch_related("provider")


async def create_model(
    *,
    user_id: int,
    provider_id: int,
    code: str,
    display_name: str | None = None,
    type: str = "chat",
    context_window: int = 8192,
    input_price: float | None = None,
    output_price: float | None = None,
    default_params: dict | None = None,
    capabilities: list[str] | None = None,
    is_enabled: bool = True,
    is_default: bool = False,
    order: int = 0,
    remark: str | None = None,
) -> BiModel:
    # 校验 provider 存在
    if await BiModelProvider.filter(id=provider_id).first() is None:
        raise ValueError(f"BiModelProvider<{provider_id}> not found")
    # 校验 (provider_id, code) 唯一
    if await BiModel.filter(provider_id=provider_id, code=code).exists():
        raise ValueError(f"provider={provider_id} 下 code '{code}' 已存在")
    # 规范化 capabilities：去空、去前后空白、None 视作空列表
    caps_list: list[str] = []
    if capabilities:
        caps_list = [str(c).strip() for c in capabilities if str(c).strip()]
    async with in_transaction():
        if is_default:
            await BiModel.filter(is_default=True).update(is_default=False)
        m = await BiModel.create(
            provider_id=provider_id,
            code=code,
            display_name=display_name,
            type=type,
            context_window=context_window,
            input_price=input_price,
            output_price=output_price,
            default_params=default_params,
            capabilities=caps_list or None,  # DelimitedListField 自动转 '|a|b|'
            is_enabled=is_enabled,
            is_default=is_default,
            order=order,
            remark=remark,
            created_by=user_id,
            updated_by=user_id,
        )
    await _refresh_llm_router()
    return m


async def update_model(model_id: int, **fields: Any) -> BiModel:
    m = await get_model(model_id)
    if m is None:
        raise DoesNotExist(f"BiModel<{model_id}> not found")
    if "capabilities" in fields:
        v = fields["capabilities"]
        if v is None:
            fields["capabilities"] = None
        elif isinstance(v, list):
            fields["capabilities"] = [str(c).strip() for c in v if str(c).strip()] or None
    async with in_transaction():
        if fields.get("is_default") is True:
            await BiModel.filter(is_default=True).exclude(id=model_id).update(is_default=False)
        for k, v in list(fields.items()):
            if v == "":
                fields[k] = None
        for k, v in fields.items():
            setattr(m, k, v)
        await m.save()
    await _refresh_llm_router()
    return m


async def delete_model(model_id: int) -> None:
    m = await get_model(model_id)
    if m is None:
        return
    await m.delete()
    await _refresh_llm_router()


async def get_default_model() -> BiModel | None:
    """取 is_default=True 的模型（连同 provider）。"""
    return await BiModel.filter(is_default=True, is_enabled=True).prefetch_related("provider").first()


# ---------- test connection ----------


async def test_provider_connection(provider_id: int) -> tuple[bool, str | None, str | None]:
    """轻量测试 provider 连通性。优先取 provider 的 is_default=True 的 model 来发请求。

    返回 (ok, error, model_code_used)。
    """
    p = await get_provider(provider_id)
    if p is None:
        return False, f"BiModelProvider<{provider_id}> not found", None
    if p.type == ModelProviderType.mock:
        await _update_test_status(p, ok=True)
        return True, None, None
    # 找一个能用的 model
    m = await BiModel.filter(provider_id=p.id, is_enabled=True).order_by("-is_default", "order").first()
    model_code = m.code if m else None
    # 用一个最小的 chat 请求来探测
    if not p.base_url:
        await _update_test_status(p, ok=False)
        return False, "base_url 为空", model_code
    if not p.api_key and p.type != ModelProviderType.ollama:
        await _update_test_status(p, ok=False)
        return False, "api_key 为空", model_code
    url = p.base_url.rstrip("/") + "/v1/models"  # OpenAI 兼容: /v1/models, 多数厂商都支持
    headers = {"Authorization": f"Bearer {p.api_key}"} if p.api_key else {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code < 400:
            await _update_test_status(p, ok=True)
            return True, None, model_code
        await _update_test_status(p, ok=False)
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}", model_code
    except Exception as exc:  # noqa: BLE001
        await _update_test_status(p, ok=False)
        return False, f"{type(exc).__name__}: {exc}", model_code


async def _update_test_status(p: BiModelProvider, *, ok: bool) -> None:
    p.last_tested_at = _now_naive()
    p.last_test_ok = ok
    await p.save(update_fields=["last_tested_at", "last_test_ok"])


__all__ = [
    "list_providers",
    "search_providers",
    "get_provider",
    "create_provider",
    "update_provider",
    "delete_provider",
    "list_models",
    "search_models",
    "get_model",
    "create_model",
    "update_model",
    "delete_model",
    "get_default_model",
    "test_provider_connection",
]
