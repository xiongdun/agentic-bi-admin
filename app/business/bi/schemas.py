# pyright: reportIncompatibleVariableOverride=false
"""BI 模块 Pydantic schema — 13 个模型的请求/响应 Schema。

项目历史教训：
- 对外 ID 用 ``SqidId`` / ``SqidPath``（输出由 ``BaseModel.to_dict`` 自动编码为 sqid）。
- **SQID 参数在 request schema 中定义为 str 类型，API 层解码**（避免 bare ``int``
  直接拒绝前端传来的 sqid 字符串）。FK 引用字段（``datasource_id`` /
  ``provider_id`` / ``session_id`` / ``table_id`` 等）在 Create / Update / Search
  schema 中一律声明为 ``str``，由 API/service 层 ``decode_id()`` 后再传入 ORM。
- Update schema 用 ``make_optional`` 生成。
- 分页 schema 继承 ``PageQueryBase``。
- ``Out`` schema 仅作为 OpenAPI 响应文档模型（CRUDRouter 实际响应走 ``to_dict``），
  密码 / API Key 等敏感字段在 ``Out`` 中用 ``"***"`` 占位或不返回。
"""

from datetime import datetime

from pydantic import Field

from app.utils import PageQueryBase, SchemaBase, StatusType, make_optional

# ============================================================
# metadata：BiDatasource / BiTable / BiColumn / BiIndex / BiForeignKey
# ============================================================


class BiDatasourceBase(SchemaBase):
    name: str | None = Field(None, title="数据源名称")
    db_type: str | None = Field(None, title="数据库类型", description="postgresql/mysql/clickhouse/trino/sqlite")
    host: str | None = Field(None, title="主机地址")
    port: int | None = Field(None, title="端口")
    username: str | None = Field(None, title="用户名")
    database: str | None = Field(None, title="数据库名")
    extra_params: dict | None = Field(None, title="额外连接参数")
    status_type: StatusType | None = Field(None, title="状态")
    tenant_id: int | None = Field(None, title="租户ID")


class BiDatasourceCreate(BiDatasourceBase):
    name: str = Field(title="数据源名称")
    db_type: str = Field(title="数据库类型")
    host: str = Field(title="主机地址")
    port: int = Field(title="端口")
    username: str = Field(title="用户名")
    password: str = Field(title="密码（明文，后端 Fernet 加密存储）")
    database: str = Field(title="数据库名")


BiDatasourceUpdate = make_optional(BiDatasourceCreate, "BiDatasourceUpdate")
# password 在 Update 中可选（不传则保留原密文）
BiDatasourceUpdate.model_fields["password"].default = None
BiDatasourceUpdate.model_rebuild(force=True)


class BiDatasourceSearch(BiDatasourceBase, PageQueryBase):
    pass  # type: ignore[misc]


class BiDatasourceOut(SchemaBase):
    """数据源响应（不返回 password 明文）。"""

    id: str | None = Field(None, title="数据源ID（sqid）")
    name: str | None = Field(None, title="数据源名称")
    db_type: str | None = Field(None, title="数据库类型")
    host: str | None = Field(None, title="主机地址")
    port: int | None = Field(None, title="端口")
    username: str | None = Field(None, title="用户名")
    database: str | None = Field(None, title="数据库名")
    extra_params: dict | None = Field(None, title="额外连接参数")
    status_type: StatusType | None = Field(None, title="状态")
    tenant_id: int | None = Field(None, title="租户ID")
    last_synced_at: datetime | None = Field(None, title="最后同步时间")
    password: str | None = Field("***", title="密码（脱敏占位符）")


class BiDatasourceTestResult(SchemaBase):
    success: bool = Field(title="是否成功")
    message: str = Field(title="结果消息")
    elapsed_ms: int = Field(title="耗时毫秒")


class BiDatasourceSyncResult(SchemaBase):
    datasource_id: str = Field(title="数据源ID")
    tables_synced: int = Field(title="同步表数")
    columns_synced: int = Field(title="同步列数")
    indexes_synced: int = Field(title="同步索引数")
    foreign_keys_synced: int = Field(title="同步外键数")
    elapsed_ms: int = Field(title="耗时毫秒")
    errors: list[str] = Field(default_factory=list, title="错误列表")


