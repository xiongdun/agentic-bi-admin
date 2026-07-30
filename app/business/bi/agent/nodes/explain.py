"""结果解释节点 — LLM 生成中文解读 + 推荐图表类型。"""

from __future__ import annotations

import time
from typing import Any

from app.business.bi.agent.state import AgentState, StepTrace


def _infer_chart_type(columns: list[str], rows: list[dict]) -> str:
    """根据结果数据推断图表类型。"""
    if not rows or not columns:
        return "table"

    # 单列单值 -> 数字展示
    if len(columns) == 1 and len(rows) == 1:
        return "table"

    # 两列（维度 + 度量）-> 柱状图
    if len(columns) == 2:
        return "bar"

    # 包含时间列 -> 折线图
    time_keywords = ["date", "time", "day", "month", "year", "日期", "时间"]
    for col in columns:
        if any(kw in col.lower() for kw in time_keywords):
            return "line"

    return "table"


async def explain_node(state: AgentState) -> dict[str, Any]:
    """结果解释节点。"""
    start = time.time()
    question = state.get("question", "")
    sql_result = state.get("sql_result", {})

    rows = sql_result.get("rows", [])
    columns = sql_result.get("columns", [])
    row_count = sql_result.get("row_count", 0)

    # 推断图表类型
    chart_type = _infer_chart_type(columns, rows)

    explanation = ""
    token_usage = {}

    try:
        from app.business.bi.llm.router import BiLLMRouter

        provider = await BiLLMRouter.get_default_from_db()

        # 限制传给 LLM 的数据量
        sample_rows = rows[:10]

        prompt = f"""用户问题: {question}

SQL 执行结果（共 {row_count} 行，展示前 {len(sample_rows)} 行）:
列: {columns}
数据: {sample_rows}

请用简洁的中文解读这个查询结果，回答用户的问题。如果数据为空，说明可能的原因。
推荐图表类型: {chart_type}

解读:"""

        result = await provider.chat(prompt, temperature=0.3)
        explanation = result.content.strip()
        token_usage = result.token_usage

    except Exception as e:
        explanation = f"查询完成，共返回 {row_count} 行数据。（解读生成失败: {e}）"

    elapsed_ms = int((time.time() - start) * 1000)
    step: StepTrace = {
        "node": "explain",
        "status": "success",
        "data": {"chart_type": chart_type},
        "elapsed_ms": elapsed_ms,
        "error": None,
    }

    # 合并 token_usage（防御性：value 非 int/float 时用新值覆盖）
    prev_usage = state.get("token_usage", {})
    merged_usage = {}
    for k in set(list(prev_usage.keys()) + list(token_usage.keys())):
        pv = prev_usage.get(k, 0)
        nv = token_usage.get(k, 0)
        if isinstance(pv, int | float) and isinstance(nv, int | float):
            merged_usage[k] = pv + nv
        else:
            merged_usage[k] = nv

    return {
        "explanation": explanation,
        "chart_type": chart_type,
        "steps": state.get("steps", []) + [step],
        "token_usage": merged_usage,
    }
