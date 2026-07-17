"""Intent Router (LLM-based) 单元测试。

Phase 1.x 行为:
- 必走 LLM,不再用纯规则
- 成功解析 → intent="metric" + metric_ids 填充
- intent="metric" + metrics=[] → 降级为 "table"
- JSON 解析失败 → 降级 "table"
- 选中的 metric id 不在 DB 现有集合 → 忽略
- LLM 抛 NoLLMProviderError → 透传给上层
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from tortoise import Tortoise

from app.business.bi.agent.nodes.intent import IntentRouter
from app.business.bi.agent.state import AgentState
from app.business.bi.llm.router import NoLLMProviderError
from app.business.bi.models.metadata import Datasource, DatasourceType
from app.business.bi.services.metric import create_metric

_LITE_TORTOISE_ORM = {
    "connections": {"default": "sqlite://:memory:"},
    "apps": {
        "app_system": {
            "models": ["app.business.bi.models"],
            "default_connection": "default",
        },
    },
    "use_tz": False,
    "timezone": "Asia/Shanghai",
}


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def lite_db():
    await Tortoise.init(config=_LITE_TORTOISE_ORM)
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()


@pytest_asyncio.fixture(loop_scope="session")
async def ds(lite_db):
    d = await Datasource.create(
        name=f"ds_ir_{uuid.uuid4().hex[:8]}",
        type=DatasourceType.sqlite, database=":memory:",
        tenant_id=1, is_default=False,
    )
    return d


def _state(**kw) -> AgentState:
    base: AgentState = {
        "question": "本月销售额",
        "schema_text": "- orders(id, amount, status, ordered_at)",
        "dialect": "sqlite",
        "datasource_id": 0,
        "intent": None,  # type: ignore[typeddict-item]
        "metric_ids": [],
        "metric_templates": [],
        "steps": [],
        "tokens_used": 0,
        "_llm_provider": None,
    }
    base.update(kw)  # type: ignore[typeddict-item]
    return base  # type: ignore[return-value]


def _fake_resp(content: str, total_tokens: int = 100) -> MagicMock:
    resp = MagicMock()
    resp.content = content
    resp.usage.total_tokens = total_tokens
    return resp


@pytest.mark.asyncio(loop_scope="session")
async def test_intent_router_parses_metric_with_id(ds):
    m = await create_metric(
        name="sales", display_name="销售额",
        sql_template="SUM({order}.amount) WHERE {order}.status='paid'",
        datasource_id=ds.id, owner_id=1,
    )
    payload = json.dumps(
        {"intent": "metric", "metrics": [{"id": m.id, "reason": "金额汇总"}], "reasoning": "用户问销售额"}
    )

    with patch("app.business.bi.agent.nodes.intent.get_router") as gr:
        router = MagicMock()
        router.achat = AsyncMock(return_value=_fake_resp(payload, 120))
        gr.return_value = router

        state = _state(datasource_id=ds.id)
        out = await IntentRouter()(state)

    assert out["intent"] == "metric"
    assert m.id in out["metric_ids"]
    assert out["metric_templates"] == [m.sql_template]
    assert any(s["node"] == "intent" for s in out["steps"])
    assert out["tokens_used"] >= 120


@pytest.mark.asyncio(loop_scope="session")
async def test_intent_router_falls_back_when_empty_metrics(ds):
    """intent=metric + metrics=[] → 降级 table。"""
    payload = json.dumps({"intent": "metric", "metrics": [], "reasoning": "无匹配 metric"})

    with patch("app.business.bi.agent.nodes.intent.get_router") as gr:
        router = MagicMock()
        router.achat = AsyncMock(return_value=_fake_resp(payload, 80))
        gr.return_value = router

        state = _state(datasource_id=ds.id)
        out = await IntentRouter()(state)

    assert out["intent"] == "table"
    assert out["metric_ids"] == []
    assert out["metric_templates"] == []


@pytest.mark.asyncio(loop_scope="session")
async def test_intent_router_handles_invalid_json(ds):
    """LLM 返回非 JSON → 降级 table。"""
    with patch("app.business.bi.agent.nodes.intent.get_router") as gr:
        router = MagicMock()
        router.achat = AsyncMock(return_value=_fake_resp("not a json", 50))
        gr.return_value = router

        state = _state(datasource_id=ds.id)
        out = await IntentRouter()(state)

    assert out["intent"] == "table"
    assert out["metric_ids"] == []


@pytest.mark.asyncio(loop_scope="session")
async def test_intent_router_filters_unknown_metric_ids(ds):
    """LLM 选中的 metric id 不在 DB 集合里 → 忽略,降级 table。"""
    payload = json.dumps(
        {"intent": "metric", "metrics": [{"id": 99999, "reason": "x"}], "reasoning": "x"}
    )

    with patch("app.business.bi.agent.nodes.intent.get_router") as gr:
        router = MagicMock()
        router.achat = AsyncMock(return_value=_fake_resp(payload, 60))
        gr.return_value = router

        state = _state(datasource_id=ds.id)
        out = await IntentRouter()(state)

    assert out["intent"] == "table"
    assert out["metric_ids"] == []


@pytest.mark.asyncio(loop_scope="session")
async def test_intent_router_propagates_no_llm_error(ds):
    """未配置 LLM → 透传 NoLLMProviderError。"""
    with patch("app.business.bi.agent.nodes.intent.get_router") as gr:
        router = MagicMock()
        router.achat = AsyncMock(side_effect=NoLLMProviderError(available=[], requested="x"))
        gr.return_value = router

        state = _state(datasource_id=ds.id)
        with pytest.raises(NoLLMProviderError):
            await IntentRouter()(state)


@pytest.mark.asyncio(loop_scope="session")
async def test_intent_router_normalizes_intent_values(ds):
    """LLM 返回不在白名单的 intent → 降级 table。"""
    payload = json.dumps({"intent": "magic", "metrics": [], "reasoning": "x"})

    with patch("app.business.bi.agent.nodes.intent.get_router") as gr:
        router = MagicMock()
        router.achat = AsyncMock(return_value=_fake_resp(payload, 30))
        gr.return_value = router

        state = _state(datasource_id=ds.id)
        out = await IntentRouter()(state)

    assert out["intent"] == "table"