# ---- BiTable / BiColumn / BiIndex / BiForeignKey（只读） ----


class BiTableSearch(PageQueryBase):
    datasource_id: str | None = Field(None, title="数据源ID（sqid）")
    name: str | None = Field(None, title="表名（模糊）")


class BiTableOut(SchemaBase):
    id: str | None = Field(None, title="表ID（sqid）")
    datasource_id: str | None = Field(None, title="数据源ID（sqid）")
    name: str | None = Field(None, title="表名")
    comment: str | None = Field(None, title="表注释")
    row_count: int | None = Field(None, title="行数")
    source_created_at: datetime | None = Field(None, title="源表创建时间")
    source_updated_at: datetime | None = Field(None, title="源表更新时间")


class BiColumnSearch(PageQueryBase):
    table_id: str | None = Field(None, title="表ID（sqid）")
    name: str | None = Field(None, title="列名（模糊）")


class BiColumnOut(SchemaBase):
    id: str | None = Field(None, title="列ID（sqid）")
    table_id: str | None = Field(None, title="表ID（sqid）")
    name: str | None = Field(None, title="列名")
    data_type: str | None = Field(None, title="数据类型")
    is_primary: bool | None = Field(None, title="是否主键")
    is_nullable: bool | None = Field(None, title="是否可空")
    default_value: str | None = Field(None, title="默认值")
    comment: str | None = Field(None, title="列注释")
    sample_values: list | None = Field(None, title="采样值")


class BiIndexSearch(PageQueryBase):
    table_id: str | None = Field(None, title="表ID（sqid）")


class BiIndexOut(SchemaBase):
    id: str | None = Field(None, title="索引ID（sqid）")
    table_id: str | None = Field(None, title="表ID（sqid）")
    name: str | None = Field(None, title="索引名")
    index_type: str | None = Field(None, title="索引类型")
    columns: list | None = Field(None, title="包含的列数组")
    is_unique: bool | None = Field(None, title="是否唯一索引")


class BiForeignKeySearch(PageQueryBase):
    table_id: str | None = Field(None, title="表ID（sqid）")


class BiForeignKeyOut(SchemaBase):
    id: str | None = Field(None, title="外键ID（sqid）")
    table_id: str | None = Field(None, title="表ID（sqid）")
    name: str | None = Field(None, title="外键名")
    column_name: str | None = Field(None, title="源列名")
    ref_table: str | None = Field(None, title="目标表名")
    ref_column: str | None = Field(None, title="目标列名")


# ============================================================
# semantic：BiMetric
# ============================================================


class BiMetricBase(SchemaBase):
    name: str | None = Field(None, title="指标名称")
    code: str | None = Field(None, title="指标编码")
    description: str | None = Field(None, title="指标描述")
    sql_template: str | None = Field(None, title="SQL 模板", description="含 {xxx} 占位符")
    chart_type: str | None = Field(None, title="推荐图表类型")
    status_type: StatusType | None = Field(None, title="状态")


class BiMetricCreate(BiMetricBase):
    name: str = Field(title="指标名称")
    code: str = Field(title="指标编码")
    datasource_id: str = Field(title="数据源ID（sqid）")
    sql_template: str = Field(title="SQL 模板")


BiMetricUpdate = make_optional(BiMetricCreate, "BiMetricUpdate")


class BiMetricSearch(BiMetricBase, PageQueryBase):
    datasource_id: str | None = Field(None, title="数据源ID（sqid）")


class BiMetricOut(SchemaBase):
    id: str | None = Field(None, title="指标ID（sqid）")
    name: str | None = Field(None, title="指标名称")
    code: str | None = Field(None, title="指标编码")
    description: str | None = Field(None, title="指标描述")
    datasource_id: str | None = Field(None, title="数据源ID（sqid）")
    sql_template: str | None = Field(None, title="SQL 模板")
    chart_type: str | None = Field(None, title="推荐图表类型")
    status_type: StatusType | None = Field(None, title="状态")


class BiMetricTestResult(SchemaBase):
    success: bool = Field(title="是否成功")
    sql: str = Field(title="实际执行的 SQL")
    row_count: int = Field(title="返回行数")
    elapsed_ms: int = Field(title="耗时毫秒")
    error: str | None = Field(None, title="错误信息")


