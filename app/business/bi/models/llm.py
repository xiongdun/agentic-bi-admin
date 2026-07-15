# pyright: reportIncompatibleVariableOverride=false
"""AgenticBI 数据模型 — LLM 子模块。

两张表：
- ``bi_model_provider``：LLM 提供商（DeepSeek / OpenAI / Anthropic / Ollama / 自定义）
- ``bi_model``：提供商下的具体模型（chat / embedding / vision）

策略：全局共享（不分租户），由 BI 管理员统一管理。``is_default`` 标志决定
router 默认值，最多 1 条为 True（业务写入时由 service 层保证互斥）。
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from tortoise import fields

from app.core.base_model import AuditMixin, BaseModel, StatusType
from app.core.fields import DelimitedListField


class ModelProviderType(str, Enum):
    """提供商协议族。

    - ``openai_compatible``：OpenAI Chat Completions 协议（DeepSeek / Qwen / 智谱 / Moonshot 等）
    - ``anthropic``：Anthropic Messages 协议
    - ``ollama``：本地 / 远端 Ollama（OpenAI 兼容子集）
    - ``mock``：内置 mock（无外部调用）
    - ``custom``：用户自定义（按 OpenAI 兼容协议 + 自定义 base_url / header）
    """

    openai_compatible = "openai_compatible"
    anthropic = "anthropic"
    ollama = "ollama"
    mock = "mock"
    custom = "custom"


# type → 默认 base_url（可被用户覆盖）
DEFAULT_BASE_URLS: dict[str, str] = {
    ModelProviderType.openai_compatible: "https://api.deepseek.com",
    ModelProviderType.anthropic: "https://api.anthropic.com",
    ModelProviderType.ollama: "http://localhost:11434",
    ModelProviderType.mock: "",
    ModelProviderType.custom: "",
}


class BiModelProvider(BaseModel, AuditMixin):
    """LLM 提供商。

    - ``code`` 全局唯一（router 注册时用的 key）
    - ``api_key`` 字段按决策明文存储；后续若要加密再迁
    - ``extra`` 放 timeout / proxy / 自定义 header
    """

    id = fields.IntField(primary_key=True, description="提供商ID")
    name = fields.CharField(max_length=100, unique=True, description="业务展示名")
    code = fields.CharField(max_length=64, unique=True, description="提供商编码（router key）")
    type = fields.CharEnumField(enum_type=ModelProviderType, default=ModelProviderType.openai_compatible, db_index=True, description="协议族")
    display_name = fields.CharField(max_length=100, null=True, blank=True, description="UI 展示名（可与 name 不同）")
    base_url = fields.CharField(max_length=500, null=True, blank=True, description="API base URL（按 type 预填可覆盖）")
    api_key = fields.CharField(max_length=2000, null=True, blank=True, description="API Key（明文）")
    extra = fields.JSONField(null=True, description="驱动特定配置（timeout / proxy / headers）")
    is_enabled = fields.BooleanField(default=True, db_index=True, description="是否启用")
    is_default = fields.BooleanField(default=False, db_index=True, description="是否为默认提供商（至多 1 条 True）")
    order = fields.IntField(default=0, description="展示顺序")
    last_tested_at = fields.DatetimeField(null=True, blank=True, description="最近一次连通测试时间")
    last_test_ok = fields.BooleanField(null=True, blank=True, description="最近一次连通测试结果")
    status_type = fields.CharEnumField(enum_type=StatusType, default=StatusType.enable, db_index=True, description="状态")
    remark = fields.CharField(max_length=500, null=True, blank=True, description="备注")

    models: fields.ReverseRelation["BiModel"]

    class Meta:
        table = "bi_model_provider"
        table_description = "BI LLM 提供商表"


class ModelType(str, Enum):
    """模型用途。"""

    chat = "chat"
    embedding = "embedding"
    vision = "vision"


class BiModel(BaseModel, AuditMixin):
    """具体模型。

    - ``(provider_id, code)`` 联合唯一
    - ``capabilities`` 存功能位字符串，用 DelimitedListField
    - ``default_params`` 存 temperature / max_tokens 等默认参数
    """

    id = fields.IntField(primary_key=True, description="模型ID")
    provider_id: int
    provider: fields.ForeignKeyRelation[BiModelProvider] = fields.ForeignKeyField(
        "app_system.BiModelProvider",
        related_name="models",
        on_delete=fields.CASCADE,
        description="所属提供商",
    )
    code = fields.CharField(max_length=100, description="模型编码（e.g. deepseek-chat）")
    display_name = fields.CharField(max_length=100, null=True, blank=True, description="展示名")
    type = fields.CharEnumField(enum_type=ModelType, default=ModelType.chat, db_index=True, description="模型用途")
    context_window = fields.IntField(default=8192, description="上下文窗口（token）")
    input_price = fields.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, description="输入价格（元/千 token）")
    output_price = fields.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, description="输出价格（元/千 token）")
    default_params = fields.JSONField(null=True, description="默认参数（如 {temperature: 0.1, max_tokens: 2048, top_p: 1.0}）")
    capabilities = DelimitedListField(max_length=500, null=True, blank=True, description="能力位（function_call,reasoning,json_mode,vision）")
    is_enabled = fields.BooleanField(default=True, db_index=True, description="是否启用")
    is_default = fields.BooleanField(default=False, db_index=True, description="是否为默认模型（至多 1 条 True）")
    order = fields.IntField(default=0, description="展示顺序")
    status_type = fields.CharEnumField(enum_type=StatusType, default=StatusType.enable, db_index=True, description="状态")
    remark = fields.CharField(max_length=500, null=True, blank=True, description="备注")

    class Meta:
        table = "bi_model"
        table_description = "BI LLM 模型表"
        unique_together = (("provider_id", "code"),)


__all__ = [
    "ModelProviderType",
    "DEFAULT_BASE_URLS",
    "BiModelProvider",
    "ModelType",
    "BiModel",
    # 兼容 Decimal 类型导出
    "Decimal",
]
