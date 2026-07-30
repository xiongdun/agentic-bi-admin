"""执行节点 — 配额检查 + SQLAlchemy 异步执行。"""

from __future__ import annotations

import time
from typing import Any

from app.business.bi.agent.state import AgentState, StepTrace
from app.business.bi.models import BiDatasource
from app.business.bi.sandbox.executor import execute_sql


async def executor_node(state: AgentState) -> dict[str, Any]:
    """执行节点。"""
    start = time.time()
    validated_sql = state.get("validated_sql", "")

    if not validated_sql:
        elapsed_ms = int((time.time() - start) * 1000)
        step: StepTrace = {
            "node": "executor",
            "status": "failed",
            "data": {},
            "elapsed_ms": elapsed_ms,
            "error": "校验后的 SQL 为空",
        }
        return {
            "sql_result": {},
            "error": "校验后的 SQL 为空",
            "steps": state.get("steps", []) + [step],
        }

    try:
        # 获取数据源
        datasource_id = state.get("datasource_id")
        if datasource_id:
            datasource = await BiDatasource.filter(id=datasource_id).first()
        else:
            datasource = await BiDatasource.filter(status_type="1").first()

        if datasource is None:
            raise Exception("未配置可用数据源")

        user_id = state.get("user_id", 0)

        # 执行 SQL
        result = await execute_sql(
            sql=validated_sql,
            datasource=datasource,
            user_id=user_id,
        )

        sql_result = {
            "rows": result.rows,
            "columns": result.columns,
            "elapsedMs": result.elapsed_ms,
            "rowCount": result.row_count,
        }

        elapsed_ms = int((time.time() - start) * 1000)
        step = {
            "node": "executor",
            "status": "success",
            "data": {"row_count": result.row_count, "elapsed_ms": result.elapsed_ms},
            "elapsed_ms": elapsed_ms,
            "error": None,
        }

        return {
            "sql_result": sql_result,
            "steps": state.get("steps", []) + [step],
        }

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        step = {
            "node": "executor",
            "status": "failed",
            "data": {},
            "elapsed_ms": elapsed_ms,
            "error": str(e),
        }
        return {
            "sql_result": {},
            "error": str(e),
            "steps": state.get("steps", []) + [step],
        }
