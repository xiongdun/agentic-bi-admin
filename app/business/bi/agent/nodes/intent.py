"""意图识别节点 — LLM 识别用户意图类型 + 规则兜底。"""

from __future__ import annotations

import time
from typing import Any

from app.business.bi.agent.state import AgentState, StepTrace

# 意图关键词规则（LLM 失败时兜底）
_INTENT_RULES = {
    "count": ["多少", "几个", "数量", "count", "总数", "统计"],
    "aggregate": ["平均", "总和", "最大", "最小", "avg", "sum", "max", "min", "汇总"],
    "list": ["列表", "清单", "所有", "list", "哪些", "展示"],
    "query": ["查询", "查找", "搜索", "find", "search", "获取"],
}


def _rule_based_intent(question: str) -> str:
    """规则兜底意图识别。"""
    q_lower = question.lower()
    for intent, keywords in _INTENT_RULES.items():
        if any(kw in q_lower for kw in keywords):
            return intent
    return "query"


async def intent_node(state: AgentState) -> dict[str, Any]:
    """意图识别节点。

    LLM 识别意图类型，失败时用规则兜底。
    """
    start = time.time()
    question = state.get("question", "")

    intent_type = "query"
    token_usage = {}

    try:
        from app.business.bi.llm.router import BiLLMRouter

        provider = await BiLLMRouter.get_default_from_db()

        prompt = f"""请识别以下用户问题的意图类型，只返回一个单词：
- query: 普通查询（查找特定数据）
- count: 计数（问"多少/几个"）
- aggregate: 聚合（平均/总和/最大/最小）
- list: 列表（列出所有/清单）

用户问题: {question}

意图类型:"""

        result = await provider.chat(prompt, temperature=0)
        content = result.content.strip().lower()
        token_usage = result.token_usage

        # 提取意图类型
        for intent in ["query", "count", "aggregate", "list"]:
            if intent in content:
                intent_type = intent
                break
    except Exception:
        # LLM 失败，规则兜底
        intent_type = _rule_based_intent(question)

    elapsed_ms = int((time.time() - start) * 1000)
    step: StepTrace = {
        "node": "intent",
        "status": "success",
        "data": {"intent_type": intent_type},
        "elapsed_ms": elapsed_ms,
        "error": None,
    }

    return {
        "intent_type": intent_type,
        "steps": state.get("steps", []) + [step],
        "token_usage": token_usage,
    }
