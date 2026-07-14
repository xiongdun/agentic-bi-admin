"""LLM 路由 — 根据 provider / model 选择具体实现。

提供全局单例 ``get_router()``，业务侧通过 ``router.achat(provider, request)``
统一调用。生产配置从 ``APP_SETTINGS`` 读取，未配置 LLM 时自动回退到 MockChatModel。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.business.bi.llm.base import BaseChatModel, ChatRequest, ChatResponse
from app.business.bi.llm.deepseek import DeepSeekChatModel
from app.business.bi.llm.mock import MockChatModel
from app.core.config import APP_SETTINGS
from app.core.log import log


@dataclass(slots=True)
class LLMRouter:
    """多 provider 路由。

    支持：
    - register(name, model)
    - get(name) → BaseChatModel
    - achat(provider, request) / astream(provider, request)
    """

    _models: dict[str, BaseChatModel]
    default_provider: str = "mock"

    @classmethod
    def build_default(cls) -> "LLMRouter":
        """根据 APP_SETTINGS 构建默认路由器。"""
        router = cls(_models={})

        # Mock 始终可用（兜底）
        router._models["mock"] = MockChatModel()
        router.default_provider = "mock"

        # DeepSeek: 有 key 就注册
        api_key = getattr(APP_SETTINGS, "DEEPSEEK_API_KEY", "")
        if api_key:
            try:
                router._models["deepseek"] = DeepSeekChatModel(api_key=api_key)
                router.default_provider = "deepseek"
                log.info("LLM router: deepseek provider enabled")
            except Exception as exc:
                log.warning(f"LLM router: failed to init deepseek: {exc}")

        return router

    def register(self, name: str, model: BaseChatModel) -> None:
        self._models[name] = model

    def get(self, name: str | None = None) -> BaseChatModel:
        if name is None:
            name = self.default_provider
        m = self._models.get(name)
        if m is None:
            # 未找到指定 provider，回退到 mock
            log.warning(f"LLM router: provider '{name}' not registered, falling back to mock")
            return self._models["mock"]
        return m

    async def achat(self, provider: str | None, request: ChatRequest) -> ChatResponse:
        m = self.get(provider)
        return await m.achat(request)

    async def astream(self, provider: str | None, request: ChatRequest):
        m = self.get(provider)
        async for chunk in m.astream(request):
            yield chunk


_default_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    """获取全局 LLM 路由器（单例）。"""
    global _default_router
    if _default_router is None:
        _default_router = LLMRouter.build_default()
    return _default_router


def reset_router_for_testing() -> None:
    """重置单例（仅供测试）。"""
    global _default_router
    _default_router = None


__all__ = ["LLMRouter", "get_router", "reset_router_for_testing"]
