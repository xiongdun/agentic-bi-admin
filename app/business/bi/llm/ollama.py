"""Ollama LLM Provider — 基于 langchain_ollama.ChatOllama（langchain_community 0.4+ 已移除 ChatOllama）。"""

from __future__ import annotations

import os
from typing import Any

from app.business.bi.llm.base import BaseLLMProvider
from app.utils import BizError


class OllamaProvider(BaseLLMProvider):
    provider_type = "ollama"

    def _create_chat_model(self) -> Any:
        # langchain_community 0.4+ 移除了 ChatOllama，迁移到独立包 langchain_ollama
        try:
            from langchain_ollama import ChatOllama  # pyright: ignore[reportMissingImports]
        except ImportError:
            try:
                from langchain_community.chat_models import ChatOllama  # type: ignore[import-not-found]
            except ImportError as e:
                raise BizError(
                    4200,
                    "Ollama Provider 不可用：需安装 langchain_ollama 或降级 langchain_community",
                ) from e

        base_url = self.provider_config.get("base_url") or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        model = self.model_config.get("name") or os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

        # cast to Any 绕过 basedpyright 存根差异
        cls: Any = ChatOllama
        return cls(
            model=model,
            base_url=base_url,
            temperature=self.model_config.get("temperature", 0.1),
        )
