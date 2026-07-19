"""Intent Node — LLM 必走,一次返回 {intent, metrics, reasoning}。

Phase 1.x 行为:
- 必走 LLM,不再用纯规则
- LLM 返回 JSON 解析失败 → 降级 "table"
- intent="metric" + metrics=[] → 降级 "table"
- 选中的 metric id 不在 DB 现有集合 → 忽略
- LLM 抛 NoLLMProviderError → 透传给上层(SSE error 事件 / 前端跳 /bi/models)
"""

from __future__ import annotations

import json
import time
from typing import Any

from app.business.bi.agent.prompts import INTENT_ROUTER_SYSTEM, INTENT_ROUTER_USER
from app.business.bi.agent.state import AgentState, StepTrace
from app.business.bi.llm import ChatMessage, ChatRequest, get_router
from app.business.bi.models.semantic import Metric
from app.core.base_model import StatusType
from app.core.log import log

_VALID_INTENTS = ("metric", "table", "freeform")


class IntentRouter:
    """LLM 意图路由 + 选 metric。"""

    def __init__(self) -> None:
        self.prompt = INTENT_ROUTER_USER
        self.system = INTENT_ROUTER_SYSTEM

    async def __call__(self, state: AgentState) -> AgentState:
        started = time.perf_counter()
        ds_id = state.get("datasource_id", 0)

        # 1) 取该 datasource 下所有 enabled metric
        metrics: list[Metric] = await Metric.filter(
            datasource_id=ds_id,
            status_type=StatusType.enable,
        ).order_by("id")

        metric_list = "\n".join(f"  - id={m.id} name={m.name} desc={m.description or ''} template=`{m.sql_template}`" for m in metrics) or "  (无)"

        # 2) LLM 调用
        router = get_router()
        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=self.system),
                ChatMessage(
                    role="user",
                    content=self.prompt.format(
                        dialect=state.get("dialect", "sqlite"),
                        schema_text=state.get("schema_text", ""),
                        metric_count=len(metrics),
                        metric_list=metric_list,
                        question=state.get("question", ""),
                    ),
                ),
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        # NoLLMProviderError 直接透传 — 由 chat.py SSE / 前端跳 /bi_models
        resp = await router.achat(state.get("_llm_provider"), request)

        # 3) 解析 + 校验
        try:
            parsed: dict[str, Any] = json.loads(resp.content)
        except (json.JSONDecodeError, TypeError):
            log.warning(f"intent LLM returned non-JSON: {str(resp.content)[:200]}")
            parsed = {"intent": "table", "metrics": [], "reasoning": "parse_failed"}

        intent = parsed.get("intent", "table")
        if intent not in _VALID_INTENTS:
            intent = "table"

        valid_ids = {m.id for m in metrics}
        chosen: list[dict[str, Any]] = []
        for c in parsed.get("metrics", []) or []:
            try:
                mid = int(c.get("id"))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            if mid in valid_ids:
                chosen.append({"id": mid, "reason": str(c.get("reason", ""))[:50]})

        # 4) 降级
        if intent == "metric" and not chosen:
            intent = "table"

        # 5) 写 state
        state["intent"] = intent
        state["metric_ids"] = [c["id"] for c in chosen]  # type: ignore[index]
        id2template = {m.id: m.sql_template for m in metrics}
        state["metric_templates"] = [id2template[mid] for mid in state["metric_ids"]]
        state.setdefault("tokens_used", 0)
        state["tokens_used"] = state["tokens_used"] + resp.usage.total_tokens  # type: ignore[operator]

        state.setdefault("steps", []).append(
            StepTrace(
                node="intent",
                started_at=started,
                ended_at=time.perf_counter(),
                input={
                    "question": state.get("question", ""),
                    "available_metrics": len(metrics),
                },
                output={
                    "intent": intent,
                    "metric_ids": state["metric_ids"],
                    "metric_names": [m.name for m in metrics if m.id in state["metric_ids"]],
                    "reasoning": str(parsed.get("reasoning", ""))[:100],
                },
                tokens=resp.usage.total_tokens,
            ).to_dict()
        )
        return state


intent_node = IntentRouter()


__all__ = ["IntentRouter", "intent_node"]
