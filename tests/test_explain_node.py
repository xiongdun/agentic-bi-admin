"""Explain Node 单元测试。

Phase 1.x 行为:
- LLM 失败 → 异常直接上抛,不再 mock 兜底
- LLM 成功 → explanation / step 写入 state
- final_sql / draft_sql 都没时直接返回（不调 LLM）
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.business.bi.agent.nodes.explain import explain_node
from app.business.bi.agent.state import AgentState
from app.business.bi.llm.router import NoLLMProviderError


def _state(**kw) -> AgentState:
    base: AgentState = {
        "question": "本月销售额",
        "draft_sql": "SELECT 1",
        "final_sql": "",
        "query_result": {"row_count": 1, "cost_ms": 5},
        "explanation": None,
        "steps": [],
        "tokens_used": 0,
        "_llm_provider": None,
    }
    base.update(kw)  # type: ignore[typeddict-item]
    return base  # type: ignore[return-value]


def _fake_resp(content: str, total_tokens: int = 80) -> MagicMock:
    r = MagicMock()
    r.content = content
    r.usage.total_tokens = total_tokens
    return r


@pytest.mark.asyncio
async def test_explain_raises_when_no_llm():
    """未配置 LLM → NoLLMProviderError 透传,且**只调用一次** LLM（不重试 mock）。"""
    with patch("app.business.bi.agent.nodes.explain.get_router") as gr:
        router = MagicMock()
        router.achat = AsyncMock(side_effect=NoLLMProviderError(available=[], requested="x"))
        gr.return_value = router
        state = _state()
        with pytest.raises(NoLLMProviderError):
            await explain_node(state)
    # 关键：不应回退到 mock 重试
    assert router.achat.await_count == 1
    # 也不应显式以 "mock" 名字调用
    for call in router.achat.await_args_list:
        assert call.args[0] != "mock"


@pytest.mark.asyncio
async def test_explain_writes_step():
    fake = _fake_resp("本查询统计了总数。", 80)
    with patch("app.business.bi.agent.nodes.explain.get_router") as gr:
        router = MagicMock()
        router.achat = AsyncMock(return_value=fake)
        gr.return_value = router
        state = _state()
        out = await explain_node(state)
    assert out["explanation"] == "本查询统计了总数。"
    assert any(s["node"] == "explain" for s in out["steps"])
    assert out["tokens_used"] >= 80


@pytest.mark.asyncio
async def test_explain_short_circuits_when_no_sql():
    """draft_sql + final_sql 都为空 → 不调 LLM,直接返回。"""
    with patch("app.business.bi.agent.nodes.explain.get_router") as gr:
        router = MagicMock()
        router.achat = AsyncMock(side_effect=AssertionError("should not be called"))
        gr.return_value = router
        state = _state(draft_sql="", final_sql="")
        out = await explain_node(state)
    assert out["explanation"] == ""


@pytest.mark.asyncio
async def test_explain_uses_final_sql_first():
    """优先用 final_sql 解释;否则用 draft_sql。"""
    fake = _fake_resp("ok", 10)
    captured: dict = {}

    class _Router:
        async def achat(self, provider, request):
            captured["prompt"] = request.messages[1].content
            return fake

    with patch("app.business.bi.agent.nodes.explain.get_router") as gr:
        gr.return_value = _Router()
        state = _state(draft_sql="SELECT 1", final_sql="SELECT 2")
        await explain_node(state)
    assert "SELECT 2" in captured["prompt"]
