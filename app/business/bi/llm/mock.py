"""Mock LLM Provider — 开发测试兜底，不依赖外部 API。"""

from __future__ import annotations

import time

from app.business.bi.llm.base import BaseLLMProvider, ChatResult


class MockProvider(BaseLLMProvider):
    provider_type = "mock"

    # 预设响应（按关键词匹配）
    _MOCK_RESPONSES: dict[str, str] = {
        "select": "SELECT * FROM users LIMIT 100;",
        "count": "SELECT COUNT(*) AS total FROM orders;",
        "default": "SELECT 1;",
    }

    def _create_chat_model(self):
        """Mock 不需要真实 chat model。"""
        return None

    async def chat(self, prompt: str, **kwargs) -> ChatResult:
        start = time.time()
        prompt_lower = prompt.lower()

        # 简单关键词匹配
        content = self._MOCK_RESPONSES["default"]
        for keyword, response in self._MOCK_RESPONSES.items():
            if keyword in prompt_lower:
                content = response
                break

        elapsed_ms = int((time.time() - start) * 1000)
        return ChatResult(
            content=content,
            elapsed_ms=elapsed_ms,
            token_usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            raw_response=None,
        )
