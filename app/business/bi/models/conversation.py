# pyright: reportIncompatibleVariableOverride=false
"""AgenticBI 数据模型 — 对话与执行子模块。

3 张表：
- ChatSession
- ChatMessage
- QueryExecution
"""

from __future__ import annotations

from enum import Enum

from tortoise import fields

from app.business.bi.models.metadata import Datasource
from app.business.bi.models.semantic import Chart, Dataset
from app.core.base_model import AuditMixin, BaseModel, StatusType


class ChatSession(BaseModel, AuditMixin):
    """对话会话。

    每个 ChatSession 隶属于一个用户 + 一个租户，可选绑定一个 Dataset 作为
    Schema Select Agent 的候选范围。
    """

    id = fields.IntField(primary_key=True, description="会话ID")
    user_id = fields.IntField(db_index=True, description="所属用户ID")
    tenant_id = fields.IntField(db_index=True, description="租户ID")
    title = fields.CharField(max_length=200, description="会话标题（首条问题前 30 字）")
    dataset_id: int | None
    dataset: fields.ForeignKeyNullableRelation["Dataset"] = fields.ForeignKeyField(
        "app_system.Dataset",
        null=True,
        blank=True,
        on_delete=fields.SET_NULL,
        related_name="chat_sessions",
        description="绑定的数据集（可空）",
    )
    datasource_id: int | None
    datasource: fields.ForeignKeyNullableRelation["Datasource"] = fields.ForeignKeyField(
        "app_system.Datasource",
        null=True,
        blank=True,
        on_delete=fields.SET_NULL,
        related_name="chat_sessions",
        description="绑定的数据源（可空）",
    )
    last_message_at = fields.DatetimeField(null=True, db_index=True, description="最近一次消息时间")
    status_type = fields.CharEnumField(enum_type=StatusType, default=StatusType.enable, description="状态")

    class Meta:
        table = "bi_chat_session"
        table_description = "BI 对话会话"


class MessageRole(str, Enum):
    """消息角色。"""

    user = "user"
    assistant = "assistant"
    system = "system"
    tool = "tool"


class ChatMessage(BaseModel, AuditMixin):
    """单条对话消息。

    ``agent_steps_json`` 记录本次回复的每个 agent 节点耗时 / 输入 / 输出 / token，
    给审计面板与"思维链留痕"用。
    """

    id = fields.IntField(primary_key=True, description="消息ID")
    session_id: int
    session: fields.ForeignKeyRelation[ChatSession] = fields.ForeignKeyField(
        "app_system.ChatSession",
        related_name="messages",
        on_delete=fields.CASCADE,
        description="所属会话",
    )
    role = fields.CharEnumField(enum_type=MessageRole, db_index=True, description="消息角色")
    content = fields.TextField(description="消息内容")
    thinking = fields.TextField(null=True, blank=True, description="思维链（Explain Agent 输出）")
    sql = fields.TextField(null=True, blank=True, description="生成的 SQL（仅 assistant）")
    chart_id: int | None
    chart: fields.ForeignKeyNullableRelation["Chart"] = fields.ForeignKeyField(
        "app_system.Chart",
        null=True,
        blank=True,
        on_delete=fields.SET_NULL,
        related_name="messages",
        description="推荐图表（可空）",
    )
    error = fields.TextField(null=True, blank=True, description="错误信息")
    agent_steps_json = fields.JSONField(null=True, description="Agent 步骤留痕 [{node, input, output, cost_ms, tokens}]")
    cost_ms = fields.IntField(null=True, description="本次回复总耗时（毫秒）")
    tokens_used = fields.IntField(null=True, description="本次 LLM 调用总 token")

    class Meta:
        table = "bi_chat_message"
        table_description = "BI 对话消息"


class ExecutionStatus(str, Enum):
    """查询执行结果状态。"""

    success = "success"
    failed = "failed"
    timeout = "timeout"
    denied = "denied"


class QueryExecution(BaseModel, AuditMixin):
    """查询执行记录：每次沙箱跑 SQL 写一条，用于审计和结果缓存键。

    失败 / 拒绝 / 成功都写，方便后续做慢查询聚合。
    """

    id = fields.IntField(primary_key=True, description="执行ID")
    session_id: int | None
    session: fields.ForeignKeyNullableRelation[ChatSession] = fields.ForeignKeyField(
        "app_system.ChatSession",
        null=True,
        blank=True,
        on_delete=fields.SET_NULL,
        related_name="executions",
        description="所属会话（SQL 工作台可能为空）",
    )
    message_id: int | None
    message: fields.ForeignKeyNullableRelation[ChatMessage] = fields.ForeignKeyField(
        "app_system.ChatMessage",
        null=True,
        blank=True,
        on_delete=fields.SET_NULL,
        related_name="executions",
        description="所属消息（SQL 工作台可能为空）",
    )
    user_id = fields.IntField(db_index=True, description="执行用户")
    tenant_id = fields.IntField(db_index=True, description="租户")
    datasource_id: int
    datasource: fields.ForeignKeyRelation[Datasource] = fields.ForeignKeyField(
        "app_system.Datasource",
        related_name="executions",
        on_delete=fields.CASCADE,
        description="数据源",
    )
    sql = fields.TextField(description="执行的 SQL")
    status = fields.CharEnumField(enum_type=ExecutionStatus, db_index=True, description="执行状态")
    row_count = fields.IntField(null=True, description="返回行数")
    cost_ms = fields.IntField(null=True, description="执行耗时（毫秒）")
    error = fields.TextField(null=True, blank=True, description="错误信息")
    explain_json = fields.JSONField(null=True, description="SQL EXPLAIN 输出")
    row_limit_applied = fields.IntField(null=True, description="触发的行数限制")
    sql_hash = fields.CharField(max_length=64, db_index=True, null=True, blank=True, description="SQL 哈希（用于结果缓存）")

    class Meta:
        table = "bi_query_execution"
        table_description = "BI 查询执行记录"


__all__ = ["ChatSession", "MessageRole", "ChatMessage", "ExecutionStatus", "QueryExecution"]
