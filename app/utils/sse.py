"""SSE（Server-Sent Events）工具。

SSE 协议层格式化 + 通用 header。实际响应对象使用
`sse_starlette.EventSourceResponse`，业务代码自行包装异步生成器。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterable
from typing import Any

SSE_HEADERS: dict[str, str] = {
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-cache, no-transform",
    # 关闭 nginx 等代理的缓冲，否则首条事件可能被压住
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def format_sse_event(
    data: Any,
    *,
    event: str | None = None,
    event_id: str | None = None,
    retry_ms: int | None = None,
) -> str:
    """格式化单条 SSE event。

    data 接受 dict / list，自动 JSON 序列化。字符串按原文。
    """
    if isinstance(data, (dict, list, tuple)):
        data_str = json.dumps(data, ensure_ascii=False, default=str)
    else:
        data_str = str(data)

    # data 内不能有换行 → 拆成多行 data: ...
    parts: list[str] = []
    if retry_ms is not None:
        parts.append(f"retry: {retry_ms}")
    if event_id is not None:
        parts.append(f"id: {event_id}")
    if event is not None:
        parts.append(f"event: {event}")
    for line in data_str.splitlines() or [""]:
        parts.append(f"data: {line}")
    parts.append("")  # 末尾空行
    parts.append("")
    return "\n".join(parts)


def sse_keepalive_payload() -> str:
    """SSE 心跳。"""
    return ": keep-alive\n\n"


async def sse_heartbeat_wrapper(
    source: AsyncIterator[Any],
    *,
    interval_seconds: float = 15.0,
) -> AsyncIterator[Any]:
    """在 `source` 空闲时插入心跳。

    `source` yield 的是已格式化的 SSE 字符串或 `ServerSentEvent` /
    `JSONServerSentEvent` 对象;sse_starlette 都会正确处理。
    """
    import asyncio

    while True:
        try:
            msg = await asyncio.wait_for(source.__anext__(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            yield sse_keepalive_payload()
            continue
        except StopAsyncIteration:
            return
        yield msg


def sse_done_event(payload: Any | None = None) -> str:
    """约定俗成的 'DONE' 事件。"""
    if payload is None:
        return format_sse_event("[DONE]", event="done")
    return format_sse_event(payload, event="done")


__all__: Iterable[str] = (
    "SSE_HEADERS",
    "format_sse_event",
    "sse_keepalive_payload",
    "sse_heartbeat_wrapper",
    "sse_done_event",
)
