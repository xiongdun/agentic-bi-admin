"""SSE 事件封装 — 基于 sse_starlette。

项目历史教训：
1. 必须用 ``ServerSentEvent(data=json.dumps(...))`` 避免 ``data:`` 双前缀。
   直接传 dict 给 ``EventSourceResponse`` 会被二次格式化，导致前端收到
   ``data: data: {...}`` 这种双前缀文本，``JSON.parse`` 失败。
   注：``sse_starlette`` 早期文档提到 ``JSONServerSentEvent``，但 3.4.x 实际
   只暴露 ``ServerSentEvent``。本模块统一用 ``ServerSentEvent + json.dumps``，
   语义等价于"显式指定 data 为 JSON 字符串，不再做 dict→str 转换"。
2. 用 ``EventSourceResponse(..., ping=15)`` 而非 ``asyncio.wait_for`` 包
   ``__anext__`` —— 后者会破坏异步生成器内部状态，导致后续 ``__anext__``
   抛 ``StopAsyncIteration``。``ping=15`` 让 sse_starlette 在独立任务中
   自行发送心跳，不干扰源生成器。

事件类型：
- ``step``    —— Agent 单节点执行留痕（intent / sql_gen / sql_validate / executor / explain）
- ``final``   —— 整条流水线完成的最终结果（含 SQL / 结果集 / 解读 / token 用量）
- ``error``   —— 流水线级或节点级错误（已持久化 assistant 失败消息）
- ``heartbeat`` —— 心跳（由 ``ping=15`` 自动发送，业务层一般不主动产出）
"""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator

from sse_starlette import EventSourceResponse
from sse_starlette.event import ServerSentEvent


def create_sse_response(event_generator: AsyncGenerator[dict, None]) -> EventSourceResponse:
    """创建 SSE 响应。

    项目历史教训：用 ``ping=15`` 参数让 sse_starlette 自己发心跳，
    不要用 ``asyncio.wait_for`` 包 ``__anext__``（会破坏生成器状态）。
    """
    return EventSourceResponse(
        _to_sse_events(event_generator),
        ping=15,
    )


async def _to_sse_events(
    generator: AsyncGenerator[dict, None],
) -> AsyncGenerator[ServerSentEvent, None]:
    """将 dict 事件流转换为 ``ServerSentEvent``。

    项目历史教训：用 ``json.dumps`` 序列化 data，避免双 ``data:`` 前缀。
    ``ServerSentEvent(data=<str>, event=<type>)`` 会原样输出
    ``event: <type>\\ndata: <str>\\n\\n``，不会再做一次 dict → str 转换。
    """
    async for event in generator:
        event_type = event.get("type", "message")
        data = json.dumps(event, ensure_ascii=False, default=str)
        yield ServerSentEvent(data=data, event=event_type)


def make_event(event_type: str, **payload: Any) -> dict:
    """构造一个 SSE 事件 dict（供业务层便捷产出）。"""
    payload["type"] = event_type
    return payload


async def bi_sse_response(event_generator: AsyncGenerator[dict, None]) -> EventSourceResponse:
    """创建 BI SSE 响应（Task 22 入口）。

    与 ``create_sse_response`` 等价，BI 模块对外暴露的语义入口；后续如有 BI
    专属头部（如 ``X-BI-Stream-Id``）可在此扩展。

    Args:
        event_generator: 产出 dict 事件的异步生成器（每个 dict 含 type / data 等）

    Returns:
        ``EventSourceResponse`` with ``ping=15``
    """
    return create_sse_response(event_generator)