# ============================================================
# conversation：BiChatSession / BiChatMessage
# ============================================================


class BiChatSessionBase(SchemaBase):
    title: str | None = Field(None, title="会话标题")


class BiChatSessionCreate(SchemaBase):
    title: str = Field("新对话", title="会话标题")


BiChatSessionUpdate = make_optional(BiChatSessionCreate, "BiChatSessionUpdate")


class BiChatSessionSearch(PageQueryBase):
    title: str | None = Field(None, title="标题（模糊）")


class BiChatSessionOut(SchemaBase):
    id: str | None = Field(None, title="会话ID（sqid）")
    title: str | None = Field(None, title="会话标题")
    user_id: str | None = Field(None, title="创建用户ID（sqid）")
    last_message_at: datetime | None = Field(None, title="最后消息时间")
    tenant_id: int | None = Field(None, title="租户ID")


class BiChatMessageSearch(PageQueryBase):
    session_id: str | None = Field(None, title="会话ID（sqid）")
    role: str | None = Field(None, title="角色")
    status: str | None = Field(None, title="状态")


class BiChatMessageOut(SchemaBase):
    id: str | None = Field(None, title="消息ID（sqid）")
    session_id: str | None = Field(None, title="会话ID（sqid）")
    role: str | None = Field(None, title="角色")
    content: str | None = Field(None, title="消息内容")
    sql_text: str | None = Field(None, title="生成的 SQL")
    sql_result: dict | None = Field(None, title="SQL 执行结果")
    agent_steps_json: list | None = Field(None, title="Agent 流水线步骤留痕")
    intent_type: str | None = Field(None, title="意图类型")
    execution_time_ms: int | None = Field(None, title="执行耗时（毫秒）")
    token_usage: dict | None = Field(None, title="Token 用量")
    status: str | None = Field(None, title="状态")
    error_message: str | None = Field(None, title="错误信息")
    created_at: datetime | None = Field(None, title="创建时间")


class ChatSendSchema(SchemaBase):
    """发送对话消息请求（Task 23 命名规范，与 ChatSendRequest 等价）。"""

    session_id: str | None = Field(None, title="会话ID（sqid，None 创建新会话）")
    question: str = Field(title="用户问题")
    datasource_id: str | None = Field(None, title="数据源ID（sqid，None 用默认）")


# 兼容别名：早期文档使用 ChatSendRequest
ChatSendRequest = ChatSendSchema


# ============================================================
# llm：BiLLMProvider / BiLLMModel
# ============================================================


class BiLLMProviderBase(SchemaBase):
    name: str | None = Field(None, title="Provider 名称")
    provider_type: str | None = Field(None, title="Provider 类型", description="deepseek/ollama/qwen/openai/mock/custom")
    base_url: str | None = Field(None, title="Base URL")
    default_model: str | None = Field(None, title="默认模型名")
    is_default: bool | None = Field(None, title="是否默认 Provider")
    status_type: StatusType | None = Field(None, title="状态")
    extra_config: dict | None = Field(None, title="额外配置")


class BiLLMProviderCreate(BiLLMProviderBase):
    name: str = Field(title="Provider 名称")
    provider_type: str = Field(title="Provider 类型")
    api_key: str = Field(title="API Key（明文，后端 Fernet 加密存储）")


BiLLMProviderUpdate = make_optional(BiLLMProviderCreate, "BiLLMProviderUpdate")
BiLLMProviderUpdate.model_fields["api_key"].default = None
BiLLMProviderUpdate.model_rebuild(force=True)


class BiLLMProviderSearch(BiLLMProviderBase, PageQueryBase):
    pass  # type: ignore[misc]


class BiLLMProviderOut(SchemaBase):
    """Provider 响应（不返回 api_key 明文）。"""

    id: str | None = Field(None, title="ProviderID（sqid）")
    name: str | None = Field(None, title="Provider 名称")
    provider_type: str | None = Field(None, title="Provider 类型")
    base_url: str | None = Field(None, title="Base URL")
    default_model: str | None = Field(None, title="默认模型名")
    is_default: bool | None = Field(None, title="是否默认 Provider")
    status_type: StatusType | None = Field(None, title="状态")
    extra_config: dict | None = Field(None, title="额外配置")
    api_key: str | None = Field("***", title="API Key（脱敏占位符）")


