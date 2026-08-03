# pyright: reportIncompatibleVariableOverride=false
"""BI 智能数据分析模块 Tortoise ORM 模型。

13 个模型，表名统一 ``biz_bi_*`` 前缀：

- metadata：BiDatasource / BiTable / BiColumn / BiIndex / BiForeignKey
- semantic：BiMetric
- conversation：BiChatSession / BiChatMessage
- llm：BiLLMProvider / BiLLMModel
- audit：BiAuditLog
- security：BiMaskingRule / BiQuotaConfig

FK 关联引用本模块内模型时使用 ``app_system.<Model>`` 字符串
（业务模块默认注册到 ``app_system`` app label，与 ``app/system`` 共享连接）。
"""

from tortoise import fields

from app.utils import AuditMixin, BaseModel, SoftDeleteManager, SoftDeleteMixin, StatusType

# ==================== metadata 子模块 ====================


class BiDatasource(BaseModel, AuditMixin, SoftDeleteMixin):
    """数据源配置"""

    id = fields.IntField(primary_key=True, description="主键ID")
    name = fields.CharField(max_length=100, description="数据源名称")
    db_type = fields.CharField(max_length=20, description="数据库类型（postgresql/mysql/clickhouse/trino/sqlite）")
    host = fields.CharField(max_length=200, description="主机地址")
    port = fields.SmallIntField(description="端口")
    username = fields.CharField(max_length=100, description="用户名")
    password = fields.CharField(max_length=500, description="密码（Fernet 加密存储）")
    database = fields.CharField(max_length=200, description="数据库名")
    extra_params = fields.JSONField(null=True, description="额外连接参数")
    status_type = fields.CharEnumField(enum_type=StatusType, default=StatusType.enable, description="状态")
    last_synced_at = fields.DatetimeField(null=True, description="最后同步时间")
    tenant_id = fields.IntField(default=0, description="租户ID（行级 data_scope 作用域）")

    class Meta:
        table = "biz_bi_datasource"
        manager = SoftDeleteManager()


class BiTable(BaseModel, AuditMixin):
    """表元数据"""

    id = fields.IntField(primary_key=True, description="主键ID")
    datasource_id: int
    datasource: fields.ForeignKeyRelation[BiDatasource] = fields.ForeignKeyField("app_system.BiDatasource", related_name="tables", on_delete=fields.CASCADE, description="所属数据源")
    name = fields.CharField(max_length=200, description="表名")
    comment = fields.CharField(max_length=500, null=True, blank=True, description="表注释")
    row_count = fields.BigIntField(default=0, description="行数")
    # 注：源表创建/更新时间用 source_ 前缀，避免与 AuditMixin 的 created_at / updated_at 冲突
    source_created_at = fields.DatetimeField(null=True, description="源表创建时间")
    source_updated_at = fields.DatetimeField(null=True, description="源表更新时间")

    class Meta:
        table = "biz_bi_table"


class BiColumn(BaseModel, AuditMixin):
    """列元数据"""

    id = fields.IntField(primary_key=True, description="主键ID")
    table_id: int
    table: fields.ForeignKeyRelation[BiTable] = fields.ForeignKeyField("app_system.BiTable", related_name="columns", on_delete=fields.CASCADE, description="所属表")
    name = fields.CharField(max_length=200, description="列名")
    data_type = fields.CharField(max_length=100, description="数据类型")
    is_primary = fields.BooleanField(default=False, description="是否主键")
    is_nullable = fields.BooleanField(default=True, description="是否可空")
    default_value = fields.CharField(max_length=200, null=True, blank=True, description="默认值")
    comment = fields.CharField(max_length=500, null=True, blank=True, description="列注释")
    sample_values = fields.JSONField(null=True, description="采样值")

    class Meta:
        table = "biz_bi_column"


class BiIndex(BaseModel, AuditMixin):
    """索引元数据"""

    id = fields.IntField(primary_key=True, description="主键ID")
    table_id: int
    table: fields.ForeignKeyRelation[BiTable] = fields.ForeignKeyField("app_system.BiTable", related_name="indexes", on_delete=fields.CASCADE, description="所属表")
    name = fields.CharField(max_length=200, description="索引名")
    index_type = fields.CharField(max_length=50, description="索引类型")
    columns = fields.JSONField(description="包含的列数组")
    is_unique = fields.BooleanField(default=False, description="是否唯一索引")

    class Meta:
        table = "biz_bi_index"


