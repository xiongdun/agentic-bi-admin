"""BI 智能对话路由 — 会话 CRUD + SSE 流式发送。

按钮码：
- ``B_BI_CHAT_NEW`` —— 新建会话 / 发送消息
- ``B_BI_CHAT_DELETE`` —— 删除会话

会话按当前用户隔离（``user_id``），用户只能查看 / 删除自己的会话。

SSE 端点（``POST /chat/send``）：
- 返回 ``EventSourceResponse``，事件类型 ``step`` / ``final`` / ``error`` / ``heartbeat``
- 由 ``sse.py::bi_sse_response`` 创建响应（``ping=15``，``json.dumps`` 避免 data: 双前缀）
- Agent 流水线持久化用户消息 + assistant 消息（含错误路径，项目历史教训）
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.business.bi.models import BiChatSession
from app.business.bi.schemas import (
    BiChatMessageSearch,
    BiChatSessionCreate,
    BiChatSessionSearch,
    ChatSendSchema,
)
from app.business.bi.services import (
    delete_chat_session,
    list_session_messages,
    list_user_sessions,
    send_chat_message,
)
from app.business.bi.sse import bi_sse_response
from app.utils import (
    DependAuth,
    SqidPath,
    Success,
    SuccessExtra,
    get_current_user_id,
    require_buttons,
)

router = APIRouter()


@router.post(
    "/chat/sessions",
    summary="创建对话会话",
    name="bi.chat.create",
    dependencies=[DependAuth, require_buttons("B_BI_CHAT_NEW")],
)
async def create_session(obj_in: BiChatSessionCreate):
    """创建新的对话会话。"""
    user_id = get_current_user_id()
    session = await BiChatSession.create(
        title=obj_in.title,
        user_id=user_id,
        tenant_id=0,
    )
    return Success(msg="创建成功", data={"createdId": session.id, "created_id": session.id})


@router.post(
    "/chat/sessions/search",
    summary="查看当前用户的会话列表",
    name="bi.chat.list",
    dependencies=[DependAuth],
)
async def list_sessions(obj_in: BiChatSessionSearch):
    """列出当前用户的会话（按最后消息时间倒序）。"""
    user_id = get_current_user_id()
    total, records = await list_user_sessions(user_id, obj_in)
    return SuccessExtra(data={"records": records}, total=total, current=obj_in.current, size=obj_in.size)


@router.delete(
    "/chat/sessions/{session_id}",
    summary="删除对话会话",
    name="bi.chat.delete",
    dependencies=[DependAuth, require_buttons("B_BI_CHAT_DELETE")],
)
async def delete_session(session_id: SqidPath):
    """删除会话（级联删除消息）。仅会话创建人可删除。"""
    user_id = get_current_user_id()
    deleted_id = await delete_chat_session(session_id, user_id)
    return Success(msg="删除成功", data={"deletedId": deleted_id, "deleted_id": deleted_id})


@router.post(
    "/chat/sessions/{session_id}/messages/search",
    summary="查看会话消息列表",
    name="bi.chat.messages",
    dependencies=[DependAuth],
)
async def list_messages(session_id: SqidPath, obj_in: BiChatMessageSearch):
    """列出指定会话的消息（按时间正序）。"""
    total, records = await list_session_messages(session_id, obj_in)
    return SuccessExtra(data={"records": records}, total=total, current=obj_in.current, size=obj_in.size)


@router.post(
    "/chat/send",
    summary="发送对话消息（SSE 流式响应）",
    name="bi.chat.send",
    dependencies=[DependAuth, require_buttons("B_BI_CHAT_NEW")],
)
async def send_chat(schema: ChatSendSchema, user: Any = DependAuth):
    """发送对话消息，返回 SSE 流式响应。

    事件类型：
    - ``step`` —— Agent 单节点执行留痕
    - ``final`` —— 流水线完成的最终结果
    - ``error`` —— 流水线级或节点级错误（已持久化 assistant 失败消息）
    - ``heartbeat`` —— 心跳（由 ``ping=15`` 自动发送）

    项目历史教训：
    1. ``bi_sse_response`` 内部用 ``ServerSentEvent(data=json.dumps(...))`` 避免 data: 双前缀
    2. ``ping=15`` 由 sse_starlette 独立任务发送心跳，不干扰源生成器
    3. Agent runner 在 error 路径也会持久化 assistant 消息，避免"无结果"
    """
    return await bi_sse_response(send_chat_message(user, schema))
