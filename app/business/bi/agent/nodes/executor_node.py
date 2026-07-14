"""Executor Node — 调用 sandbox pipeline 执行 SQL，并把结果写回 state。

从 AgentState 读取：
- draft_sql（由 sql_gen_node 写入）
- user_id / tenant_id / role_code（用于 masking rules 查询）
- datasource_id

执行前自动按 role_code + datasource_id 取列脱敏规则传给 pipeline。
"""

from __future__ import annotations

import time

from app.business.bi.agent.state import AgentState, StepTrace
from app.business.bi.sandbox.pipeline import (
    PipelineContext,
    SqlExecutionDenied,
    run_pipeline,
)
from app.business.bi.services.datasource import get_datasource
from app.business.bi.services.masking import get_masking_rules


async def executor_node(state: AgentState) -> AgentState:
    """调 sandbox pipeline 执行。"""
    started = time.perf_counter()
    draft = state.get("draft_sql", "")
    if state.get("execution_error") or not draft:
        return state

    ds_id = state.get("datasource_id")
    if ds_id is None:
        state["execution_error"] = "datasource_id_missing"
        return state
    ds = await get_datasource(ds_id)
    if ds is None:
        state["execution_error"] = f"datasource_not_found: {ds_id}"
        return state

    user_id = state.get("user_id", 0)
    tenant_id = state.get("tenant_id", 0)
    role_code = state.get("role_code")

    # 按角色取列脱敏规则
    masking_rules = await get_masking_rules(
        role_code=role_code,
        datasource_id=ds.id,
    )

    ctx = PipelineContext(
        datasource=ds,
        user_id=user_id,
        tenant_id=tenant_id,
        masking_rules=masking_rules,
    )
    try:
        result = await run_pipeline(draft, ctx=ctx)
    except SqlExecutionDenied as exc:
        state["execution_error"] = f"sandbox_denied: {exc}"
        return state

    state["final_sql"] = result.final_sql
    state["query_result"] = {
        "columns": result.query.columns,
        "rows": result.query.rows,
        "row_count": result.query.row_count,
        "cost_ms": result.query.cost_ms,
    }
    steps: list = state.setdefault("steps", [])
    steps.append(
        StepTrace(
            node="executor",
            started_at=started,
            ended_at=time.perf_counter(),
            input={"draft_sql": draft, "datasource_id": ds_id, "role_code": role_code},
            output={
                "final_sql": result.final_sql,
                "row_count": result.query.row_count,
                "cost_ms": result.query.cost_ms,
                "masked_columns": result.masked_columns,
            },
        ).to_dict()
    )
    return state


__all__ = ["executor_node"]