class BiForeignKey(BaseModel, AuditMixin):
    """外键关系元数据"""

    id = fields.IntField(primary_key=True, description="主键ID")
    table_id: int
    table: fields.ForeignKeyRelation[BiTable] = fields.ForeignKeyField("app_system.BiTable", related_name="foreign_keys", on_delete=fields.CASCADE, description="所属表")
    name = fields.CharField(max_length=200, description="外键名")
    column_name = fields.CharField(max_length=200, description="源列名")
    ref_table = fields.CharField(max_length=200, description="目标表名")
    ref_column = fields.CharField(max_length=200, description="目标列名")

    class Meta:
        table = "biz_bi_foreign_key"


# ==================== semantic 子模块 ====================


class BiMetric(BaseModel, AuditMixin):
    """指标定义"""

    id = fields.IntField(primary_key=True, description="主键ID")
    name = fields.CharField(max_length=100, description="指标名称")
    code = fields.CharField(max_length=50, unique=True, description="指标编码")
    description = fields.TextField(null=True, blank=True, description="指标描述")
    datasource_id: int
    datasource: fields.ForeignKeyRelation[BiDatasource] = fields.ForeignKeyField("app_system.BiDatasource", related_name="metrics", on_delete=fields.CASCADE, description="所属数据源")
    sql_template = fields.TextField(description="SQL 模板（含 {xxx} 占位符）")
    chart_type = fields.CharField(max_length=50, null=True, blank=True, description="推荐图表类型")
    status_type = fields.CharEnumField(enum_type=StatusType, default=StatusType.enable, description="状态")

    class Meta:
        table = "biz_bi_metric"


# ==================== conversation 子模块 ====================


class BiChatSession(BaseModel, AuditMixin):
    """对话会话"""

    id = fields.IntField(primary_key=True, description="主键ID")
    title = fields.CharField(max_length=200, description="会话标题")
    user_id = fields.IntField(description="创建用户ID")
    last_message_at = fields.DatetimeField(null=True, description="最后消息时间")
    tenant_id = fields.IntField(default=0, description="租户ID（行级 data_scope 作用域）")

    class Meta:
        table = "biz_bi_chat_session"


class BiChatMessage(BaseModel, AuditMixin):
    """对话消息"""

    id = fields.IntField(primary_key=True, description="主键ID")
    session_id: int
    session: fields.ForeignKeyRelation[BiChatSession] = fields.ForeignKeyField("app_system.BiChatSession", related_name="messages", on_delete=fields.CASCADE, description="所属会话")
    role = fields.CharField(max_length=20, description="角色（user/assistant/system）")
    content = fields.TextField(description="消息内容")
    sql_text = fields.TextField(null=True, blank=True, description="生成的 SQL")
    sql_result = fields.JSONField(null=True, description="SQL 执行结果")
    agent_steps_json = fields.JSONField(null=True, description="Agent 流水线步骤留痕")
    intent_type = fields.CharField(max_length=50, null=True, blank=True, description="意图类型")
    execution_time_ms = fields.IntField(default=0, description="执行耗时（毫秒）")
    token_usage = fields.JSONField(null=True, description="Token 用量")
    status = fields.CharField(max_length=20, description="状态（success/failed）")
    error_message = fields.TextField(null=True, blank=True, description="错误信息")

    class Meta:
        table = "biz_bi_chat_message"


# ==================== llm 子模块 ====================


class BiLLMProvider(BaseModel, AuditMixin):
    """LLM Provider 配置"""

    id = fields.IntField(primary_key=True, description="主键ID")
    name = fields.CharField(max_length=100, description="Provider 名称")
    provider_type = fields.CharField(max_length=20, description="Provider 类型（deepseek/ollama/qwen/openai/mock/custom）")
    api_key = fields.CharField(max_length=500, description="API Key（Fernet 加密存储）")
    base_url = fields.CharField(max_length=500, null=True, blank=True, description="Base URL")
    default_model = fields.CharField(max_length=100, null=True, blank=True, description="默认模型名")
    is_default = fields.BooleanField(default=False, description="是否默认 Provider")
    status_type = fields.CharEnumField(enum_type=StatusType, default=StatusType.enable, description="状态")
    extra_config = fields.JSONField(null=True, description="额外配置（Temperature/Max Tokens/Top P 等）")

    class Meta:
        table = "biz_bi_llm_provider"


class BiLLMModel(BaseModel, AuditMixin):
    """LLM 模型配置"""

    id = fields.IntField(primary_key=True, description="主键ID")
    provider_id: int
    provider: fields.ForeignKeyRelation[BiLLMProvider] = fields.ForeignKeyField("app_system.BiLLMProvider", related_name="models", on_delete=fields.CASCADE, description="所属 Provider")
    name = fields.CharField(max_length=100, description="模型名（如 deepseek-chat）")
    display_name = fields.CharField(max_length=200, null=True, blank=True, description="展示名")
    context_length = fields.IntField(default=4096, description="上下文长度")
    order = fields.SmallIntField(default=0, description="排序")
    is_active = fields.BooleanField(default=True, description="是否启用")

    class Meta:
        table = "biz_bi_llm_model"


