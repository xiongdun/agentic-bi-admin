"""LLM Provider 抽象基类 — 封装 langchain BaseChatModel。

所有 Provider 实现统一接口，便于 Agent 节点调用。
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.utils import BizError


@dataclass
class ChatResult:
    """LLM 调用结果。"""

    content: str
    elapsed_ms: int
    token_usage: dict[str, int | float] = field(default_factory=dict)
    raw_response: Any = None


class BaseLLMProvider(ABC):
    """LLM Provider 抽象基类。

    子类必须实现 _create_chat_model() 返回 langchain BaseChatModel 实例。
    """

    provider_type: str = "base"

    def __init__(self, provider_config: dict | None = None, model_config: dict | None = None):
        """
        Args:
            provider_config: Provider 配置（api_key / base_url 等，来自 BiLLMProvider 模型或 .env）
            model_config: 模型配置（model_name / temperature 等，来自 BiLLMModel 模型）
        """
        self.provider_config = provider_config or {}
        self.model_config = model_config or {}
        self._chat_model: Any = None

    @abstractmethod
    def _create_chat_model(self) -> Any:
        """创建 langchain BaseChatModel 实例（子类实现）。"""
        ...

    def get_chat_model(self):
        """获取 chat model（懒加载单例）。"""
        if self._chat_model is None:
            self._chat_model = self._create_chat_model()
        return self._chat_model

    async def chat(self, prompt: str, **kwargs) -> ChatResult:
        """调用 LLM 生成回复。

        Args:
            prompt: 用户提示词
            **kwargs: 额外参数（temperature / max_tokens 等）

        Returns:
            ChatResult: 调用结果

        Raises:
            BizError(4200): LLM 调用失败
        """
        start = time.time()
        try:
            from langchain_core.messages import HumanMessage

            chat_model = self.get_chat_model()

            # 应用额外参数
            if kwargs:
                # langchain chat model 支持运行时参数
                response = await chat_model.ainvoke([HumanMessage(content=prompt)], config=kwargs)
            else:
                response = await chat_model.ainvoke([HumanMessage(content=prompt)])

            content = response.content if hasattr(response, "content") else str(response)
            elapsed_ms = int((time.time() - start) * 1000)

            # 提取 token 用量（只保留顶层 int/float 值，过滤嵌套 dict
            # 如 input_token_details / output_token_details，避免节点合并时
            # 触发 dict + dict TypeError）
            token_usage: dict[str, int | float] = {}
            raw_usage: dict = {}
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                raw_usage = dict(response.usage_metadata)
            elif hasattr(response, "response_metadata") and response.response_metadata:
                meta = response.response_metadata
                if isinstance(meta, dict) and "token_usage" in meta:
                    raw_usage = dict(meta["token_usage"])
            for k, v in raw_usage.items():
                if isinstance(v, int | float):
                    token_usage[k] = v

            return ChatResult(
                content=content,
                elapsed_ms=elapsed_ms,
                token_usage=token_usage,
                raw_response=response,
            )
        except BizError:
            raise
        except Exception as e:
            raise BizError(4200, f"LLM 调用失败: {e}") from e

    async def test_connection(self) -> tuple[bool, str, int, dict]:
        """测试 Provider 连接。

        Returns:
            (success, message, elapsed_ms, token_usage)
        """
        try:
            result = await self.chat("Hello, respond with 'OK' only.")
            return True, result.content, result.elapsed_ms, result.token_usage
        except BizError as e:
            return False, str(e), 0, {}
