"""AgenticBI Agent 编排 — 包入口。

状态机用纯 Python dict（TypedDict）管理，不引入 LangGraph。Phase 1 用顺序
链式执行（intent → sql_gen → validate → execute → explain），Phase 2 升级为
LangGraph StateGraph 加分支 / retry / 并行。
"""

from app.business.bi.agent.runner import run_chat_turn
from app.business.bi.agent.state import AgentState, StepTrace

__all__ = ["AgentState", "StepTrace", "run_chat_turn"]
