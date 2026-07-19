"""SQL Gen Agent — 调用 LLM 根据 schema + question 生成 SQL。

支持：
- 直接 LLM 调用（带 system / user 消息）
- 输出在 ```sql ... ``` 中则提取
- 有 metric_templates 时切换为 SQL_GEN_WITH_METRIC_USER（强约束）
- 失败时**不再 mock 兜底**，让 NoLLMProviderError / 其他异常直接上抛
"""

from __future__ import annotations

import re
import time

from app.business.bi.agent.prompts import (
    SCHEMA_HEADER,
    SQL_GEN_PROMPT,
    SQL_GEN_WITH_METRIC_USER,
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
    """LLM 生成 SQL。

    行为分支：
    - state["metric_templates"] 非空 → 使用 SQL_GEN_WITH_METRIC_USER
    - 否则使用旧 SQL_GEN_PROMPT
    - LLM 异常（包括 NoLLMProviderError）**直接上抛**,不再兜底 mock
    """
    started = time.perf_counter()
    question = state.get("question", "")
    schema_text = state.get("schema_text", "(no schema)")
    dialect = state.get("dialect", "sqlite")
    metric_templates: list[str] = list(state.get("metric_templates") or [])

    schema_header = SCHEMA_HEADER.format(dialect=dialect, schema_text=schema_text)

    if metric_templates:
        user_prompt = SQL_GEN_WITH_METRIC_USER.format(
            schema_header=schema_header,
            question=question,
            metric_count=len(metric_templates),
            metric_templates="\n".join(f"  {i + 1}. {t}" for i, t in enumerate(metric_templates)),
        )
    else:
        user_prompt = SQL_GEN_PROMPT.format(schema_header=schema_header, question=question)

    messages = [
        ChatMessage(role="system", content=SYSTEM_BASE),
        ChatMessage(role="user", content=user_prompt),
    ]
    request = ChatRequest(messages=messages, temperature=0.1)

    router = get_router()
    provider = state.get("_llm_provider")
    # NoLLMProviderError / 其他 LLM 错误直接上抛 — 由 chat.py SSE 转 error 事件
    resp = await router.achat(provider, request)

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
            input={
                "question": question,
                "schema_chars": len(schema_text),
                "metric_count": len(metric_templates),
            },
            output={"draft_sql": draft, "raw_excerpt": resp.content[:200]},
            tokens=resp.usage.total_tokens,
        ).to_dict()
    )
    state["tokens_used"] = state.get("tokens_used", 0) + resp.usage.total_tokens
    return state


__all__ = ["sql_gen_node", "_extract_sql"]
