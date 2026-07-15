"""AgenticBI 数据模型 — 入口 re-export。

业务模块要求 ``app.business.bi.models`` 是一个可 import 的包（autodiscover
据此把本模块注册到 Tortoise）。本文件聚合四个子模块中的所有模型类。
"""

from app.business.bi.models.conversation import (
    ChatMessage,
    ChatSession,
    ExecutionStatus,
    MessageRole,
    QueryExecution,
)
from app.business.bi.models.llm import (
    DEFAULT_BASE_URLS,
    BiModel,
    BiModelProvider,
    ModelProviderType,
    ModelType,
)
from app.business.bi.models.metadata import (
    BiColumn,
    BiTable,
    Datasource,
    DatasourceType,
    JoinType,
    Relation,
    Synonym,
    SynonymKind,
    Tenant,
)
from app.business.bi.models.security import (
    AuditLog,
    ColumnMasking,
    DataScopeType,
    DatasourceGrant,
    MaskType,
)
from app.business.bi.models.audit import BiAuditSql
from app.business.bi.models.semantic import (
    Chart,
    ChartAgg,
    ChartType,
    Dataset,
    DatasetVisibility,
    Metric,
)

__all__ = [
    # metadata
    "Tenant",
    "DatasourceType",
    "Datasource",
    "BiTable",
    "BiColumn",
    "JoinType",
    "Relation",
    "SynonymKind",
    "Synonym",
    # semantic
    "Metric",
    "Dataset",
    "DatasetVisibility",
    "ChartType",
    "ChartAgg",
    "Chart",
    # conversation
    "ChatSession",
    "MessageRole",
    "ChatMessage",
    "ExecutionStatus",
    "QueryExecution",
    # security
    "DataScopeType",
    "DatasourceGrant",
    "MaskType",
    "ColumnMasking",
    "AuditLog",
    # audit
    "BiAuditSql",
    # llm
    "ModelProviderType",
    "DEFAULT_BASE_URLS",
    "BiModelProvider",
    "ModelType",
    "BiModel",
]
