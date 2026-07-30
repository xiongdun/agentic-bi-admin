"""LLM Provider 路由器 — 按 LLM_DEFAULT_PROVIDER 路由。

项目历史教训：测试路径与正式路径使用相同 fallback 逻辑
（is_default=True → order_by fallback → .env → mock），避免"测试通过但聊天 404"。
"""

from __future__ import annotations

import os

from app.business.bi.llm.base import BaseLLMProvider
from app.business.bi.llm.deepseek import DeepSeekProvider
from app.business.bi.llm.mock import MockProvider
from app.business.bi.llm.ollama import OllamaProvider
from app.business.bi.llm.openai import OpenAIProvider
from app.business.bi.llm.qwen import QwenProvider
from app.utils import BizError

# Provider 类型 -> 类映射
_PROVIDER_CLASSES: dict[str, type[BaseLLMProvider]] = {
    "deepseek": DeepSeekProvider,
    "ollama": OllamaProvider,
    "qwen": QwenProvider,
    "openai": OpenAIProvider,
    "mock": MockProvider,
}


def _build_provider_config(provider) -> dict:
    """从 BiLLMProvider 模型实例构建 provider_config（统一两条路径的构建逻辑）。"""
    return {
        "api_key": provider.api_key,
        "api_key_encrypted": True,  # 数据库存储的是密文
        "base_url": provider.base_url,
    }


def _build_model_config(provider, model) -> dict:
    """从 BiLLMProvider + BiLLMModel 构建 model_config（统一两条路径的构建逻辑）。

    temperature / max_tokens 取自 provider.extra_config（BiLLMModel 无此字段）。
    """
    if not model:
        return {}
    extra = provider.extra_config or {}
    return {
        "name": model.name,
        "max_tokens": extra.get("max_tokens", 4096),
        "temperature": extra.get("temperature", 0.1),
    }


async def _resolve_provider(provider) -> BaseLLMProvider:
    """根据 BiLLMProvider 模型实例解析出 BaseLLMProvider（统一两条路径的解析逻辑）。

    项目历史教训：测试路径与正式路径使用相同的 model 解析 fallback
    （BiLLMModel 有 order 字段，按 order, id 排序取首个 is_active=True 的模型）。
    """
    from app.business.bi.models import BiLLMModel

    # BiLLMModel 有 order 字段，按 order, id 排序
    model = await BiLLMModel.filter(provider_id=provider.id, is_active=True).order_by("order", "id").first()

    provider_config = _build_provider_config(provider)
    model_config = _build_model_config(provider, model)

    provider_cls = _PROVIDER_CLASSES.get(provider.provider_type.lower())
    if provider_cls is None:
        raise BizError(4200, f"未知的 Provider 类型: {provider.provider_type}")

    try:
        return provider_cls(provider_config=provider_config, model_config=model_config)
    except Exception as e:
        raise BizError(4200, f"Provider 初始化失败: {e}") from e


class BiLLMRouter:
    """LLM Provider 路由器。"""

    @staticmethod
    def get_default() -> BaseLLMProvider:
        """获取默认 Provider（从 .env LLM_DEFAULT_PROVIDER 读取）。

        项目历史教训：与 get_default_from_db() 的最终 fallback 使用相同逻辑。
        """
        provider_type = os.getenv("LLM_DEFAULT_PROVIDER", "deepseek").lower()

        provider_cls = _PROVIDER_CLASSES.get(provider_type)
        if provider_cls is None:
            # 未知 provider 类型，fallback 到 mock
            return MockProvider()

        try:
            return provider_cls()
        except Exception:
            # 初始化失败，fallback 到 mock（开发环境友好）
            return MockProvider()

    @staticmethod
    async def get_default_from_db() -> BaseLLMProvider:
        """从数据库获取默认 Provider（is_default=True）。

        项目历史教训：测试路径与正式路径使用相同 fallback 逻辑：
        1. 优先查 is_default=True 且 status_type=enable
        2. fallback 到 status_type=enable 按 id 排序首个
           （BiLLMProvider 无 order 字段，按 id 排序）
        3. 数据库无 Provider，fallback 到 .env 配置（get_default）
        """
        from app.business.bi.models import BiLLMProvider
        from app.utils import StatusType

        # 优先查 is_default=True（StatusType.enable.value = "1"）
        provider = await BiLLMProvider.filter(is_default=True, status_type=StatusType.enable).first()

        if provider is None:
            # 项目历史教训：order_by fallback
            # BiLLMProvider 模型无 order 字段（只有 BiLLMModel 有），按 id 排序
            provider = await BiLLMProvider.filter(status_type=StatusType.enable).order_by("id").first()

        if provider is None:
            # 数据库无 Provider，fallback 到 .env
            return BiLLMRouter.get_default()

        return await _resolve_provider(provider)

    @staticmethod
    async def get_provider_by_id(provider_id: int) -> BaseLLMProvider:
        """按 ID 获取 Provider（用于测试接口）。

        项目历史教训：与 get_default_from_db() 使用相同的 model 解析逻辑
        （_resolve_provider），避免"测试通过但聊天 404"。
        """
        from app.business.bi.models import BiLLMProvider

        provider = await BiLLMProvider.filter(id=provider_id).first()
        if provider is None:
            raise BizError(4200, f"Provider 不存在: {provider_id}")

        return await _resolve_provider(provider)
