"""DeepSeek 客户端 — OpenAI 兼容协议（DeepSeek 提供 OpenAI 兼容 endpoint）。

Phase 1 主推 provider：国内访问稳定、价格低、reasoning 强。
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.business.bi.llm.base import (
    BaseChatModel,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ToolCall,
    Usage,
)
from app.core.config import APP_SETTINGS
from app.core.log import log


def _to_openai_messages(messages: list[ChatMessage]) -> list[dict]:
    out: list[dict] = []
    for m in messages:
        d: dict[str, Any] = {"role": m.role, "content": m.content}
        if m.name:
            d["name"] = m.name
        if m.tool_call_id:
            d["tool_call_id"] = m.tool_call_id
        if m.tool_calls:
            d["tool_calls"] = m.tool_calls
        out.append(d)
    return out


class DeepSeekChatModel(BaseChatModel):
    """DeepSeek provider — 使用 OpenAI 兼容 HTTP 接口。

    配置：
    - ``DEEPSEEK_API_KEY``
    - ``DEEPSEEK_BASE_URL``（默认 https://api.deepseek.com）
    - ``DEEPSEEK_MODEL``（默认 deepseek-chat）
    """

    name = "deepseek"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key or getattr(APP_SETTINGS, "DEEPSEEK_API_KEY", "") or ""
        self.base_url = (base_url or getattr(APP_SETTINGS, "DEEPSEEK_BASE_URL", "") or "https://api.deepseek.com").rstrip("/")
        self.default_model = default_model or getattr(APP_SETTINGS, "DEEPSEEK_MODEL", "") or "deepseek-chat"
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _check_key(self) -> None:
        if not self.api_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY not set; cannot call DeepSeek. Set it in .env or use MockChatModel for local development.",
            )

    async def achat(self, request: ChatRequest) -> ChatResponse:
        self._check_key()
        url = f"{self.base_url}/v1/chat/completions"
        payload: dict[str, Any] = {
            "model": request.model or self.default_model,
            "messages": _to_openai_messages(request.messages),
            "temperature": request.temperature,
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens
        if request.tools:
            payload["tools"] = request.tools
        if request.stop:
            payload["stop"] = request.stop
        if request.response_format:
            payload["response_format"] = request.response_format

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        client = self._get_client()
        start = time.perf_counter()
        try:
            resp = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            log.error(f"DeepSeek request failed: {exc}")
            raise
        cost_ms = int((time.perf_counter() - start) * 1000)
        if resp.status_code >= 400:
            log.error(f"DeepSeek returned {resp.status_code}: {resp.text[:500]}")
            resp.raise_for_status()
        data = resp.json()
        return self._parse_response(data, cost_ms=cost_ms)

    @staticmethod
    def _parse_response(data: dict, *, cost_ms: int | None = None) -> ChatResponse:
        choices = data.get("choices") or []
        if not choices:
            return ChatResponse(content="", model=data.get("model", ""), finish_reason="empty")
        first = choices[0]
        message = first.get("message", {})
        content = message.get("content") or ""
        tool_calls_raw = message.get("tool_calls") or []
        tool_calls: list[ToolCall] = []
        for tc in tool_calls_raw:
            try:
                args = json.loads(tc.get("function", {}).get("arguments", "{}") or "{}")
            except (json.JSONDecodeError, TypeError):
                args = {}
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=tc.get("function", {}).get("name", ""),
                    arguments=args,
                )
            )
        usage_data = data.get("usage", {}) or {}
        usage = Usage(
            prompt_tokens=int(usage_data.get("prompt_tokens", 0)),
            completion_tokens=int(usage_data.get("completion_tokens", 0)),
            total_tokens=int(usage_data.get("total_tokens", 0)),
        )
        return ChatResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            model=data.get("model", ""),
            finish_reason=first.get("finish_reason", "stop"),
            raw=data,
        )

    async def astream(self, request: ChatRequest) -> AsyncIterator[str]:
        """流式返回（SSE chunk 拼接）。

        Yields:
            增量内容字符串。
        """
        self._check_key()
        url = f"{self.base_url}/v1/chat/completions"
        payload: dict[str, Any] = {
            "model": request.model or self.default_model,
            "messages": _to_openai_messages(request.messages),
            "temperature": request.temperature,
            "stream": True,
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens
        if request.stop:
            payload["stop"] = request.stop
        if request.response_format:
            payload["response_format"] = request.response_format

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        client = self._get_client()
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or line.startswith(":"):
                    continue
                if line.startswith("data: "):
                    payload_str = line[6:].strip()
                    if payload_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload_str)
                    except json.JSONDecodeError:
                        continue
                    for choice in chunk.get("choices", []):
                        delta = (choice.get("delta") or {}).get("content") or ""
                        if delta:
                            yield delta


__all__ = ["DeepSeekChatModel"]
