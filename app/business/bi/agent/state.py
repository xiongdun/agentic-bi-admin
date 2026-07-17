"""Agent 共享状态 — TypedDict。

每个 Agent 节点读取 / 修改同一份 state，结构扁平便于序列化（写
ChatMessage.agent_steps_json 用）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """Agent 共享状态。"""

    # 输入
    user_id: int
    tenant_id: int
    question: str
    datasource_id: int
    session_id: int | None
    role_code: str | None  # 当前用户角色（用于列脱敏 / 行级授权）
    _llm_provider: str | None  # 内部覆盖 LLM provider（仅供 runner 使用）

    # 上下文
    schema_text: str  # 注入 prompt 的 schema 摘要
    dialect: str
    intent: str  # "table" | "metric" | "freeform"
    target_tables: list[str]
    target_metrics: list[str]

    # 意图路由选中的 metric（Phase 1.x）
    metric_ids: list[int]  # LLM 选中的 metric id 列表（可空）
    metric_templates: list[str]  # 对应 metric 的 sql_template 列表

    # LLM 输出
    draft_sql: str
    final_sql: str
    chart_suggestion: dict
    explanation: str

    # 执行结果
    query_result: dict  # {columns, rows, row_count, cost_ms}
    execution_error: str | None

    # 兜底
    fallback_used: str | None  # "mock" | "rule" | None

    # 留痕
    steps: list[dict]
    tokens_used: int
    cost_ms_total: int


@dataclass(slots=True)
class StepTrace:
    """单步 agent 节点留痕。"""

    node: str
    started_at: float
    ended_at: float = 0.0
    input: dict = field(default_factory=dict)
    output: dict = field(default_factory=dict)
    tokens: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node": self.node,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "durationMs": int((self.ended_at - self.started_at) * 1000),
            "input": self.input,
            "output": self.output,
            "tokens": self.tokens,
            "error": self.error,
        }


__all__ = ["AgentState", "StepTrace"]
