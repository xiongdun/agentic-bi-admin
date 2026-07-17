"""Agent Prompt 模板测试。"""

from app.business.bi.agent.prompts import (
    EXPLAIN_PROMPT,
    INTENT_PROMPT,
    INTENT_ROUTER_SYSTEM,
    INTENT_ROUTER_USER,
    SCHEMA_HEADER,
    SQL_GEN_PROMPT,
    SQL_GEN_WITH_METRIC_USER,
    SYSTEM_BASE,
)


def test_intent_router_system_loaded():
    assert "意图" in INTENT_ROUTER_SYSTEM or "JSON" in INTENT_ROUTER_SYSTEM


def test_intent_router_user_has_placeholders():
    for key in ("{dialect}", "{schema_text}", "{metric_count}", "{metric_list}", "{question}"):
        assert key in INTENT_ROUTER_USER, f"Missing placeholder {key}"


def test_intent_router_user_mentions_metrics():
    """Prompt 必须引导 LLM 选 metric 列表。"""
    assert "metric" in INTENT_ROUTER_USER.lower() or "指标" in INTENT_ROUTER_USER


def test_intent_router_user_returns_json_shape():
    """Prompt 应规定 JSON 返回结构(intent / metrics / reasoning)。"""
    assert "intent" in INTENT_ROUTER_USER
    assert "metrics" in INTENT_ROUTER_USER
    assert "reasoning" in INTENT_ROUTER_USER


def test_sql_gen_with_metric_has_placeholders():
    for key in ("{schema_header}", "{question}", "{metric_count}", "{metric_templates}"):
        assert key in SQL_GEN_WITH_METRIC_USER, f"Missing placeholder {key}"
    assert "必须" in SQL_GEN_WITH_METRIC_USER or "原样" in SQL_GEN_WITH_METRIC_USER


def test_sql_gen_with_metric_requires_template_verbatim():
    """Prompt 必须强制 LLM 原样使用模板表达式。"""
    assert "原样" in SQL_GEN_WITH_METRIC_USER or "原表达式" in SQL_GEN_WITH_METRIC_USER


def test_existing_prompts_still_present():
    """新增 prompt 不应破坏已有导出。"""
    for sym in (SYSTEM_BASE, SCHEMA_HEADER, INTENT_PROMPT, SQL_GEN_PROMPT, EXPLAIN_PROMPT):
        assert isinstance(sym, str) and len(sym) > 0
