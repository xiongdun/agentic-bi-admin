"""OpenAI LLM Provider — 基于 langchain_openai.ChatOpenAI."""

from __future__ import annotations

import os
from typing import Any

from app.business.bi.llm.base import BaseLLMProvider
from app.utils import BizError


class OpenAIProvider(BaseLLMProvider):
    provider_type = "openai"

    def _create_chat_model(self) -> Any:
        from langchain_openai import ChatOpenAI

        api_key = self.provider_config.get("api_key") or os.getenv("OPENAI_API_KEY")
        base_url = self.provider_config.get("base_url") or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        model = self.model_config.get("name") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        if not api_key:
            raise BizError(4200, "OpenAI API Key 未配置")

        if self.provider_config.get("api_key_encrypted"):
            from app.business.bi.security.crypto import decrypt

            api_key = decrypt(api_key)

        # cast to Any 绕过 basedpyright 对 langchain_openai 存根的误报
        # （max_tokens 实际存在，已通过 model_fields 验证）
        cls: Any = ChatOpenAI
        return cls(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=self.model_config.get("temperature", 0.1),
            max_tokens=self.model_config.get("max_tokens", 4096),
        )