# ==================== audit 子模块 ====================


class BiAuditLog(BaseModel, AuditMixin):
    """BI 审计日志

    ``created_at`` 由 ``AuditMixin`` 提供（``auto_now_add=True``），
    不在此重复声明。
    """

    id = fields.IntField(primary_key=True, description="主键ID")
    trace_id = fields.CharField(max_length=100, null=True, blank=True, description="链路追踪 ID")
    event_type = fields.CharField(
        max_length=50,
        description="事件类型（USER_BEHAVIOR/QUERY_OPERATION/SYSTEM_OPERATION/PERMISSION_CHANGE/BUTTON_CLICK）",
    )
    action = fields.CharField(max_length=100, description="具体操作")
    user_id = fields.BigIntField(null=True, description="操作用户ID")
    username = fields.CharField(max_length=100, null=True, blank=True, description="操作用户名")
    ip_address = fields.CharField(max_length=50, null=True, blank=True, description="IP 地址")
    resource_type = fields.CharField(max_length=50, null=True, blank=True, description="资源类型")
    resource_id = fields.CharField(max_length=100, null=True, blank=True, description="资源ID")
    detail = fields.JSONField(null=True, description="详细信息")
    status = fields.CharField(max_length=20, description="状态（success/failed）")
    error_message = fields.TextField(null=True, blank=True, description="错误信息")
    execution_time_ms = fields.IntField(default=0, description="执行耗时（毫秒）")

    class Meta:
        table = "biz_bi_audit_log"


# ==================== security 子模块 ====================


class BiMaskingRule(BaseModel, AuditMixin):
    """列脱敏规则"""

    id = fields.IntField(primary_key=True, description="主键ID")
    name = fields.CharField(max_length=100, description="规则名称")
    column_pattern = fields.CharField(max_length=200, description="列名匹配模式（支持正则）")
    mask_type = fields.CharField(max_length=20, description="脱敏类型（phone/idcard/email/bankcard/custom）")
    mask_char = fields.CharField(max_length=10, default="*", description="脱敏占位字符")
    keep_prefix = fields.SmallIntField(default=0, description="保留前缀位数")
    keep_suffix = fields.SmallIntField(default=0, description="保留后缀位数")
    status_type = fields.CharEnumField(enum_type=StatusType, default=StatusType.enable, description="状态")

    class Meta:
        table = "biz_bi_masking_rule"


class BiQuotaConfig(BaseModel, AuditMixin):
    """配额配置"""

    id = fields.IntField(primary_key=True, description="主键ID")
    name = fields.CharField(max_length=100, description="配置名称")
    max_rows = fields.IntField(default=10000, description="最大行数")
    timeout_seconds = fields.IntField(default=30, description="超时秒数")
    breaker_threshold = fields.SmallIntField(default=10, description="熔断阈值")
    breaker_window_seconds = fields.IntField(default=60, description="熔断窗口秒数")
    scope_type = fields.CharField(max_length=20, description="作用域类型（global/user/datasource）")
    scope_id = fields.BigIntField(null=True, description="作用域ID")
    status_type = fields.CharEnumField(enum_type=StatusType, default=StatusType.enable, description="状态")

    class Meta:
        table = "biz_bi_quota_config"


# ==================== chart 子模块 ====================


class BiChart(BaseModel, AuditMixin, SoftDeleteMixin):
    """保存的图表（可来自对话或 SQL 工作台）。

    把会话/工作台里的临时图表变成可复用资产：支持列表、刷新、分享。
    ``result_snapshot`` 与 ``BiChatMessage.sql_result`` 结构一致，
    刷新失败时前端可降级显示快照。
    """

    id = fields.IntField(primary_key=True, description="主键ID")
    name = fields.CharField(max_length=100, description="图表标题")
    description = fields.TextField(null=True, blank=True, description="图表说明")
    datasource_id: int
    datasource: fields.ForeignKeyRelation[BiDatasource] = fields.ForeignKeyField(
        "app_system.BiDatasource",
        related_name="charts",
        on_delete=fields.CASCADE,
        description="所属数据源",
    )
    chart_type = fields.CharField(max_length=20, description="图表类型：bar/line/pie/scatter/area/radar/funnel/gauge/heatmap")
    x_col = fields.CharField(max_length=100, null=True, blank=True, description="X 轴字段名")
    y_col = fields.CharField(max_length=100, null=True, blank=True, description="Y 轴字段名")
    sql_text = fields.TextField(description="来源 SQL（用于刷新数据）")
    # 结果快照：结构 {columns, rows, rowCount, elapsedMs, isTruncated}
    # 保存时最多保留前 BI_CHART_SNAPSHOT_MAX_ROWS 行（默认 1000）
    result_snapshot = fields.JSONField(description="结果快照（最多 1000 行）")
    tags = fields.CharField(max_length=500, null=True, blank=True, description="标签（逗号分隔，如 销售,月报）")
    is_public = fields.BooleanField(default=False, description="是否开启外部分享")
    share_token = fields.CharField(max_length=32, null=True, blank=True, unique=True, description="外部分享 token（sqid 编码）")
    snapshot_at = fields.DatetimeField(description="结果快照的生成时间")
    tenant_id = fields.IntField(default=0, description="租户ID（行级 data_scope 作用域）")

    class Meta:
        table = "biz_bi_chart"
        manager = SoftDeleteManager()