class BiLLMProviderTestResult(SchemaBase):
    success: bool = Field(title="是否成功")
    message: str = Field(title="结果消息")
    model_name: str | None = Field(None, title="测试用模型名")
    elapsed_ms: int = Field(title="耗时毫秒")


class BiLLMModelBase(SchemaBase):
    name: str | None = Field(None, title="模型名")
    display_name: str | None = Field(None, title="展示名")
    context_length: int | None = Field(None, title="上下文长度")
    order: int | None = Field(None, title="排序")
    is_active: bool | None = Field(None, title="是否启用")


class BiLLMModelCreate(BiLLMModelBase):
    name: str = Field(title="模型名")
    provider_id: str = Field(title="所属 Provider ID（sqid）")


BiLLMModelUpdate = make_optional(BiLLMModelCreate, "BiLLMModelUpdate")


class BiLLMModelSearch(BiLLMModelBase, PageQueryBase):
    provider_id: str | None = Field(None, title="Provider ID（sqid）")  # type: ignore[assignment]


class BiLLMModelOut(SchemaBase):
    id: str | None = Field(None, title="模型ID（sqid）")
    provider_id: str | None = Field(None, title="ProviderID（sqid）")
    name: str | None = Field(None, title="模型名")
    display_name: str | None = Field(None, title="展示名")
    context_length: int | None = Field(None, title="上下文长度")
    order: int | None = Field(None, title="排序")
    is_active: bool | None = Field(None, title="是否启用")


# ============================================================
# audit：BiAuditLog（只读）
# ============================================================


class BiAuditLogSearch(PageQueryBase):
    event_type: str | None = Field(None, title="事件类型")
    action: str | None = Field(None, title="具体操作（模糊）")
    user_id: str | None = Field(None, title="操作用户ID（sqid）")
    username: str | None = Field(None, title="操作用户名（模糊）")
    status: str | None = Field(None, title="状态")
    resource_type: str | None = Field(None, title="资源类型")
    created_at_start: datetime | None = Field(None, title="创建时间起始")
    created_at_end: datetime | None = Field(None, title="创建时间结束")


# 兼容别名：审计搜索 schema
AuditSearchSchema = BiAuditLogSearch


class BiAuditLogOut(SchemaBase):
    id: str | None = Field(None, title="日志ID（sqid）")
    trace_id: str | None = Field(None, title="链路追踪 ID")
    event_type: str | None = Field(None, title="事件类型")
    action: str | None = Field(None, title="具体操作")
    user_id: str | None = Field(None, title="操作用户ID（sqid）")
    username: str | None = Field(None, title="操作用户名")
    ip_address: str | None = Field(None, title="IP 地址")
    resource_type: str | None = Field(None, title="资源类型")
    resource_id: str | None = Field(None, title="资源ID")
    detail: dict | None = Field(None, title="详细信息")
    status: str | None = Field(None, title="状态")
    error_message: str | None = Field(None, title="错误信息")
    execution_time_ms: int | None = Field(None, title="执行耗时（毫秒）")
    created_at: datetime | None = Field(None, title="创建时间")


class BiAuditStatisticsRequest(SchemaBase):
    start_date: datetime | None = Field(None, title="起始时间")
    end_date: datetime | None = Field(None, title="结束时间")


class BiAuditStatistics(SchemaBase):
    total: int = Field(0, title="日志总数")
    success_count: int = Field(0, title="成功数")
    failed_count: int = Field(0, title="失败数")
    by_event_type: dict[str, int] = Field(default_factory=dict, title="按事件类型分组")
    by_action: dict[str, int] = Field(default_factory=dict, title="按操作分组")
    by_user: dict[str, int] = Field(default_factory=dict, title="按用户分组")


# ============================================================
# security：BiMaskingRule / BiQuotaConfig
# ============================================================


