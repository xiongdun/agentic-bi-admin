"""Agent 节点 — 全部通过纯函数 + state 字典流转。

每个 node 接受 ``AgentState``，返回更新后的 ``AgentState``（TypedDict 合并）。
"""

from app.business.bi.agent.nodes import executor_node, explain, intent, sql_gen, sql_validate

__all__ = ["intent", "sql_gen", "sql_validate", "executor_node", "explain"]
