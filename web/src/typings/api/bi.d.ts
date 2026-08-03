declare namespace Api {
  /**
   * namespace Bi
   *
   * backend api module: "bi" — 智能数据分析模块
   *
   * 类型字段命名遵循 camelCase（由后端 ``BaseModel.to_dict`` 自动转换）；
   * 所有 ``id`` / ``*_id`` 字段后端通过 sqid 编码为字符串。
   */
  namespace Bi {
    type CommonSearchParams = Pick<Common.PaginatingCommonParams, 'current' | 'size'>;

    /** common delete params */
    type CommonDeleteParams = { id: string };

    /** common batch delete params */
    type CommonBatchDeleteParams = { ids: string[] };

    /** common create result */
    type CreateResult = { createdId: string };

    /** common update result */
    type UpdateResult = { updatedId: string };

    /** common delete result */
    type DeleteResult = { deletedId: string };

    // ============================================================
    // Datasource（数据源）
    // ============================================================

    /** 数据源类型，对应后端 db_type 字段 */
    type DatasourceType = 'postgresql' | 'mysql' | 'clickhouse' | 'trino' | 'sqlite';

    type BiDatasource = Common.CommonRecord<{
      /** 数据源名称 */
      name: string;
      /** 数据库类型 */
      dbType: DatasourceType;
      /** 主机地址 */
      host: string;
      /** 端口 */
      port: number;
      /** 用户名 */
      username: string;
      /** 密码（脱敏占位符 ***，仅创建/更新时传明文） */
      password: string;
      /** 数据库名 */
      database: string;
      /** 额外连接参数 */
      extraParams: Record<string, any> | null;
      /** 租户 ID（行级 data_scope 作用域） */
      tenantId: number;
      /** 最后同步时间（毫秒时间戳） */
      lastSyncedAt: number | null;
      /** 格式化的最后同步时间 */
      fmtLastSyncedAt?: string | null;
    }>;

    type BiDatasourceSearchParams = CommonType.RecordNullable<
      {
        name?: string;
        dbType?: DatasourceType;
        statusType?: Common.EnableStatus;
      } & CommonSearchParams
    >;

    type BiDatasourceList = Common.PaginatingQueryRecord<BiDatasource>;

    type BiDatasourceOperateParams = {
      id?: string;
      name: string;
      dbType: DatasourceType;
      host: string;
      port: number;
      username: string;
      /** 创建时必填（明文，后端 Fernet 加密存储），更新时可选 */
      password?: string;
      database: string;
      extraParams?: Record<string, any> | null;
      statusType?: Common.EnableStatus;
    };

    /** 数据源连接测试结果 */
    type BiDatasourceTestResult = {
      success: boolean;
      message: string;
      elapsedMs: number;
    };

    /** 数据源元数据同步结果 */
    type BiSyncResult = {
      datasourceId: string;
      tablesSynced: number;
      columnsSynced: number;
      indexesSynced: number;
      foreignKeysSynced: number;
      elapsedMs: number;
      errors: string[];
    };

    // ============================================================
    // Metadata（表 / 列 / 索引 / 外键 — 只读）
    // ============================================================

    type BiTable = Common.CommonRecord<{
      /** 所属数据源 ID（sqid） */
      datasourceId: string;
      /** 表名 */
      name: string;
      /** 表注释 */
      comment: string | null;
      /** 行数 */
      rowCount: number;
      /** 源表创建时间（毫秒时间戳） */
      sourceCreatedAt: number | null;
      /** 源表更新时间（毫秒时间戳） */
      sourceUpdatedAt: number | null;
    }>;

    type BiColumn = Common.CommonRecord<{
      /** 所属表 ID（sqid） */
      tableId: string;
      /** 列名 */
      name: string;
      /** 数据类型 */
      dataType: string;
      /** 是否主键 */
      isPrimary: boolean;
      /** 是否可空 */
      isNullable: boolean;
      /** 默认值 */
      defaultValue: string | null;
      /** 列注释 */
      comment: string | null;
      /** 采样值 */
      sampleValues: any[] | null;
    }>;

    type BiIndex = Common.CommonRecord<{
      /** 所属表 ID（sqid） */
      tableId: string;
      /** 索引名 */
      name: string;
      /** 索引类型 */
      indexType: string;
      /** 包含的列数组 */
      columns: string[];
      /** 是否唯一索引 */
      isUnique: boolean;
    }>;

    type BiForeignKey = Common.CommonRecord<{
      /** 所属表 ID（sqid） */
      tableId: string;
      /** 外键名 */
      name: string;
      /** 源列名 */
      columnName: string;
      /** 目标表名 */
      refTable: string;
      /** 目标列名 */
      refColumn: string;
    }>;

    /** 表详情（含列 / 索引 / 外键聚合） */
    type BiTableDetail = BiTable & {
      columns: BiColumn[];
      indexes: BiIndex[];
      foreignKeys: BiForeignKey[];
    };

    type BiTableSearchParams = CommonType.RecordNullable<
      {
        datasourceId?: string;
        name?: string;
      } & CommonSearchParams
    >;

    type BiTableList = Common.PaginatingQueryRecord<BiTable>;

    type BiColumnSearchParams = CommonType.RecordNullable<
      {
        tableId?: string;
        name?: string;
      } & CommonSearchParams
    >;

    type BiColumnList = Common.PaginatingQueryRecord<BiColumn>;

    // ============================================================
    // Metric（指标）
    // ============================================================

    type BiMetric = Common.CommonRecord<{
      /** 指标名称 */
      name: string;
      /** 指标编码 */
      code: string;
      /** 指标描述 */
      description: string | null;
      /** 所属数据源 ID（sqid） */
      datasourceId: string;
      /** SQL 模板（含 {xxx} 占位符） */
      sqlTemplate: string;
      /** 推荐图表类型 */
      chartType: string | null;
    }>;

    type BiMetricSearchParams = CommonType.RecordNullable<
      {
        name?: string;
        code?: string;
        datasourceId?: string;
        statusType?: Common.EnableStatus;
      } & CommonSearchParams
    >;

    type BiMetricList = Common.PaginatingQueryRecord<BiMetric>;

    type BiMetricOperateParams = {
      id?: string;
      name: string;
      code: string;
      description?: string | null;
      datasourceId: string;
      sqlTemplate: string;
      chartType?: string | null;
      statusType?: Common.EnableStatus;
    };

    /** 指标测试结果（在绑定数据源上执行 SQL 模板） */
    type BiMetricTestResult = {
      success: boolean;
      sql: string;
      rowCount: number;
      elapsedMs: number;
      error: string | null;
    };

    // ============================================================
    // Chat（智能对话 — 会话 / 消息 / SSE 事件）
    // ============================================================

    /** 消息角色 */
    type ChatRole = 'user' | 'assistant' | 'system';

    /** 消息状态 */
    type ChatMessageStatus = 'success' | 'failed';

    type BiChatSession = Common.CommonRecord<{
      /** 会话标题 */
      title: string;
      /** 创建用户 ID（sqid） */
      userId: string;
      /** 最后消息时间（毫秒时间戳） */
      lastMessageAt: number | null;
      /** 租户 ID */
      tenantId: number;
    }>;

    /** SQL 执行结果（消息内嵌） */
    type ChatSqlResult = {
      rows: Record<string, any>[];
      columns: string[];
      elapsedMs: number;
      rowCount: number;
    };

    type BiChatMessage = Common.CommonRecord<{
      /** 所属会话 ID（sqid） */
      sessionId: string;
      /** 角色 */
      role: ChatRole;
      /** 消息内容 */
      content: string;
      /** 生成的 SQL */
      sqlText: string | null;
      /** SQL 执行结果 */
      sqlResult: ChatSqlResult | null;
      /** Agent 流水线步骤留痕 */
      agentStepsJson: any[] | null;
      /** 意图类型 */
      intentType: string | null;
      /** 执行耗时（毫秒） */
      executionTimeMs: number;
      /** Token 用量 */
      tokenUsage: Record<string, number> | null;
      /** 状态（success / failed） */
      status: ChatMessageStatus;
      /** 错误信息 */
      errorMessage: string | null;
    }>;

    type BiChatSessionSearchParams = CommonType.RecordNullable<
      {
        title?: string;
      } & CommonSearchParams
    >;

    type BiChatSessionList = Common.PaginatingQueryRecord<BiChatSession>;

    type BiChatMessageSearchParams = CommonType.RecordNullable<
      {
        sessionId?: string;
        role?: ChatRole;
        status?: ChatMessageStatus;
      } & CommonSearchParams
    >;

    type BiChatMessageList = Common.PaginatingQueryRecord<BiChatMessage>;

    /** 发送对话消息请求 */
    type ChatSendParams = {
      /** 用户问题 */
      question: string;
      /** 会话 ID（sqid，None 创建新会话） */
      sessionId?: string;
      /** 数据源 ID（sqid，None 用默认） */
      datasourceId?: string;
    };

    /** 创建会话请求 */
    type BiChatSessionCreateParams = {
      title?: string;
    };

    /** 修改会话请求 */
    type BiChatSessionUpdateParams = {
      title: string;
    };

    // ---- SSE 事件类型 ----

    /** Agent 单节点执行留痕事件 */
    type ChatStepEvent = {
      type: 'step';
      node: string;
      status: string;
      data: Record<string, any>;
      elapsedMs: number;
    };

    /** 流水线完成事件 */
    type ChatFinalEvent = {
      type: 'final';
      data: {
        sqlText: string;
        sqlResult: ChatSqlResult | null;
        explanation: string;
        chartType: string;
        steps: any[];
        tokenUsage: Record<string, number>;
        assistantMsgId: string;
        totalElapsedMs: number;
      };
    };

    /** 错误事件（流水线级或节点级错误，已持久化 assistant 失败消息） */
    type ChatErrorEvent = {
      type: 'error';
      node: string;
      error: string;
      elapsedMs?: number;
    };

    /** 心跳事件 */
    type ChatHeartbeatEvent = {
      type: 'heartbeat';
    };

    type ChatEvent = ChatStepEvent | ChatFinalEvent | ChatErrorEvent | ChatHeartbeatEvent;

    // ============================================================
    // LLM（Provider / Model）
    // ============================================================

    /** Provider 类型 */
    type LLMProviderType = 'deepseek' | 'ollama' | 'qwen' | 'openai' | 'mock' | 'custom';

    type BiLLMProvider = Common.CommonRecord<{
      /** Provider 名称 */
      name: string;
      /** Provider 类型 */
      providerType: LLMProviderType;
      /** API Key（脱敏占位符 ***，仅创建/更新时传明文） */
      apiKey: string;
      /** Base URL */
      baseUrl: string | null;
      /** 默认模型名 */
      defaultModel: string | null;
      /** 是否默认 Provider */
      isDefault: boolean;
      /** 额外配置（Temperature/Max Tokens/Top P 等） */
      extraConfig: Record<string, any> | null;
    }>;

    type BiLLMModel = Common.CommonRecord<{
      /** 所属 Provider ID（sqid） */
      providerId: string;
      /** 模型名 */
      name: string;
      /** 展示名 */
      displayName: string | null;
      /** 上下文长度 */
      contextLength: number;
      /** 排序 */
      order: number;
      /** 是否启用 */
      isActive: boolean;
    }>;

    type BiLLMProviderSearchParams = CommonType.RecordNullable<
      {
        name?: string;
        providerType?: LLMProviderType;
        statusType?: Common.EnableStatus;
        isDefault?: boolean;
      } & CommonSearchParams
    >;

    type BiLLMProviderList = Common.PaginatingQueryRecord<BiLLMProvider>;

    type BiLLMProviderOperateParams = {
      id?: string;
      name: string;
      providerType: LLMProviderType;
      /** 创建时必填（明文，后端 Fernet 加密存储），更新时可选 */
      apiKey?: string;
      baseUrl?: string | null;
      defaultModel?: string | null;
      isDefault?: boolean;
      statusType?: Common.EnableStatus;
      extraConfig?: Record<string, any> | null;
    };

    type BiLLMModelSearchParams = CommonType.RecordNullable<
      {
        providerId?: string;
        name?: string;
        displayName?: string;
        isActive?: boolean;
      } & CommonSearchParams
    >;

    type BiLLMModelList = Common.PaginatingQueryRecord<BiLLMModel>;

    type BiLLMModelOperateParams = {
      id?: string;
      name: string;
      providerId: string;
      displayName?: string | null;
      contextLength?: number;
      order?: number;
      isActive?: boolean;
    };

    /** Provider 测试结果 */
    type BiLLMTestResult = {
      success: boolean;
      message: string;
      modelName: string | null;
      elapsedMs: number;
    };

    // ============================================================
    // Audit（审计日志 — 只读）
    // ============================================================

    type BiAuditLog = Common.CommonRecord<{
      /** 链路追踪 ID */
      traceId: string | null;
      /** 事件类型 */
      eventType: string;
      /** 具体操作 */
      action: string;
      /** 操作用户 ID（sqid） */
      userId: string | null;
      /** 操作用户名 */
      username: string | null;
      /** IP 地址 */
      ipAddress: string | null;
      /** 资源类型 */
      resourceType: string | null;
      /** 资源 ID */
      resourceId: string | null;
      /** 详细信息 */
      detail: Record<string, any> | null;
      /** 状态 */
      status: string;
      /** 错误信息 */
      errorMessage: string | null;
      /** 执行耗时（毫秒） */
      executionTimeMs: number;
    }>;

    type BiAuditSearchParams = CommonType.RecordNullable<
      {
        eventType?: string;
        action?: string;
        userId?: string;
        username?: string;
        status?: string;
        resourceType?: string;
        createdAtStart?: number;
        createdAtEnd?: number;
      } & CommonSearchParams
    >;

    type BiAuditList = Common.PaginatingQueryRecord<BiAuditLog>;

    /** 审计统计请求 */
    type BiAuditStatsParams = {
      startDate?: number;
      endDate?: number;
    };

    /** 审计统计结果 */
    type BiAuditStats = {
      total: number;
      successCount: number;
      failedCount: number;
      byEventType: Record<string, number>;
      byAction: Record<string, number>;
      byUser: Record<string, number>;
    };

    // ============================================================
    // Security（脱敏规则 / 配额 — 类型预留）
    // ============================================================

    /** 脱敏类型 */
    type MaskType = 'phone' | 'idcard' | 'email' | 'bankcard' | 'custom';

    type BiMaskingRule = Common.CommonRecord<{
      name: string;
      columnPattern: string;
      maskType: MaskType;
      maskChar: string | null;
      keepPrefix: number;
      keepSuffix: number;
    }>;

    type BiQuotaConfig = Common.CommonRecord<{
      name: string;
      maxRows: number;
      timeoutSeconds: number;
      breakerThreshold: number;
      breakerWindowSeconds: number;
      scopeType: string;
      scopeId: number;
    }>;

    // ============================================================
    // SQL Workbench（SQL 工作台）
    // ============================================================

    /** 执行 SQL 请求 */
    type SqlRunParams = {
      sql: string;
      datasourceId: string;
    };

    /** SQL 执行结果 */
    type SqlExecutionResult = {
      sql: string;
      columns: string[];
      rows: Record<string, any>[];
      rowCount: number;
      elapsedMs: number;
    };

    /** 表预览结果（前 100 行） */
    type SqlPreviewResult = SqlExecutionResult;

    /** 生成 SELECT 语句结果 */
    type SqlGenerateSelectResult = {
      sql: string;
    };

    /** SQL 格式化请求 */
    type SqlFormatParams = {
      sql: string;
    };

    /** SQL 格式化结果 */
    type SqlFormatResult = {
      sql: string;
    };

    /** SQL 解析请求 */
    type SqlExplainParams = {
      sql: string;
      dialect?: string;
    };

    /** SQL 解析结果 */
    type SqlExplainResult = {
      sql: string;
      statements: Array<{
        type: string;
        sql: string;
      }>;
      error?: string;
    };

    // ============================================================
    // Chart（保存的图表）
    // ============================================================

    /** 图表结果快照（与 SqlExecutionResult 对齐，外加 isTruncated 标记） */
    type ChartResultSnapshot = {
      columns: string[];
      rows: Record<string, any>[];
      rowCount: number;
      elapsedMs: number;
      isTruncated?: boolean;
    };

    /** 保存的图表实体 */
    type BiChart = Common.CommonRecord<{
      /** 图表标题 */
      name: string;
      /** 图表说明 */
      description?: string | null;
      /** 所属数据源 ID（sqid） */
      datasourceId: string;
      /** 图表类型 */
      chartType: string;
      /** X 轴字段名 */
      xCol?: string | null;
      /** Y 轴字段名 */
      yCol?: string | null;
      /** 来源 SQL（用于刷新数据） */
      sqlText: string;
      /** 结果快照（最多 1000 行） */
      resultSnapshot: ChartResultSnapshot;
      /** 标签（逗号分隔） */
      tags?: string | null;
      /** 是否开启外部分享 */
      isPublic: boolean;
      /** 外部分享 token（sqid 编码） */
      shareToken?: string | null;
      /** 结果快照生成时间 */
      snapshotAt: string;
    }>;

    /** 图表分页搜索参数 */
    type BiChartSearchParams = CommonSearchParams & {
      /** 按名称模糊搜索 */
      name?: string;
      /** 按标签筛选（包含某个标签） */
      tags?: string;
      /** 按数据源筛选（sqid） */
      datasourceId?: string;
    };

    /** 图表分页列表 */
    type BiChartList = {
      records: BiChart[];
      total: number;
      current: number;
      size: number;
    };

    /** 创建/更新图表参数 */
    type BiChartOperateParams = {
      id?: string;
      name: string;
      description?: string | null;
      datasourceId: string;
      chartType: string;
      xCol?: string | null;
      yCol?: string | null;
      sqlText: string;
      resultSnapshot: ChartResultSnapshot;
      tags?: string | null;
      snapshotAt: string;
    };

    /** 图表刷新结果（返回完整图表） */
    type BiChartRefreshResult = BiChart;

    /** 开启分享结果 */
    type BiChartShareEnableResult = {
      shareToken: string;
    };

    /** 免登录查看分享图表响应（不含 sqlText） */
    type BiChartShared = {
      name: string;
      chartType: string;
      xCol?: string | null;
      yCol?: string | null;
      resultSnapshot: ChartResultSnapshot;
      snapshotAt: string;
    };

    /** 图表标签列表响应 */
    type BiChartTagsResult = {
      tags: string[];
    };

    // ============================================================
    // 异步大查询（BiQueryTask）
    // ============================================================

    /** 异步查询任务状态 */
    type BiQueryTaskStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled';

    /** 异步查询任务结果快照（结构同 SqlExecutionResult，外加 isTruncated） */
    type BiQueryTaskSnapshot = {
      columns: string[];
      rows: Record<string, any>[];
      rowCount: number;
      elapsedMs: number;
      isTruncated: boolean;
    };

    /** 异步查询任务 */
    interface BiQueryTask {
      /** 任务 ID（sqid） */
      id: string;
      /** 任务名称 */
      name: string | null;
      /** 数据源 ID（sqid） */
      datasourceId: string;
      /** 任务状态 */
      status: BiQueryTaskStatus;
      /** 进度百分比 0-100 */
      progress: number;
      /** 已扫描行数 */
      rowsFetched: number;
      /** 执行耗时（毫秒） */
      elapsedMs: number;
      /** 结果总行数 */
      resultRowCount: number;
      /** 结果是否被截断（仅预览截断，CSV 完整） */
      resultIsTruncated: boolean;
      /** 结果预览快照 */
      resultSnapshot: BiQueryTaskSnapshot | null;
      /** 错误信息 */
      errorMessage: string | null;
      /** 开始执行时间 */
      startedAt: string | null;
      /** 完成时间 */
      finishedAt: string | null;
      /** 提交来源：manual / auto_transfer */
      source: 'manual' | 'auto_transfer';
      /** 创建时间 */
      createdAt: string;
      /** SQL 全文（仅详情接口返回） */
      sqlText?: string;
    }

    /** 异步查询任务列表查询参数 */
    interface BiQueryTaskSearchParams {
      current: number;
      size: number;
      name?: string;
      status?: BiQueryTaskStatus;
      datasourceId?: string;
    }

    /** 异步查询任务列表分页响应 */
    interface BiQueryTaskList {
      records: BiQueryTask[];
      total: number;
    }

    /** 提交异步查询请求 */
    interface BiAsyncRunPayload {
      sql: string;
      datasourceId: string;
      name?: string;
    }

    /** 提交异步查询响应 */
    interface BiAsyncRunResult {
      taskId: string;
      status: string;
    }

    /** 异步任务结果预览响应 */
    interface BiQueryTaskResult {
      resultSnapshot: BiQueryTaskSnapshot | null;
      resultRowCount: number;
      resultIsTruncated: boolean;
    }

    /** 智能切换响应（/sql/run 软超时触发） */
    interface BiSqlRunTransferredResult {
      transferred: true;
      taskId: string;
      message: string;
      datasourceId: string;
      sqlText: string;
    }

    /** /sql/run 返回的联合结果：同步成功 / 软超时转异步 */
    type BiSqlRunResult = SqlExecutionResult | BiSqlRunTransferredResult;

    // ============================================================
    // Dashboard（仪表盘）
    // ============================================================

    /** Dashboard layout 单元素（与 BiChart 关联，存 SQID 编码字符串） */
    interface BiDashboardItem {
      /** BiChart 的 SQID 编码 */
      chartId: string;
      /** 列位置 0-11 */
      x: number;
      /** 行位置 0-N */
      y: number;
      /** 宽度 1-12 */
      w: number;
      /** 高度 1-6 */
      h: number;
    }

    /** Dashboard layout 结构 */
    interface BiDashboardLayout {
      items: BiDashboardItem[];
    }

    /** 列表页简要信息 */
    interface BiDashboardBrief {
      id: string;
      name: string;
      description: string | null;
      /** 图表数量 */
      itemCount: number;
      createdAt: string | null;
      updatedAt: string | null;
    }

    /** 分页列表响应 */
    interface BiDashboardList {
      records: BiDashboardBrief[];
      total: number;
      current: number;
      size: number;
    }

    /** 详情（含完整 layout） */
    interface BiDashboardDetail {
      id: string;
      name: string;
      description: string | null;
      layout: BiDashboardLayout;
      tenantId?: number;
      createdAt: string | null;
      updatedAt: string | null;
    }

    /** 图表元信息（刷新/预览响应内嵌） */
    interface BiChartMeta {
      name: string;
      chartType: string;
      xCol: string | null;
      yCol: string | null;
    }

    /** 刷新单项结果 */
    interface BiDashboardRefreshItem {
      chartId: string;
      /** success / failed / deleted */
      status: 'success' | 'failed' | 'deleted';
      /** 成功时返回 */
      resultSnapshot?: ChartResultSnapshot;
      /** 失败/已删除时为 null */
      chartMeta: BiChartMeta | null;
      /** 失败时返回错误信息 */
      errorMessage?: string;
      /** 成功时返回快照时间 ISO */
      snapshotAt?: string;
    }

    /** 刷新响应聚合 */
    interface BiDashboardRefreshResult {
      items: BiDashboardRefreshItem[];
      totalElapsedMs: number;
    }

    /** 预览单项结果（不刷新，用 BiChart 已有快照） */
    interface BiDashboardPreviewItem {
      chartId: string;
      chartMeta: BiChartMeta | null;
      /** 已删除时无快照 */
      resultSnapshot?: ChartResultSnapshot;
      /** 仅 deleted 状态出现 */
      status?: 'deleted';
    }

    /** 预览响应聚合 */
    interface BiDashboardPreview {
      id: number;
      name: string;
      description: string | null;
      layout: BiDashboardLayout;
      items: BiDashboardPreviewItem[];
    }

    /** 创建/更新请求 */
    interface BiDashboardPayload {
      name: string;
      description?: string | null;
      layout: BiDashboardLayout;
    }

    /** 分页查询参数 */
    interface BiDashboardSearchParams {
      current: number;
      size: number;
      name?: string;
    }
  }
}
