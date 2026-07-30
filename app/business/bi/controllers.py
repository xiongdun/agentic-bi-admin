"""BI 模块 controllers — 基于 CRUDBase 的控制器。

每个 controller 负责单模型的 CRUD 入口，build_search 由 CRUDRouter 调用。
加密 / 解密 / 脱敏由 service 层和 CRUDRouter 的 override 钩子处理。
"""

from __future__ import annotations

from app.business.bi.models import (
    BiAuditLog,
    BiChatMessage,
    BiChatSession,
    BiColumn,
    BiDatasource,
    BiForeignKey,
    BiIndex,
    BiLLMModel,
    BiLLMProvider,
    BiMaskingRule,
    BiMetric,
    BiQuotaConfig,
    BiTable,
)
from app.utils import CRUDBase

# ---- metadata ----
bi_datasource_controller = CRUDBase(model=BiDatasource)
bi_table_controller = CRUDBase(model=BiTable)
bi_column_controller = CRUDBase(model=BiColumn)
bi_index_controller = CRUDBase(model=BiIndex)
bi_foreign_key_controller = CRUDBase(model=BiForeignKey)

# ---- semantic ----
bi_metric_controller = CRUDBase(model=BiMetric)

# ---- conversation ----
bi_chat_session_controller = CRUDBase(model=BiChatSession)
bi_chat_message_controller = CRUDBase(model=BiChatMessage)

# ---- llm ----
bi_llm_provider_controller = CRUDBase(model=BiLLMProvider)
bi_llm_model_controller = CRUDBase(model=BiLLMModel)

# ---- audit ----
bi_audit_log_controller = CRUDBase(model=BiAuditLog)

# ---- security ----
bi_masking_rule_controller = CRUDBase(model=BiMaskingRule)
bi_quota_config_controller = CRUDBase(model=BiQuotaConfig)


# 兼容别名：与 HR 模块命名风格一致（PascalCase + Controller 后缀）
BiDatasourceController = bi_datasource_controller
BiTableController = bi_table_controller
BiColumnController = bi_column_controller
BiIndexController = bi_index_controller
BiForeignKeyController = bi_foreign_key_controller
BiMetricController = bi_metric_controller
BiChatSessionController = bi_chat_session_controller
BiChatMessageController = bi_chat_message_controller
BiLLMProviderController = bi_llm_provider_controller
BiLLMModelController = bi_llm_model_controller
BiAuditLogController = bi_audit_log_controller
BiMaskingRuleController = bi_masking_rule_controller
BiQuotaConfigController = bi_quota_config_controller
