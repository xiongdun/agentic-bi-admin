"""Intent Agent — 识别用户问题的意图（table / metric / freeform）。

Phase 1 简单规则：含"指标" → metric；含"排名/排行/排序" → table；否则 freeform。
Phase 2 改 LLM。
"""

from __future__ import annotations

import time

from app.business.bi.agent.state import AgentState, StepTrace


def _rule_intent(question: str) -> str:
    if any(kw in question for kw in ("指标", "metric")):
        return "metric"
    if any(kw in question for kw in ("排名", "排行", "排序", "top", "ranking")):
        return "table"
    if any(kw in question for kw in ("趋势", "变化", "增长", "对比", "占比", "分布")):
        return "freeform"
    return "table"


async def intent_node(state: AgentState) -> AgentState:
    """识别用户意图。"""
    question = state.get("question", "")
    started = time.perf_counter()
    intent_label = _rule_intent(question)
    state["intent"] = intent_label
    state.setdefault("steps", []).append(
        StepTrace(
            node="intent",
            started_at=started,
            ended_at=time.perf_counter(),
            input={"question": question},
            output={"intent": intent_label},
        ).to_dict()
    )
    return state


__all__ = ["intent_node"]
