"""Agent 流水线状态定义。"""

from __future__ import annotations

from typing import Any, TypedDict


class StepTrace(TypedDict, total=False):
    """单步执行留痕。"""

    node: str  # 节点名（intent / sql_gen / sql_validate / executor / explain）
    status: str  # started / success / failed
    data: dict[str, Any]  # 节点输出数据
    elapsed_ms: int  # 耗时毫秒
    error: str | None  # 错误信息（status=failed 时）


class AgentState(TypedDict, total=False):
    """Agent 流水线状态（LangGraph StateGraph 用）。"""

    # 输入
    question: str  # 用户自然语言问题
    session_id: int  # 对话会话 ID
    user_id: int  # 用户 ID
    user_msg_id: int  # 用户消息 ID（用于持久化）
    data_scope: str  # 用户 data_scope（all / scope / self / custom）
    scope_id: int | None  # 行级 scope_id（data_scope != all 时用于 tenant 注入）
    datasource_id: int | None  # 数据源 ID（None 用默认）

    # 中间状态
    intent_type: str  # 意图类型（query / count / aggregate / list / unknown）
    tables: list[dict]  # 相关表元数据（供 sql_gen 用）
    sql_text: str  # 生成的 SQL
    validated_sql: str  # 校验后的 SQL（含 LIMIT / tenant 注入）
    validate_error: str | None  # 最近一次校验失败原因（用于自纠错重试）
    retry_count: int  # SQL 生成已重试次数（上限 MAX_SQL_RETRIES）

    # 输出
    sql_result: dict[str, Any]  # 执行结果（rows / columns / elapsed_ms / row_count）
    explanation: str  # LLM 生成的中文解读
    chart_type: str  # 推荐图表类型（bar / line / pie / table / scatter）
    steps: list[StepTrace]  # 步骤留痕
    error: str | None  # 错误信息（整个流程失败时）
    token_usage: dict[str, int | float]  # 累计 token 用量