# ==================== async query 子模块 ====================


class BiQueryTask(BaseModel, AuditMixin, SoftDeleteMixin):
    """异步查询任务。

    记录一次异步 SQL 执行的完整生命周期：提交 → 运行 → 完成/失败/取消。
    小结果（≤ ``BI_ASYNC_QUERY_PREVIEW_ROWS``）直接存 ``result_snapshot`` JSONField；
    大结果落 CSV 到 ``BI_ASYNC_QUERY_CSV_DIR``，``result_uri`` 存相对路径。

    行级隔离：``tenant_id`` 存 ``user.id``（与 BiChart / BiChatSession 一致）。
    """

    id = fields.IntField(primary_key=True, description="主键ID")
    name = fields.CharField(max_length=100, null=True, blank=True, description="任务名称（可选，默认自动生成）")
    datasource_id: int
    datasource: fields.ForeignKeyRelation[BiDatasource] = fields.ForeignKeyField(
        "app_system.BiDatasource",
        related_name="query_tasks",
        on_delete=fields.CASCADE,
        description="所属数据源",
    )
    sql_text = fields.TextField(description="来源 SQL（提交时已过白名单校验）")
    # 实时状态在 Redis Hash，这里存最终快照（runner 完成时回写）
    status = fields.CharField(max_length=20, default="pending", description="任务状态：pending/running/success/failed/cancelled")
    progress = fields.IntField(default=0, description="进度百分比 0-100")
    rows_fetched = fields.IntField(default=0, description="已扫描行数")
    elapsed_ms = fields.IntField(default=0, description="执行耗时（毫秒）")
    # 结果存储
    result_snapshot = fields.JSONField(null=True, description="结果预览（≤1万行，结构 {columns, rows, rowCount, elapsedMs, isTruncated}）")
    result_uri = fields.CharField(max_length=255, null=True, description="CSV 文件相对路径（大结果时）")
    result_row_count = fields.IntField(default=0, description="结果总行数")
    result_is_truncated = fields.BooleanField(default=False, description="结果是否被截断（仅预览截断，CSV 完整）")
    # 错误
    error_message = fields.TextField(null=True, description="失败/取消原因")
    # 时间
    started_at = fields.DatetimeField(null=True, description="开始执行时间")
    finished_at = fields.DatetimeField(null=True, description="完成/失败/取消时间")
    # 行级隔离
    tenant_id = fields.IntField(default=0, description="租户ID（行级 data_scope 作用域，存 user.id）")
    # 来源
    source = fields.CharField(max_length=20, default="manual", description="提交来源：manual（手动）/ auto_transfer（同步软超时转异步）")

    class Meta:
        table = "biz_bi_query_task"
        manager = SoftDeleteManager()
        indexes = [
            ("tenant_id", "status"),
            ("tenant_id", "created_at"),
        ]


# ==================== dashboard 子模块 ====================


class BiDashboard(BaseModel, AuditMixin, SoftDeleteMixin):
    """仪表盘：把多个 BiChart 组装成 12 列栅格布局。

    ``layout`` 存 ``{"items": [{chartId, x, y, w, h}]}``，引用 BiChart（不级联删）。
    打开时全量刷新所有图表数据，失败的卡片显示占位。
    """

    id = fields.IntField(primary_key=True, description="主键ID")
    name = fields.CharField(max_length=100, description="仪表盘名称")
    description = fields.TextField(null=True, blank=True, description="说明")
    # 布局：{items: [{chartId, x, y, w, h}]}，chartId 为 BiChart 的 SQID 编码字符串
    layout = fields.JSONField(default={"items": []}, description="布局：{items: [{chartId, x, y, w, h}]}")
    tenant_id = fields.IntField(default=0, description="租户ID（行级 data_scope 作用域，存 user.id）")

    class Meta:
        table = "biz_bi_dashboard"
        manager = SoftDeleteManager()
        indexes = [
            ("tenant_id", "created_at"),
        ]
