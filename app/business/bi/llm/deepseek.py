"""DeepSeek LLM Provider — 基于 langchain_deepseek.ChatDeepSeek."""

from __future__ import annotations

import os
from typing import Any

from app.business.bi.llm.base import BaseLLMProvider
from app.utils import BizError


class DeepSeekProvider(BaseLLMProvider):
    provider_type = "deepseek"

    def _create_chat_model(self) -> Any:
        from langchain_deepseek import ChatDeepSeek

        # 优先用 provider_config（来自数据库），否则用 .env
        api_key = self.provider_config.get("api_key") or os.getenv("DEEPSEEK_API_KEY")
        base_url = self.provider_config.get("base_url") or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        model = self.model_config.get("name") or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

        if not api_key:
            raise BizError(4200, "DeepSeek API Key 未配置")

        # 如果 api_key 是密文（来自数据库），先解密
        if self.provider_config.get("api_key_encrypted"):
            from app.business.bi.security.crypto import decrypt

            api_key = decrypt(api_key)

        # cast to Any 绕过 basedpyright 对 langchain_deepseek 存根的误报
        # （api_base / max_tokens 实际存在，已通过 model_fields 验证）
        cls: Any = ChatDeepSeek
        return cls(
            model=model,
            api_key=api_key,
            api_base=base_url,
            temperature=self.model_config.get("temperature", 0.1),
            max_tokens=self.model_config.get("max_tokens", 4096),
        )
