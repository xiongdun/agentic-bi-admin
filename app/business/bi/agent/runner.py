"""Agent Runner — 把节点串成 chain，给业务 / API 层用。

执行顺序：
1. ``intent_node`` — 识别意图
2. ``sql_gen_node`` — LLM 生成 SQL
3. ``sql_validate_node`` — 白名单 / 语法校验
4. ``executor_node`` — sandbox 执行
5. ``explain_node`` — LLM 解释结果

每个节点写一条 trace 到 ``state.steps``，最后落库 ChatMessage.agent_steps_json。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.business.bi.agent.nodes.executor_node import executor_node
from app.business.bi.agent.nodes.explain import explain_node
from app.business.bi.agent.nodes.intent import intent_node
from app.business.bi.agent.nodes.sql_gen import sql_gen_node
from app.business.bi.agent.nodes.sql_validate import sql_validate_node
from app.business.bi.agent.state import AgentState


@dataclass(slots=True)
class ChatTurnResult:
    """一次 chat turn 的产物。"""

    intent: str = ""
    final_sql: str = ""
    explanation: str = ""
    columns: list[str] = field(default_factory=list)
    rows: list[list] = field(default_factory=list)
    row_count: int = 0
    cost_ms: int = 0
    tokens_used: int = 0
    error: str | None = None
    steps: list[dict] = field(default_factory=list)
    fallback_used: str | None = None


async def run_chat_turn(
    *,
    user_id: int,
    tenant_id: int,
    question: str,
    datasource_id: int,
    schema_text: str = "",
    dialect: str = "sqlite",
    session_id: int | None = None,
    llm_provider: str | None = None,
    role_code: str | None = None,
) -> ChatTurnResult:
    """执行一次完整 chat turn。"""
    state: AgentState = {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "question": question,
        "datasource_id": datasource_id,
        "session_id": session_id,
        "role_code": role_code,
        "schema_text": schema_text,
        "dialect": dialect,
        "steps": [],
        "tokens_used": 0,
    }
    if llm_provider:
        state["_llm_provider"] = llm_provider

    t0 = time.perf_counter()
    state = await intent_node(state)
    state = await sql_gen_node(state)
    state = await sql_validate_node(state)
    state = await executor_node(state)
    # 只有当执行成功才解释
    if state.get("execution_error") is None and state.get("query_result"):
        state = await explain_node(state)
    cost_ms_total = int((time.perf_counter() - t0) * 1000)

    qr = state.get("query_result") or {}
    return ChatTurnResult(
        intent=state.get("intent", ""),
        final_sql=state.get("final_sql", "") or state.get("draft_sql", ""),
        explanation=state.get("explanation", ""),
        columns=qr.get("columns", []),
        rows=qr.get("rows", []),
        row_count=qr.get("row_count", 0),
        cost_ms=qr.get("cost_ms", 0) or cost_ms_total,
        tokens_used=state.get("tokens_used", 0),
        error=state.get("execution_error"),
        steps=state.get("steps", []),
        fallback_used=state.get("fallback_used"),
    )


__all__ = ["run_chat_turn", "ChatTurnResult"]
