"""通义千问 LLM Provider — 基于 langchain_community.chat_models.ChatTongyi（依赖 dashscope）。"""

from __future__ import annotations

import os
from typing import Any

from app.business.bi.llm.base import BaseLLMProvider
from app.utils import BizError


class QwenProvider(BaseLLMProvider):
    provider_type = "qwen"

    def _create_chat_model(self) -> Any:
        from langchain_community.chat_models import ChatTongyi

        api_key = self.provider_config.get("api_key") or os.getenv("DASHSCOPE_API_KEY")
        model = self.model_config.get("name") or os.getenv("QWEN_MODEL", "qwen-max")

        if not api_key:
            raise BizError(4200, "DASHSCOPE_API_KEY 未配置")

        if self.provider_config.get("api_key_encrypted"):
            from app.business.bi.security.crypto import decrypt

            api_key = decrypt(api_key)

        # cast to Any 绕过 basedpyright 对 langchain_community 存根的误报
        # （dashscope_api_key 实际存在，已通过 model_fields 验证）
        # temperature 不是直接字段（model_fields 确认），通过 model_kwargs 传递
        cls: Any = ChatTongyi
        return cls(
            model=model,
            dashscope_api_key=api_key,
            model_kwargs={"temperature": self.model_config.get("temperature", 0.1)},
        )
