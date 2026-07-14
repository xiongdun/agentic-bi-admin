"""LLM 抽象基类 — Protocol + 数据类。

业务侧统一依赖 ``BaseChatModel``，provider（DeepSeek / OpenAI / Ollama /
Qwen / Mock）由 ``router`` 按 ``provider`` + ``model`` 选。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(slots=True)
class ChatMessage:
    """单条对话消息。"""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict] | None = None


@dataclass(slots=True)
class ToolCall:
    """LLM 返回的工具调用请求。"""

    id: str
    name: str
    arguments: dict


@dataclass(slots=True)
class Usage:
    """Token / 成本计量。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(slots=True)
class ChatRequest:
    """LLM 调用请求。"""

    messages: list[ChatMessage]
    model: str | None = None
    temperature: float = 0.1
    max_tokens: int | None = None
    tools: list[dict] | None = None
    stop: list[str] | None = None
    response_format: dict | None = None
    timeout_seconds: float = 60.0
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class ChatResponse:
    """LLM 统一响应。"""

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    finish_reason: str = "stop"
    raw: dict | None = None


@runtime_checkable
class BaseChatModel(Protocol):
    """所有 LLM provider 必须实现 ``achat`` + ``astream``。"""

    name: str  # provider 名称（"deepseek" / "openai" / ...）
    default_model: str

    async def achat(self, request: ChatRequest) -> ChatResponse: ...

    def astream(self, request: ChatRequest) -> AsyncIterator[str]: ...


__all__ = [
    "BaseChatModel",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ToolCall",
    "Usage",
]
