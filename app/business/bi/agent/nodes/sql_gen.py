"""SQL Gen Agent — 调用 LLM 根据 schema + question 生成 SQL。

支持：
- 直接 LLM 调用（带 system / user 消息）
- 输出在 ```sql ... ``` 中则提取
- 调用失败 / 无 key 时回退到 mock
"""

from __future__ import annotations

import re
import time

from app.business.bi.agent.prompts import (
    SCHEMA_HEADER,
    SQL_GEN_PROMPT,
    SYSTEM_BASE,
)
from app.business.bi.agent.state import AgentState, StepTrace
from app.business.bi.llm import ChatMessage, ChatRequest, get_router
from app.utils import safe_parse

_SQL_BLOCK_RE = re.compile(r"```sql\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _extract_sql(text: str) -> str | None:
    m = _SQL_BLOCK_RE.search(text)
    if m:
        return m.group(1).strip()
    # 兜底：去掉 ``` 后整段
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        return stripped.strip("`").strip()
    return None


async def sql_gen_node(state: AgentState) -> AgentState:
    """LLM 生成 SQL。"""
    started = time.perf_counter()
    question = state.get("question", "")
    schema_text = state.get("schema_text", "(no schema)")
    dialect = state.get("dialect", "sqlite")

    schema_header = SCHEMA_HEADER.format(dialect=dialect, schema_text=schema_text)
    user_prompt = SQL_GEN_PROMPT.format(schema_header=schema_header, question=question)

    messages = [
        ChatMessage(role="system", content=SYSTEM_BASE),
        ChatMessage(role="user", content=user_prompt),
    ]
    request = ChatRequest(messages=messages, temperature=0.1)

    router = get_router()
    provider = state.get("_llm_provider")  # 允许从外部覆盖
    try:
        resp = await router.achat(provider, request)
    except Exception:  # noqa: BLE001
        # 失败兜底：回退到 mock
        resp = await router.achat("mock", request)
        state["fallback_used"] = "mock"

    draft = _extract_sql(resp.content) or resp.content.strip()
    # 用 sqlglot 做一遍规范化
    parsed = safe_parse(draft, dialect)  # type: ignore[arg-type]
    if parsed is not None:
        draft = parsed.sql(dialect=dialect)  # type: ignore[arg-type]

    state["draft_sql"] = draft
    state.setdefault("steps", []).append(
        StepTrace(
            node="sql_gen",
            started_at=started,
            ended_at=time.perf_counter(),
            input={"question": question, "schema_chars": len(schema_text)},
            output={"draft_sql": draft, "raw_excerpt": resp.content[:200]},
            tokens=resp.usage.total_tokens,
        ).to_dict()
    )
    state["tokens_used"] = state.get("tokens_used", 0) + resp.usage.total_tokens
    return state


__all__ = ["sql_gen_node", "_extract_sql"]
