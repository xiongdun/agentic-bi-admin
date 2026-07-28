"""SQL Gen Agent — 调用 LLM 根据 schema + question 生成 SQL。

支持：
- 直接 LLM 调用（带 system / user 消息）
- 输出在 ```sql ... ``` 中则提取
- 有 metric_templates 时切换为 SQL_GEN_WITH_METRIC_USER（强约束）
  并自动把模板里的 ``{xxx}`` 占位符替换为 BiTable 实际表名,
  避免把字面量 ``{order}`` 复制到 SQL 里导致 sqlglot 解析失败
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
from app.business.bi.llm import ChatMessage, ChatRequest, ensure_router
from app.utils import safe_parse

_SQL_BLOCK_RE = re.compile(r"```sql\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def _extract_sql(text: str) -> str | None:
    m = _SQL_BLOCK_RE.search(text)
    if m:
        return m.group(1).strip()
    # 兜底：去掉 ``` 后整段
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        return stripped.strip("`").strip()
    return None


async def _resolve_placeholders(
    templates: list[str],
    *,
    datasource_id: int,
) -> tuple[list[str], dict[str, str]]:
    """把 ``{xxx}`` 占位符替换为 BiTable 里的实际表名。

    匹配规则：placeholder 名(如 ``order``)在 BiTable 表名列表里做
    case-insensitive 子串/前缀匹配;命中就用真实表名(如 ``orders``)替换;
    没命中保留原占位符(LLM 看到 schema_text 没有匹配表时自然会改写)。

    Returns:
        (substituted_templates, mapping) — mapping 是 placeholder→table_name
        便于 prompt 里告诉 LLM 已经做过替换。
    """
    if not templates:
        return [], {}
    # 延迟 import 避免节点模块加载期触发 DB
    from app.business.bi.models import BiTable

    table_rows = await BiTable.filter(datasource_id=datasource_id).values("name")
    table_names = [r["name"] for r in table_rows]
    # 全部 lowercase 用于做大小写无关匹配
    lower_tables = {t.lower(): t for t in table_names}

    mapping: dict[str, str] = {}
    for tpl in templates:
        for m in _PLACEHOLDER_RE.finditer(tpl):
            name = m.group(1)
            if name in mapping:
                continue
            # 1) 精确匹配(忽略大小写): {orders} -> orders
            if name.lower() in lower_tables:
                mapping[name] = lower_tables[name.lower()]
                continue
            # 2) 表名是 placeholder 的复数形式: {order} -> orders
            plural = f"{name.lower()}s"
            if plural in lower_tables:
                mapping[name] = lower_tables[plural]
                continue
            # 3) placeholder 是表名单数形式: {orders} -> order(取 orders)
            #    反向也试一下
            if name.lower().endswith("s") and name.lower()[:-1] in lower_tables:
                mapping[name] = lower_tables[name.lower()[:-1]]
                continue
            # 4) 子串匹配: {order} -> customer_order(最后一个匹配)
            for low, real in lower_tables.items():
                if name.lower() in low:
                    mapping[name] = real
                    break

    def _sub(tpl: str) -> str:
        return _PLACEHOLDER_RE.sub(lambda m: mapping.get(m.group(1), m.group(0)), tpl)

    return [_sub(t) for t in templates], mapping


async def sql_gen_node(state: AgentState) -> AgentState:
    """LLM 生成 SQL。

    行为分支：
    - state["metric_templates"] 非空 → 使用 SQL_GEN_WITH_METRIC_USER
      并先把 ``{xxx}`` 占位符替换为 BiTable 实际表名(避免 LLM 把字面量
      ``{order}`` 复制到 SQL 中导致 sqlglot 解析失败 → executor 跳过 → 无数据)
    - 否则使用旧 SQL_GEN_PROMPT
    - LLM 异常（包括 NoLLMProviderError）**直接上抛**,不再兜底 mock
    """
    started = time.perf_counter()
    question = state.get("question", "")
    schema_text = state.get("schema_text", "(no schema)")
    dialect = state.get("dialect", "sqlite")
    raw_templates: list[str] = list(state.get("metric_templates") or [])

    # 占位符替换：把 {order} 这种 Jinja-like 占位符替换为真实表名
    resolved_templates: list[str] = []
    placeholder_mapping: dict[str, str] = {}
    if raw_templates:
        resolved_templates, placeholder_mapping = await _resolve_placeholders(
            raw_templates,
            datasource_id=state.get("datasource_id", 0),
        )

    schema_header = SCHEMA_HEADER.format(dialect=dialect, schema_text=schema_text)

    if resolved_templates:
        # 在 prompt 里告诉 LLM 模板已替换好,直接用真实表名即可,
        # 不要再把占位符还原回去
        extra_hint = ""
        if placeholder_mapping:
            mapping_str = ", ".join(f"{{{k}}}={v}" for k, v in placeholder_mapping.items())
            extra_hint = f"\n注意:模板中的占位符已替换为真实表名({mapping_str}),直接使用,不要还原为 {{xxx}} 形式。"
        user_prompt = (
            SQL_GEN_WITH_METRIC_USER.format(
                schema_header=schema_header,
                question=question,
                metric_count=len(resolved_templates),
                metric_templates="\n".join(f"  {i + 1}. {t}" for i, t in enumerate(resolved_templates)),
            )
            + extra_hint
        )
    else:
        user_prompt = SQL_GEN_PROMPT.format(schema_header=schema_header, question=question)

    messages = [
        ChatMessage(role="system", content=SYSTEM_BASE),
        ChatMessage(role="user", content=user_prompt),
    ]
    request = ChatRequest(messages=messages, temperature=0.1)

    router = await ensure_router()
    provider = state.get("_llm_provider")
    # NoLLMProviderError / 其他 LLM 错误直接上抛 — 由 chat.py SSE 转 error 事件
    resp = await router.achat(provider, request)

    draft = _extract_sql(resp.content) or resp.content.strip()
    # 防御性：万一 LLM 还是把 {xxx} 字面量写进了 SQL,这里强制替换一次
    if placeholder_mapping and "{" in draft:
        draft = _PLACEHOLDER_RE.sub(
            lambda m: placeholder_mapping.get(m.group(1), m.group(0)),
            draft,
        )
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
                "metric_count": len(resolved_templates),
                "placeholder_mapping": placeholder_mapping,
            },
            output={"draft_sql": draft, "raw_excerpt": resp.content[:200]},
            tokens=resp.usage.total_tokens,
        ).to_dict()
    )
    state["tokens_used"] = state.get("tokens_used", 0) + resp.usage.total_tokens
    return state


__all__ = ["sql_gen_node", "_extract_sql", "_resolve_placeholders"]
