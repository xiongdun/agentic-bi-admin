"""SQL 校验节点 — 白名单 + 脱敏 + 行级注入。"""

from __future__ import annotations

import time
from typing import Any

from app.business.bi.agent.state import AgentState, StepTrace
from app.business.bi.models import BiDatasource
from app.business.bi.sandbox.dialect import get_dialect_name
from app.business.bi.sandbox.tenant import inject_tenant_filter, should_inject_tenant
from app.business.bi.sandbox.whitelist import validate_sql


async def sql_validate_node(state: AgentState) -> dict[str, Any]:
    """SQL 校验节点。"""
    start = time.time()
    sql_text = state.get("sql_text", "")

    if not sql_text:
        elapsed_ms = int((time.time() - start) * 1000)
        step: StepTrace = {
            "node": "sql_validate",
            "status": "failed",
            "data": {},
            "elapsed_ms": elapsed_ms,
            "error": "SQL 为空",
        }
        return {
            "validated_sql": "",
            "error": "SQL 为空",
            "steps": state.get("steps", []) + [step],
        }

    # 获取方言
    datasource_id = state.get("datasource_id")
    dialect = "sqlite"
    if datasource_id:
        ds = await BiDatasource.filter(id=datasource_id).first()
        if ds:
            dialect = get_dialect_name(ds.db_type)

    try:
        # 1. 白名单校验（含自动 LIMIT）
        result = validate_sql(sql_text, dialect=dialect)
        validated_sql = result.sql

        # 2. 行级 tenant 注入
        data_scope = state.get("data_scope", "all")
        if should_inject_tenant(data_scope):
            scope_id = state.get("scope_id")
            if scope_id is not None:
                validated_sql = inject_tenant_filter(validated_sql, scope_id, dialect=dialect)

        # 3. 列脱敏（在 executor 执行后对结果脱敏，这里不处理）

        elapsed_ms = int((time.time() - start) * 1000)
        step = {
            "node": "sql_validate",
            "status": "success",
            "data": {"validated_sql": validated_sql},
            "elapsed_ms": elapsed_ms,
            "error": None,
        }

        return {
            "validated_sql": validated_sql,
            "steps": state.get("steps", []) + [step],
        }

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        step = {
            "node": "sql_validate",
            "status": "failed",
            "data": {},
            "elapsed_ms": elapsed_ms,
            "error": str(e),
        }
        return {
            "validated_sql": "",
            "error": str(e),
            "steps": state.get("steps", []) + [step],
        }
