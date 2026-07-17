"""SQL Gen (LLM with metric template) 单元测试。

- 有 metric_templates 时使用 SQL_GEN_WITH_METRIC_USER
- 无 metric_templates 时回退到 SQL_GEN_PROMPT
- LLM 抛 NoLLMProviderError 直接透传(不再 mock 兜底)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.business.bi.agent.nodes.sql_gen import sql_gen_node
from app.business.bi.agent.state import AgentState
from app.business.bi.llm.router import NoLLMProviderError


def _state(**kw) -> AgentState:
    base: AgentState = {
        "question": "本月销售额",
        "schema_text": "- orders(id, amount, status)",
        "dialect": "sqlite",
        "schema_header": "sqlite:\n- orders(id, amount, status)",
        "metric_templates": [],
        "metric_ids": [],
        "draft_sql": None,
        "steps": [],
        "tokens_used": 0,
        "_llm_provider": None,
    }
    base.update(kw)  # type: ignore[typeddict-item]
    return base  # type: ignore[return-value]


def _fake_resp(content: str, total_tokens: int = 100) -> MagicMock:
    r = MagicMock()
    r.content = content
    r.usage.total_tokens = total_tokens
    return r


@pytest.mark.asyncio
async def test_sql_gen_uses_metric_prompt_when_templates_present():
    fake = _fake_resp("```sql\nSELECT SUM(orders.amount) FROM orders\n```", 150)

    with patch("app.business.bi.agent.nodes.sql_gen.get_router") as gr:
        router = MagicMock()
        router.achat = AsyncMock(return_value=fake)
        gr.return_value = router
        state = _state(
            metric_templates=["SUM({order}.amount) WHERE {order}.status='paid'"]
        )
        out = await sql_gen_node(state)

    # draft_sql 至少包含 SUM
    assert "SUM" in out["draft_sql"]
    assert any(s["node"] == "sql_gen" for s in out["steps"])


@pytest.mark.asyncio
async def test_sql_gen_falls_back_to_old_prompt_when_no_metrics():
    fake = _fake_resp("```sql\nSELECT COUNT(*) FROM orders\n```", 100)

    with patch("app.business.bi.agent.nodes.sql_gen.get_router") as gr:
        router = MagicMock()
        router.achat = AsyncMock(return_value=fake)
        gr.return_value = router
        state = _state(metric_templates=[])
        out = await sql_gen_node(state)

    assert "COUNT" in out["draft_sql"]


@pytest.mark.asyncio
async def test_sql_gen_propagates_llm_error_no_mock_fallback():
    """LLM 失败 → NoLLMProviderError 透传,不再有 mock 兜底。"""
    with patch("app.business.bi.agent.nodes.sql_gen.get_router") as gr:
        router = MagicMock()
        router.achat = AsyncMock(side_effect=NoLLMProviderError(available=[], requested="x"))
        gr.return_value = router
        state = _state(metric_templates=["SUM({order}.amount)"])
        with pytest.raises(NoLLMProviderError):
            await sql_gen_node(state)


@pytest.mark.asyncio
async def test_sql_gen_metric_prompt_contains_template_text():
    """当有 metric 模板时,LLM 收到的 user prompt 必须含模板原文。"""
    captured: dict = {}

    class _Router:
        async def achat(self, provider, request):
            captured["prompt"] = request.messages[1].content
            return _fake_resp("```sql\nSELECT 1\n```", 10)

    with patch("app.business.bi.agent.nodes.sql_gen.get_router") as gr:
        gr.return_value = _Router()
        state = _state(
            metric_templates=[
                "SUM({order}.amount) WHERE {order}.status='paid'",
                "COUNT({order}.id)",
            ]
        )
        await sql_gen_node(state)

    prompt = captured["prompt"]
    assert "SUM({order}.amount)" in prompt
    assert "COUNT({order}.id)" in prompt
    assert "必须" in prompt or "原样" in prompt
