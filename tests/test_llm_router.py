"""LLM Router 单元测试。

- 验证 NoLLMProviderError 是 BizError 且 code=4001
- 验证 LLMRouter.get() 在 provider 不存在时抛 NoLLMProviderError
- 验证 LLMRouter.has_real_provider() 在没有 provider 时返回 False
- 验证 build_default() 不再默认注册 mock
"""

import pytest

from app.business.bi.llm.router import LLMRouter, NoLLMProviderError
from app.core.exceptions import BizError


def test_no_llm_provider_error_inherits_bizerror():
    """NoLLMProviderError 是 BizError，code=4001。"""
    assert issubclass(NoLLMProviderError, BizError)
    e = NoLLMProviderError(available=[], requested="nonexistent")
    assert e.code == 4001
    assert "未配置" in e.msg or "未配置" in str(e)


def test_no_llm_provider_error_carries_data():
    """NoLLMProviderError 携带 available / requested 信息。"""
    e = NoLLMProviderError(available=["deepseek"], requested="openai")
    assert e.data == {"available": ["deepseek"], "requested": "openai"}


def test_llm_router_get_raises_when_missing():
    """LLMRouter.get() 在 provider 不存在时抛 NoLLMProviderError。"""
    router = LLMRouter(_models={}, default_provider="")
    with pytest.raises(NoLLMProviderError):
        router.get("nonexistent")


def test_llm_router_get_raises_when_default_empty():
    """default_provider 为空时 get(None) 也抛 NoLLMProviderError。"""
    router = LLMRouter(_models={}, default_provider="")
    with pytest.raises(NoLLMProviderError):
        router.get(None)


def test_llm_router_has_real_provider_false_when_empty():
    router = LLMRouter(_models={}, default_provider="")
    assert router.has_real_provider() is False


def test_llm_router_has_real_provider_true_when_providers():
    """注册了 provider 后 has_real_provider 返回 True。"""
    from app.business.bi.llm.mock import MockChatModel

    router = LLMRouter(_models={}, default_provider="")
    router.register("mock", MockChatModel())
    router.default_provider = "mock"
    assert router.has_real_provider() is True


def test_build_default_does_not_register_mock():
    """build_default() 不再默认注册 mock provider。

    Phase 1.x：未配置 LLM 时必须返回 4001，不允许 mock 兜底。
    """
    router = LLMRouter.build_default()
    # 如果没配 env API key,默认是空的
    assert "mock" not in router._models
    # 没有真实 provider
    assert router.has_real_provider() is False or bool(router.default_provider)
