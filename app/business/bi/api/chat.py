"""AgenticBI Chat API — 会话/消息 CRUD + SSE 流式问答。

设计要点：
- 会话归属 user_id + tenant_id（取自 CTX 上下文）
- 发问题采用 SSE：每个 Agent 节点输出一行 ``step`` 事件，结束时输出 ``final``
- DB 落库：先写 user 消息，再写 assistant 消息，agent_steps_json 留痕
- 异常处理（Phase 1.x）：
  - NoLLMProviderError(code=4001) → SSE error 事件,前端跳 /bi/models
  - BizError(任意 code) → SSE error 事件,前端按 code 路由
  - 其他 Exception → SSE error 事件,code=1500
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sse_starlette.event import JSONServerSentEvent
from sse_starlette.sse import EventSourceResponse

from app.business.bi.agent.state import AgentState
from app.business.bi.llm.router import NoLLMProviderError
from app.business.bi.models import (
    BiColumn,
    BiTable,
    ChatMessage,
    ChatSession,
    MessageRole,
)
from app.business.bi.schemas.chat import (
    ChatSendRequest,
    ChatSessionCreate,
)
from app.business.bi.services.metadata_api import get_datasource_by_id
from app.core.base_schema import PageQueryBase, Success, SuccessExtra
from app.core.ctx import CTX_ROLE_CODES, CTX_USER_ID
from app.core.dependency import require_buttons
from app.core.exceptions import BizError
from app.core.log import log
from app.core.sqids import decode_id, encode_id
from app.utils import sse_heartbeat_wrapper

router = APIRouter(prefix="/chat")


# ---------- helpers ----------


def _now() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


def _user_id_or_fail() -> int:
    uid = CTX_USER_ID.get()
    if not uid:
        raise BizError(msg="unauthorized", code=401)
    return int(uid)


def _first_role_code() -> str | None:
    codes = CTX_ROLE_CODES.get() or []
    return codes[0] if codes else None


def _session_to_out(s: ChatSession) -> dict:
    return {
        "id": encode_id(s.id),
        "title": s.title,
        "datasourceId": encode_id(s.datasource_id) if s.datasource_id else None,
        "lastMessageAt": s.last_message_at.isoformat() if s.last_message_at else None,
        "statusType": s.status_type.value,
        "createdAt": s.created_at.isoformat() if s.created_at else None,
    }


def _message_to_out(m: ChatMessage) -> dict:
    return {
        "id": encode_id(m.id),
        "sessionId": encode_id(m.session_id),
        "role": m.role.value,
        "content": m.content,
        "thinking": m.thinking,
        "sql": m.sql,
        "error": m.error,
        "costMs": m.cost_ms,
        "tokensUsed": m.tokens_used,
        "agentSteps": m.agent_steps_json or [],
        "createdAt": m.created_at.isoformat() if m.created_at else None,
    }


async def _build_schema_text(datasource_id: int) -> tuple[str, str]:
    """根据 datasource_id 拉表+列，拼成给 LLM 的 schema_text 摘要。"""
    ds = await get_datasource_by_id(datasource_id)
    if ds is None:
        raise BizError(msg=f"datasource<{datasource_id}> not found", code=404)
    tables = await BiTable.filter(datasource_id=datasource_id).order_by("name")
    if not tables:
        return "(empty schema, please sync metadata first)", ds.type.value
    lines: list[str] = []
    for t in tables:
        cols = await BiColumn.filter(table_id=t.id).order_by("ordinal")
        col_strs = [c.name for c in cols]
        lines.append(f"- {t.name}({', '.join(col_strs)})")
    return "\n".join(lines), ds.type.value


def _decode_ds_id(sqid: str | None) -> int | None:
    if not sqid:
        return None
    try:
        return decode_id(sqid)
    except ValueError:
        raise BizError(msg=f"invalid datasource_id: {sqid}", code=400) from None


def _decode_session_id(sqid: str) -> int:
    try:
        return decode_id(sqid)
    except ValueError:
        raise BizError(msg=f"invalid session_id: {sqid}", code=400) from None


# ---------- session CRUD ----------


@router.post("/sessions", name="bi.chat.create", summary="创建会话")
async def create_session(obj_in: ChatSessionCreate):
    user_id = _user_id_or_fail()
    ds_id = _decode_ds_id(obj_in.datasource_id) if obj_in.datasource_id else None
    s = await ChatSession.create(
        user_id=user_id,
        tenant_id=user_id,  # 单租户演示环境：tenant 跟随 user
        title=obj_in.title or "新会话",
        dataset_id=obj_in.dataset_id,
        datasource_id=ds_id,
    )
    return Success(data=_session_to_out(s))


@router.get("/sessions", name="bi.chat.list", summary="会话列表")
async def list_sessions(obj_in: PageQueryBase = Depends()):
    """GET 列表：``PageQueryBase`` 通过 ``Depends()`` 从 query string 解析，避免 Pydantic 把它当 body 校验导致 ``必填字段缺失``。"""
    user_id = _user_id_or_fail()
    qs = ChatSession.filter(user_id=user_id, status_type="enable").order_by("-last_message_at", "-id")
    total = await qs.count()
    rows = await qs.offset((obj_in.current - 1) * obj_in.size).limit(obj_in.size)
    return SuccessExtra(
        data={"records": [_session_to_out(s) for s in rows]},
        total=total,
        current=obj_in.current,
        size=obj_in.size,
    )


@router.get("/sessions/{session_id}", name="bi.chat.detail", summary="会话详情（含消息）")
async def get_session_detail(session_id: str):
    user_id = _user_id_or_fail()
    sid = _decode_session_id(session_id)
    s = await ChatSession.filter(id=sid, user_id=user_id).first()
    if s is None:
        raise BizError(msg="session not found", code=404)
    msgs = await ChatMessage.filter(session_id=sid).order_by("id")
    return Success(
        data={
            "session": _session_to_out(s),
            "messages": [_message_to_out(m) for m in msgs],
        }
    )


@router.delete("/sessions/{session_id}", name="bi.chat.delete", summary="删除会话")
async def delete_session(session_id: str):
    user_id = _user_id_or_fail()
    sid = _decode_session_id(session_id)
    s = await ChatSession.filter(id=sid, user_id=user_id).first()
    if s is None:
        raise BizError(msg="session not found", code=404)
    await ChatMessage.filter(session_id=sid).delete()
    await ChatSession.filter(id=sid).delete()
    return Success(msg="deleted")


# ---------- send (SSE) ----------


@router.post(
    "/sessions/{session_id}/messages",
    name="bi.chat.send",
    summary="发送问题（SSE 流式）",
    dependencies=[require_buttons("B_BI_CHAT_SEND")],
)
async def send_message(session_id: str, obj_in: ChatSendRequest):
    """SSE 流：先发 user message id，再 step-by-step 流式 agent 状态，最后 final 一次性给结果。"""
    user_id = _user_id_or_fail()
    sid = _decode_session_id(session_id)
    s = await ChatSession.filter(id=sid, user_id=user_id).first()
    if s is None:
        raise BizError(msg="session not found", code=404)

    ds_id = _decode_ds_id(obj_in.datasource_id) or s.datasource_id
    if not ds_id:
        raise BizError(msg="datasource is required", code=400)

    # 先写 user message
    user_msg = await ChatMessage.create(
        session_id=sid,
        role=MessageRole.user,
        content=obj_in.question,
    )

    async def event_gen():
        schema_text, dialect = await _build_schema_text(ds_id)
        async for chunk in _event_gen_with_error_handling(
            schema_text=schema_text,
            dialect=dialect,
            ds_id=ds_id,
            sid=sid,
            user_id=user_id,
            question=obj_in.question,
            user_msg_id=user_msg.id,
        ):
            yield chunk

    return EventSourceResponse(sse_heartbeat_wrapper(event_gen(), interval_seconds=15.0))


async def _event_gen_with_error_handling(
    *,
    schema_text: str,
    dialect: str,
    ds_id: int,
    sid: int,
    user_id: int,
    question: str,
    user_msg_id: int | None = None,
) -> AsyncIterator[JSONServerSentEvent]:
    """SSE 事件流生成器 — 把 5 节点 agent chain 全部包在 try/except 里。

    异常映射：
    - NoLLMProviderError → SSE error 事件,code=4001
    - BizError           → SSE error 事件,code=<biz.code>
    - 其他 Exception     → SSE error 事件,code=1500
    """
    try:
        # 1) intent — 优先用模块级 intent_node(允许测试 monkey-patch),失败时回退到 import
        yield _sse("step", {"node": "intent", "status": "running"})
        from app.business.bi.agent.nodes.intent import intent_node as _imported_intent_node

        # 模块级 patch 优先(测试 monkey-patch 用),否则用刚 import 的最新实现
        _intent_node = globals().get("intent_node") or _imported_intent_node

        state: AgentState = {
            "user_id": user_id,
            "tenant_id": user_id,
            "question": question,
            "datasource_id": ds_id,
            "session_id": sid,
            "role_code": _first_role_code(),
            "schema_text": schema_text,
            "dialect": dialect,
            "steps": [],
            "tokens_used": 0,
        }
        t0 = time.perf_counter()
        state = await _intent_node(state)
        yield _sse("step", {"node": "intent", "status": "done", "durationMs": int((time.perf_counter() - t0) * 1000), "intent": state.get("intent")})

        # 2) sql_gen
        yield _sse("step", {"node": "sql_gen", "status": "running"})
        from app.business.bi.agent.nodes.sql_gen import sql_gen_node

        t0 = time.perf_counter()
        state = await sql_gen_node(state)
        yield _sse("step", {"node": "sql_gen", "status": "done", "durationMs": int((time.perf_counter() - t0) * 1000), "draftSql": state.get("draft_sql")})

        # 3) validate
        yield _sse("step", {"node": "validate", "status": "running"})
        from app.business.bi.agent.nodes.sql_validate import sql_validate_node

        t0 = time.perf_counter()
        state = await sql_validate_node(state)
        yield _sse("step", {"node": "validate", "status": "done", "durationMs": int((time.perf_counter() - t0) * 1000), "error": state.get("validation_error")})

        # 4) executor
        yield _sse("step", {"node": "executor", "status": "running"})
        from app.business.bi.agent.nodes.executor_node import executor_node

        t0 = time.perf_counter()
        state = await executor_node(state)
        qr = state.get("query_result") or {}
        yield _sse("step", {"node": "executor", "status": "done", "durationMs": int((time.perf_counter() - t0) * 1000), "rowCount": qr.get("row_count"), "finalSql": state.get("final_sql")})

        # 5) explain (optional)
        explanation = ""
        if state.get("execution_error") is None and state.get("query_result"):
            yield _sse("step", {"node": "explain", "status": "running"})
            from app.business.bi.agent.nodes.explain import explain_node

            t0 = time.perf_counter()
            state = await explain_node(state)
            explanation = state.get("explanation", "") or ""
            yield _sse("step", {"node": "explain", "status": "done", "durationMs": int((time.perf_counter() - t0) * 1000)})

        # 6) 落库 assistant message
        final_sql = state.get("final_sql") or state.get("draft_sql") or ""
        err = state.get("execution_error")
        assistant = await ChatMessage.create(
            session_id=sid,
            role=MessageRole.assistant,
            content=explanation or err or "已生成结果。",
            thinking=None,
            sql=final_sql or None,
            error=err,
            tokens_used=state.get("tokens_used"),
            agent_steps_json=state.get("steps") or [],
        )
        # 更新 session last_message_at + 标题（首条问题前 30 字）
        s = await ChatSession.get(id=sid)
        s.last_message_at = _now()
        if not s.title or s.title == "新会话":
            s.title = question[:30] or "新会话"
        await s.save(update_fields=["last_message_at", "title"])

        yield _sse(
            "final",
            {
                "userMessageId": encode_id(user_msg_id) if user_msg_id else "",
                "assistantMessageId": encode_id(assistant.id),
                "intent": state.get("intent"),
                "finalSql": final_sql,
                "explanation": explanation,
                "error": err,
                "columns": qr.get("columns", []),
                "rows": qr.get("rows", []),
                "rowCount": qr.get("row_count", 0),
                "costMs": qr.get("cost_ms", 0),
                "tokensUsed": state.get("tokens_used", 0),
                "steps": state.get("steps", []),
            },
        )
        yield _sse("done", "[DONE]")
    except NoLLMProviderError as exc:
        log.warning(f"chat SSE: NoLLMProviderError: {exc}")
        yield _sse("error", {"code": exc.code, "message": exc.msg})
        yield _sse("done", "[DONE]")
    except BizError as exc:
        log.warning(f"chat SSE: BizError code={exc.code}: {exc.msg}")
        yield _sse("error", {"code": exc.code, "message": exc.msg})
        yield _sse("done", "[DONE]")
    except Exception as exc:  # noqa: BLE001
        log.exception("chat SSE: unexpected error")
        yield _sse("error", {"code": 1500, "message": f"internal error: {exc}"})
        yield _sse("done", "[DONE]")


def _sse(event: str, data) -> JSONServerSentEvent:
    """生成 ``JSONServerSentEvent``,sse_starlette 会走 ``json.dumps`` 序列化 data。

    直接 yield 字符串会被 sse_starlette 当 raw data 加 ``data:`` 前缀;yield dict
    时 sse_starlette 用 ``str(data)``(单引号)非 JSON。改用 ``JSONServerSentEvent``
    才能产出 ``event: xxx\\r\\ndata: {"key": ...}`` 的标准 SSE。
    """
    if isinstance(data, (dict, list)):
        payload = data
    else:
        payload = {"text": str(data)}
    return JSONServerSentEvent(data=payload, event=event)


# 模块级 intent_node 引用 — 供测试 monkey-patch,生产代码通过局部 import 拿最新实现
try:
    from app.business.bi.agent.nodes.intent import intent_node  # noqa: F401
except Exception:  # noqa: BLE001
    pass


__all__ = ["router", "_event_gen_with_error_handling", "_sse"]
