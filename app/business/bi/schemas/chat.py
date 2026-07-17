"""AgenticBI Pydantic schemas — 对话 / SQL / 鉴权 / 审计。"""

from __future__ import annotations

from app.core.base_schema import SchemaBase

# ---- Chat ----


class ChatSessionCreate(SchemaBase):
    """创建会话请求。"""

    title: str = "新会话"
    dataset_id: int | None = None
    datasource_id: str | None = None  # sqid（API 内 decode 成 int）


class ChatSessionOut(SchemaBase):
    """会话响应。"""

    id: int
    title: str
    dataset_id: int | None = None
    datasource_id: int | None = None
    last_message_at: str | None = None
    status_type: str
    created_at: str | None = None


class ChatSendRequest(SchemaBase):
    """发送问题请求。"""

    question: str
    datasource_id: str | None = None  # sqid（API 内 decode 成 int）


class ChatMessageOut(SchemaBase):
    """消息响应。"""

    id: int
    session_id: int
    role: str
    content: str
    thinking: str | None = None
    sql: str | None = None
    chart_id: int | None = None
    error: str | None = None
    cost_ms: int | None = None
    tokens_used: int | None = None
    created_at: str | None = None


# ---- SQL Workbench ----


class SqlExecuteRequest(SchemaBase):
    """SQL 工作台执行请求。"""

    datasource_id: str  # 前端传 sqid，API 内 decode 成 int
    sql: str
    allow_write: bool = False


class SqlExecuteResponse(SchemaBase):
    """SQL 执行响应。"""

    columns: list[str]
    rows: list[list]
    row_count: int
    cost_ms: int
    final_sql: str
    masked_columns: list[str] = []
    sql_hash: str


class SqlExplainRequest(SchemaBase):
    """SQL EXPLAIN 请求。"""

    datasource_id: str  # sqid
    sql: str


# ---- Grant / Masking ----


class DatasourceGrantIn(SchemaBase):
    """数据源授权请求。"""

    role_code: str
    datasource_id: int
    scope: str = "all"
    allow_export: bool = False
    allow_write: bool = False


class ColumnMaskingIn(SchemaBase):
    """列脱敏请求。"""

    column_id: int
    role_code: str
    mask_type: str


__all__ = [
    "ChatSessionCreate",
    "ChatSessionOut",
    "ChatSendRequest",
    "ChatMessageOut",
    "SqlExecuteRequest",
    "SqlExecuteResponse",
    "SqlExplainRequest",
    "DatasourceGrantIn",
    "ColumnMaskingIn",
]
