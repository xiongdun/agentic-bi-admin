"""SQL Validate Node — 用 sandbox 白名单 / 危险关键字做快速校验。

通过即进入 executor；失败则直接写到 state.execution_error，跳过 executor。
"""

from __future__ import annotations

import time
from typing import cast

from app.business.bi.agent.state import AgentState, StepTrace
from app.business.bi.sandbox.whitelist import validate_tree
from app.utils import DialectName, safe_parse


async def sql_validate_node(state: AgentState) -> AgentState:
    """白名单校验。"""
    started = time.perf_counter()
    draft = state.get("draft_sql", "")
    dialect = state.get("dialect", "sqlite")
    if not draft:
        state["execution_error"] = "empty_sql"
    else:
        tree = safe_parse(draft, cast(DialectName, dialect))
        if tree is None:
            state["execution_error"] = "parse_failed"
        else:
            ok, reason = validate_tree(tree, dialect=dialect)
            if not ok:
                state["execution_error"] = f"whitelist_denied: {reason}"
    state.setdefault("steps", []).append(
        StepTrace(
            node="sql_validate",
            started_at=started,
            ended_at=time.perf_counter(),
            input={"draft_sql": draft, "dialect": dialect},
            output={"ok": state.get("execution_error") is None, "error": state.get("execution_error")},
        ).to_dict()
    )
    return state


__all__ = ["sql_validate_node"]
