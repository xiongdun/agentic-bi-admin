declare namespace Api {
  /**
   * namespace Bi
   *
   * backend api module: "bi" (AgenticBI)
   */
  namespace Bi {
    // ---- Datasource ----

    type DatasourceType = 'postgresql' | 'mysql' | 'clickhouse' | 'trino' | 'sqlite';

    interface Datasource {
      id: string;
      name: string;
      type: DatasourceType;
      host: string | null;
      port: number | null;
      database: string;
      username: string | null;
      isDefault: boolean;
      lastSyncedAt: string | null;
      statusType: Common.EnableStatus;
      remark: string | null;
      tenantId: number;
    }

    type DatasourceSearchParams = CommonType.RecordNullable<
      { name?: string; type?: DatasourceType } & CommonSearchParams
    >;

    type DatasourceList = Common.PaginatingQueryRecord<Datasource>;

    interface DatasourceAddParams {
      name: string;
      type: DatasourceType;
      database: string;
      host?: string | null;
      port?: number | null;
      username?: string | null;
      password?: string | null;
      isDefault?: boolean;
      remark?: string | null;
    }

    type DatasourceUpdateParams = Partial<DatasourceAddParams>;

    interface DatasourceTestResult {
      ok: boolean;
      error: string | null;
    }

    interface DatasourceSyncResult {
      tables: number;
      columns: number;
      errors: string[];
    }

    interface DemoBootstrapResult {
      datasourceId: number;
      datasourceName: string;
      generated: {
        created: boolean;
        rows: number | { categories: number; products: number; customers: number; orders: number };
      };
      synced: DatasourceSyncResult;
    }

    // ---- Table / Column ----

    interface BiColumn {
      id: string;
      name: string;
      dataType: string;
      nullable: boolean;
      description: string | null;
      isDimension: boolean;
      isMetric: boolean;
      sampleValues: string[] | null;
      ordinal: number;
    }

    interface BiTable {
      id: string;
      datasourceId: string;
      name: string;
      schemaName: string | null;
      description: string | null;
      tags: string[] | null;
      version: number;
      lastSyncedAt: string | null;
      columnCount: number;
    }

    interface BiTableDetail extends BiTable {
      columns: BiColumn[];
    }

    type BiTableSearchParams = CommonType.RecordNullable<{ datasourceId?: string; name?: string } & CommonSearchParams>;

    type BiTableList = Common.PaginatingQueryRecord<BiTable>;

    // ---- SQL Workbench ----

    type ExecutionStatus = 'success' | 'failed' | 'timeout' | 'denied';

    interface SqlExecuteRequest {
      datasourceId: string; // sqid
      sql: string;
      allowWrite?: boolean;
    }

    interface SqlExecuteResponse {
      columns: string[];
      rows: (string | number | boolean | null)[][];
      rowCount: number;
      costMs: number;
      finalSql: string;
      maskedColumns: string[];
      sqlHash: string;
    }

    interface SqlExplainRequest {
      datasourceId: string; // sqid
      sql: string;
    }

    interface SqlExplainResponse {
      columns: string[];
      rows: (string | number | boolean | null)[][];
      rawSql: string;
      costMs: number;
    }

    interface QueryExecutionRecord {
      id: string;
      datasourceId: string;
      sql: string;
      status: ExecutionStatus;
      rowCount: number | null;
      costMs: number | null;
      error: string | null;
      createdAt: string | null;
    }

    type QueryExecutionList = Common.PaginatingQueryRecord<QueryExecutionRecord>;

    // ---- Chat ----

    interface ChatSession {
      id: string;
      title: string;
      datasourceId: string | null;
      lastMessageAt: string | null;
      statusType: string;
      createdAt: string | null;
    }

    interface ChatAgentStep {
      node: string;
      durationMs: number;
      input?: Record<string, unknown>;
      output?: Record<string, unknown>;
      tokens?: number;
      error?: string | null;
    }

    interface ChatMessage {
      id: string;
      sessionId: string;
      role: 'user' | 'assistant' | 'system' | 'tool';
      content: string;
      thinking: string | null;
      sql: string | null;
      error: string | null;
      costMs: number | null;
      tokensUsed: number | null;
      agentSteps: ChatAgentStep[];
      createdAt: string | null;
    }

    interface ChatSessionDetail {
      session: ChatSession;
      messages: ChatMessage[];
    }

    type ChatSessionList = Common.PaginatingQueryRecord<ChatSession>;

    interface ChatCreateRequest {
      title?: string;
      datasourceId?: string | null;
    }

    interface ChatSendRequest {
      question: string;
      datasourceId?: string | null;
    }

    // ---- Model Provider / Model (LLM) ----

    type ModelProviderType = 'openai_compatible' | 'anthropic' | 'ollama' | 'mock' | 'custom';
    type ModelType = 'chat' | 'embedding' | 'vision';
    type ModelCapability = 'function_call' | 'reasoning' | 'json_mode' | 'vision' | 'streaming';

    interface ModelProvider {
      id: string;
      name: string;
      code: string;
      type: ModelProviderType;
      displayName: string | null;
      baseUrl: string | null;
      apiKeyMasked: string | null;
      extra: Record<string, unknown> | null;
      isEnabled: boolean;
      isDefault: boolean;
      order: number;
      lastTestedAt: string | null;
      lastTestOk: boolean | null;
      statusType: Common.EnableStatus;
      remark: string | null;
      modelCount: number;
    }

    type ModelProviderSearchParams = CommonType.RecordNullable<
      { name?: string; code?: string; type?: ModelProviderType; isEnabled?: boolean } & CommonSearchParams
    >;

    type ModelProviderList = Common.PaginatingQueryRecord<ModelProvider>;

    interface ModelProviderAddParams {
      name: string;
      code: string;
      type: ModelProviderType;
      displayName?: string | null;
      baseUrl?: string | null;
      apiKey?: string | null;
      extra?: Record<string, unknown> | null;
      isEnabled?: boolean;
      isDefault?: boolean;
      order?: number;
      remark?: string | null;
    }

    type ModelProviderUpdateParams = Partial<ModelProviderAddParams>;

    interface ModelProviderTestResult {
      ok: boolean;
      error: string | null;
      model: string | null;
    }

    interface BiModel {
      id: string;
      providerId: string;
      providerCode: string | null;
      providerName: string | null;
      code: string;
      displayName: string | null;
      type: ModelType;
      contextWindow: number;
      inputPrice: number | null;
      outputPrice: number | null;
      defaultParams: Record<string, unknown> | null;
      capabilities: ModelCapability[] | null;
      isEnabled: boolean;
      isDefault: boolean;
      order: number;
      statusType: Common.EnableStatus;
      remark: string | null;
    }

    type BiModelSearchParams = CommonType.RecordNullable<
      { providerId?: string; code?: string; type?: ModelType; isEnabled?: boolean } & CommonSearchParams
    >;

    type BiModelList = Common.PaginatingQueryRecord<BiModel>;

    interface BiModelAddParams {
      providerId: string;
      code: string;
      displayName?: string | null;
      type?: ModelType;
      contextWindow?: number;
      inputPrice?: number | null;
      outputPrice?: number | null;
      defaultParams?: Record<string, unknown> | null;
      capabilities?: ModelCapability[] | null;
      isEnabled?: boolean;
      isDefault?: boolean;
      order?: number;
      remark?: string | null;
    }

    type BiModelUpdateParams = Partial<BiModelAddParams>;
  }
}
