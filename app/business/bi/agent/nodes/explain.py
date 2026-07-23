"""Explain Agent — 把 SQL + 结果翻译成人话。

Phase 1.x:
- 删除 mock 兜底：LLM 异常（包括 NoLLMProviderError）直接上抛
- final_sql 优先；否则用 draft_sql
- draft_sql + final_sql 都为空 → 短路返回,不调 LLM
"""

from __future__ import annotations

import time

from app.business.bi.agent.prompts import EXPLAIN_PROMPT
from app.business.bi.agent.state import AgentState, StepTrace
from app.business.bi.llm import ChatMessage, ChatRequest, ensure_router


async def explain_node(state: AgentState) -> AgentState:
    """LLM 生成结果解读。

    失败时**不再 mock 兜底** — 让 NoLLMProviderError / 其他异常直接上抛,
    由 ``chat.py`` SSE 转 error 事件。
    """
    started = time.perf_counter()
    question = state.get("question", "")
    final_sql = state.get("final_sql", "") or state.get("draft_sql", "")
    qr = state.get("query_result") or {}
    row_count = qr.get("row_count", 0)
    cost_ms = qr.get("cost_ms", 0)

    if not final_sql:
        state["explanation"] = ""
        return state

    user_prompt = EXPLAIN_PROMPT.format(
        question=question,
        final_sql=final_sql,
        row_count=row_count,
        cost_ms=cost_ms,
    )
    messages = [
        ChatMessage(
            role="system",
            content="你是一个数据解读助手，用简洁中文帮业务用户理解查询结果。",
        ),
        ChatMessage(role="user", content=user_prompt),
    ]
    request = ChatRequest(messages=messages, temperature=0.2)

    router = await ensure_router()
    # NoLLMProviderError / 其他 LLM 错误直接上抛
    resp = await router.achat(state.get("_llm_provider"), request)

    state["explanation"] = resp.content.strip()
    state.setdefault("steps", []).append(
        StepTrace(
            node="explain",
            started_at=started,
            ended_at=time.perf_counter(),
            input={"row_count": row_count, "cost_ms": cost_ms},
            output={"explanation": resp.content[:200]},
            tokens=resp.usage.total_tokens,
        ).to_dict()
    )
    state["tokens_used"] = state.get("tokens_used", 0) + resp.usage.total_tokens
    return state


__all__ = ["explain_node"]