class BiMaskingRuleBase(SchemaBase):
    name: str | None = Field(None, title="规则名称")
    column_pattern: str | None = Field(None, title="列名匹配模式（正则）")
    mask_type: str | None = Field(None, title="脱敏类型", description="phone/idcard/email/bankcard/custom")
    mask_char: str | None = Field(None, title="脱敏占位字符")
    keep_prefix: int | None = Field(None, title="保留前缀位数")
    keep_suffix: int | None = Field(None, title="保留后缀位数")
    status_type: StatusType | None = Field(None, title="状态")


class BiMaskingRuleCreate(BiMaskingRuleBase):
    name: str = Field(title="规则名称")
    column_pattern: str = Field(title="列名匹配模式")
    mask_type: str = Field(title="脱敏类型")


BiMaskingRuleUpdate = make_optional(BiMaskingRuleCreate, "BiMaskingRuleUpdate")


class BiMaskingRuleSearch(BiMaskingRuleBase, PageQueryBase):
    pass  # type: ignore[misc]


class BiMaskingRuleOut(SchemaBase):
    id: str | None = Field(None, title="规则ID（sqid）")
    name: str | None = Field(None, title="规则名称")
    column_pattern: str | None = Field(None, title="列名匹配模式")
    mask_type: str | None = Field(None, title="脱敏类型")
    mask_char: str | None = Field(None, title="脱敏占位字符")
    keep_prefix: int | None = Field(None, title="保留前缀位数")
    keep_suffix: int | None = Field(None, title="保留后缀位数")
    status_type: StatusType | None = Field(None, title="状态")


class BiQuotaConfigBase(SchemaBase):
    name: str | None = Field(None, title="配置名称")
    max_rows: int | None = Field(None, title="最大行数")
    timeout_seconds: int | None = Field(None, title="超时秒数")
    breaker_threshold: int | None = Field(None, title="熔断阈值")
    breaker_window_seconds: int | None = Field(None, title="熔断窗口秒数")
    scope_type: str | None = Field(None, title="作用域类型", description="global/user/datasource")
    scope_id: int | None = Field(None, title="作用域ID")
    status_type: StatusType | None = Field(None, title="状态")


class BiQuotaConfigCreate(BiQuotaConfigBase):
    name: str = Field(title="配置名称")
    scope_type: str = Field(title="作用域类型")


BiQuotaConfigUpdate = make_optional(BiQuotaConfigCreate, "BiQuotaConfigUpdate")


class BiQuotaConfigSearch(BiQuotaConfigBase, PageQueryBase):
    pass  # type: ignore[misc]


class BiQuotaConfigOut(SchemaBase):
    id: str | None = Field(None, title="配置ID（sqid）")
    name: str | None = Field(None, title="配置名称")
    max_rows: int | None = Field(None, title="最大行数")
    timeout_seconds: int | None = Field(None, title="超时秒数")
    breaker_threshold: int | None = Field(None, title="熔断阈值")
    breaker_window_seconds: int | None = Field(None, title="熔断窗口秒数")
    scope_type: str | None = Field(None, title="作用域类型")
    scope_id: int | None = Field(None, title="作用域ID")
    status_type: StatusType | None = Field(None, title="状态")


# ============================================================
# SQL 工作台请求 schema
# ============================================================


class SqlRunSchema(SchemaBase):
    """执行 SQL 请求（Task 23 命名规范，与 SqlRunRequest 等价）。"""

    sql: str = Field(title="要执行的 SQL")
    datasource_id: str = Field(title="数据源ID（sqid）")


# 兼容别名
SqlRunRequest = SqlRunSchema


class DatasourceTestSchema(SchemaBase):
    """数据源测试请求（可选 schema，用于显式测试入口）。"""

    datasource_id: str = Field(title="数据源ID（sqid）")


class SqlExplainRequest(SchemaBase):
    sql: str = Field(title="要解释的 SQL")
    dialect: str = Field("sqlite", title="方言")


class SqlFormatRequest(SchemaBase):
    sql: str = Field(title="要格式化的 SQL")


class SqlRunResult(SchemaBase):
    """SQL 执行结果。"""

    sql: str | None = Field(None, title="实际执行的 SQL（含自动 LIMIT）")
    columns: list[str] = Field(default_factory=list, title="列名")
    rows: list[dict] = Field(default_factory=list, title="数据行")
    row_count: int = Field(0, title="返回行数")
    elapsed_ms: int = Field(0, title="耗时毫秒")
