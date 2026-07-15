"""AgenticBI Pydantic schemas — LLM 提供商 / 模型管理。"""

from __future__ import annotations

from app.core.base_schema import PageQueryBase, SchemaBase, make_optional
from app.core.types import SqidPath

# ---- Provider ----


class ModelProviderCreate(SchemaBase):
    """创建提供商请求。"""

    name: str
    code: str
    type: str  # ModelProviderType value
    display_name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    extra: dict | None = None
    is_enabled: bool = True
    is_default: bool = False
    order: int = 0
    remark: str | None = None


ModelProviderUpdate = make_optional(ModelProviderCreate, "ModelProviderUpdate")


class ModelProviderOut(SchemaBase):
    """提供商响应。"""

    id: int
    name: str
    code: str
    type: str
    display_name: str | None = None
    base_url: str | None = None
    api_key_masked: str | None = None  # 脱敏后的 api_key（仅展示前 4 后 4）
    extra: dict | None = None
    is_enabled: bool
    is_default: bool
    order: int
    last_tested_at: str | None = None
    last_test_ok: bool | None = None
    status_type: str
    remark: str | None = None
    model_count: int = 0


class ModelProviderSearch(PageQueryBase):
    """提供商搜索。"""

    name: str | None = None
    code: str | None = None
    type: str | None = None
    is_enabled: bool | None = None


class ModelProviderTestResponse(SchemaBase):
    """测试连接响应。"""

    ok: bool
    error: str | None = None
    model: str | None = None  # 测试时使用的模型名（可选）


# ---- Model ----


class BiModelCreate(SchemaBase):
    """创建模型请求。"""

    provider_id: str  # 提供商主键（sqid，API 层 decode 后传入 service）
    code: str
    display_name: str | None = None
    type: str = "chat"
    context_window: int = 8192
    input_price: float | None = None
    output_price: float | None = None
    default_params: dict | None = None
    capabilities: list[str] | None = None
    is_enabled: bool = True
    is_default: bool = False
    order: int = 0
    remark: str | None = None


BiModelUpdate = make_optional(BiModelCreate, "BiModelUpdate")


class BiModelOut(SchemaBase):
    """模型响应。"""

    id: int
    provider_id: int
    provider_code: str | None = None
    provider_name: str | None = None
    code: str
    display_name: str | None = None
    type: str
    context_window: int
    input_price: float | None = None
    output_price: float | None = None
    default_params: dict | None = None
    capabilities: list[str] | None = None
    is_enabled: bool
    is_default: bool
    order: int
    status_type: str
    remark: str | None = None


class BiModelSearch(PageQueryBase):
    """模型搜索。"""

    provider_id: int | None = None
    code: str | None = None
    type: str | None = None
    is_enabled: bool | None = None


__all__ = [
    "ModelProviderCreate",
    "ModelProviderUpdate",
    "ModelProviderOut",
    "ModelProviderSearch",
    "ModelProviderTestResponse",
    "BiModelCreate",
    "BiModelUpdate",
    "BiModelOut",
    "BiModelSearch",
    "SqidPath",
]
