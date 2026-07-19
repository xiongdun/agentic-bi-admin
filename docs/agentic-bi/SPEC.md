# AgenticBI 实施规格（SPEC）

> 在 FastSoyAdmin（现 AgenticBIAdmin）基础上构建的**智能数据分析平台**。
> 业务人员用自然语言自助取数；专业用户可直连 SQL 工作台。
> 多数据源、多 LLM、多租户、可解释、可审计。

---

## 1. 项目代号 & 目标

| 项 | 值 |
|---|---|
| 项目代号 | **AgenticBI** |
| 业务模块位置 | `app/business/bi/`（与 `app/business/hr/` 平级，独立模块） |
| 目标用户 | 业务运营、财务、市场（自然语言）+ 数据分析师/DBA（SQL） |
| 交付周期 | 6 周（3 阶段，每阶段 2 周） |
| 演示场景 | 电商 demo（订单/产品/客户/退货）— 本地 SQLite |

---

## 2. 痛点 & 对应能力

| 痛点 | 对应能力 | 优先级 |
|---|---|---|
| 业务人员不会 SQL，IT 排队 2-4h | NL2SQL + 意图识别 + 自动图表 | P0 |
| 数据源分散（MySQL/PG/CH 等） | 统一数据源连接层 + 5 种方言 | P0 |
| 元数据混乱，LLM 猜错列名 | 元数据中心 + 同义词 + 业务术语 | P0 |
| NL2SQL 黑盒无解释 | 多 Agent 分步执行 + 思维链留痕 | P0 |
| 专业用户被管道束缚 | SQL 工作台（Monaco + EXPLAIN + 历史） | P0 |
| 权限管理缺失 | 多租户 + 数据源授权 + 列脱敏 | P0 |
| 操作无审计 | 全链路审计（HTTP/SQL/Agent 步骤） | P0 |

---

## 3. 已锁定的技术决策

| 维度 | 选型 | 备注 |
|---|---|---|
| **LLM** | DeepSeek API（主） / Ollama（本地） / 通义 / GPT-4o | 统一抽象层（`app/utils/llm.py`） |
| **数据源** | PostgreSQL / MySQL / ClickHouse / Trino / SQLite | sqlglot 做方言转换 + 校验 |
| **Agent 框架** | LangGraph（生产级） | async API，FastAPI 集成 |
| **租户隔离** | 共享库 + `tenant_id` 列注入 | 复用现有 `data_scope` |
| **SQL 沙箱** | 只读模式：白名单 SELECT/EXPLAIN | sqlglot AST 校验 |
| **AI 输出** | SSE 流式 | FastAPI 原生 |
| **多租户隔离** | 共享库 + tenant_id 列 | data_scope 复用 |
| **数据源 demo** | 本地 SQLite + 电商 demo 数据（订单/产品/客户/退货） | 后续接真实库 |
| **HR 业务模块** | **保留**（不动） | bi 独立新模块 |

---

## 4. 模块结构

```
app/business/bi/
├── module.py                    # manifest（autodiscover）
├── models.py                    # 15 张表（Tortoise）
├── schemas.py                   # Pydantic schemas
├── services/                    # 业务逻辑层
│   ├── datasource.py
│   ├── metadata.py
│   ├── chat.py
│   ├── execution.py
│   ├── metric.py
│   └── audit.py
├── api/                         # REST + SSE
│   ├── datasource.py
│   ├── metadata.py
│   ├── chat.py                  # SSE 端点
│   ├── sql_workbench.py
│   ├── metric.py
│   └── audit.py
├── agent/                       # LangGraph 多 Agent
│   ├── state.py                 # AgentState TypedDict
│   ├── nodes/
│   │   ├── intent.py
│   │   ├── schema_select.py
│   │   ├── sql_gen.py
│   │   ├── sql_validate.py
│   │   ├── sql_fix.py
│   │   ├── chart_recommend.py
│   │   └── explain.py
│   ├── graph.py                 # LangGraph DAG
│   ├── runner.py                # FastAPI 异步桥接
│   └── prompts/                 # 7 个 prompt 模板
├── sandbox/                     # SQL 沙箱
│   ├── executor.py              # SQLAlchemy 异步
│   ├── whitelist.py             # sqlglot AST 白名单
│   ├── masking.py               # 列脱敏
│   ├── quota.py                 # 行数/超时/熔断
│   └── tenant.py                # 多租户行级注入
├── metadata/                    # 元数据采集
│   ├── sync.py                  # 拉 schema
│   ├── sampler.py               # 列采样
│   └── profiler.py              # 字段统计
├── llm/                         # LLM 抽象层
│   ├── base.py                  # BaseChatModel
│   ├── deepseek.py
│   ├── ollama.py
│   ├── qwen.py
│   ├── openai.py
│   └── router.py                # 多 provider 路由
├── events.py                    # 事件契约
├── policies.py                  # DataPolicy
└── init_data.py                 # 种子数据
```

```
web/src/views/bi/
├── chat/                        # 对话工作台
│   ├── index.vue
│   ├── modules/
│   │   ├── chat-sessions.vue
│   │   ├── chat-messages.vue
│   │   ├── message-card.vue
│   │   ├── sql-block.vue
│   │   └── chart-block.vue
├── metadata/                    # 元数据中心
│   ├── index.vue
│   └── modules/
│       ├── datasource-tree.vue
│       └── column-editor.vue
├── sql-workbench/               # SQL 工作台
│   ├── index.vue
│   └── modules/
│       ├── sql-editor.vue
│       ├── execution-history.vue
│       └── result-table.vue
└── audit/                       # 审计面板
    └── index.vue
```

---

## 5. 数据模型（15 张表）

### 5.1 元数据 (5)

```python
class Datasource(BaseModel, AuditMixin):
    id: int
    name: str                        # 业务名
    type: Literal['postgresql','mysql','clickhouse','trino','sqlite']
    host: str
    port: int
    database: str
    username: str
    password_enc: str                # Fernet 加密
    tenant_id: int                   # 多租户
    is_default: bool
    extra: JSONField                 # driver-specific
    last_synced_at: datetime | None

class Table(BaseModel, AuditMixin):
    datasource_id: FK(Datasource)
    schema_name: str
    name: str
    description: str | None
    tags: list[str]
    version: int                     # 同步次数
    last_synced_at: datetime | None

class Column(BaseModel, AuditMixin):
    table_id: FK(Table)
    name: str
    data_type: str
    nullable: bool
    description: str | None
    is_dimension: bool               # 用于 group by
    is_metric: bool                  # 用于聚合
    enum_values: list[str] | None
    sample_values: list[str] | None  # 采样值（最多 10 个）

class Relation(BaseModel):
    src_table_id: FK(Table)
    src_column: str
    dst_table_id: FK(Table)
    dst_column: str
    join_type: Literal['inner','left','right','full']
    confidence: float                # 0-1，是否自动发现

class Synonym(BaseModel):
    term: str                        # 业务用语
    mapped_term: str                 # 实际列名/表名
    kind: Literal['column','table','metric','concept']
    datasource_id: FK(Datasource) | None
```

### 5.2 业务语义 (3)

```python
class Metric(BaseModel, AuditMixin):
    name: str                        # 业务名（"销售额"）
    display_name: str
    description: str | None
    sql_template: str                # "SUM({order}.amount) WHERE {order}.status='paid'"
    dataset_id: FK(Dataset) | None
    unit: str | None                 # 元/件/人
    owner_id: FK(User)

class Dataset(BaseModel, AuditMixin):
    name: str
    description: str | None
    owner_id: FK(User)
    visibility: Literal['private','team','public']
    tables: M2M(Table)
    metrics: M2M(Metric)

class Chart(BaseModel, AuditMixin):
    dataset_id: FK(Dataset)
    name: str
    type: Literal['bar','line','pie','funnel','sankey','radar','heatmap','scatter','area','map']
    x_field: str | None
    y_fields: list[str]
    agg: Literal['sum','avg','count','max','min']
    config_json: JSONField           # ECharts option
    sql_template: str | None
```

### 5.3 对话与执行 (3)

```python
class ChatSession(BaseModel, AuditMixin):
    user_id: FK(User)
    tenant_id: int
    title: str
    dataset_id: FK(Dataset) | None
    last_message_at: datetime

class ChatMessage(BaseModel, AuditMixin):
    session_id: FK(ChatSession)
    role: Literal['user','assistant','system','tool']
    content: str
    thinking: str | None             # 思维链
    sql: str | None
    chart_id: FK(Chart) | None
    error: str | None
    agent_steps_json: JSONField      # [{node, input, output, cost_ms, tokens}]

class QueryExecution(BaseModel, AuditMixin):
    session_id: FK(ChatSession) | None
    message_id: FK(ChatMessage) | None
    user_id: FK(User)
    tenant_id: int
    datasource_id: FK(Datasource)
    sql: str
    status: Literal['success','failed','timeout','denied']
    row_count: int | None
    cost_ms: int | None
    error: str | None
    explain_json: JSONField | None
    row_limit_applied: int | None
```

### 5.4 权限 & 审计 (4)

```python
class DatasourceGrant(BaseModel, AuditMixin):
    role_code: str
    datasource_id: FK(Datasource)
    scope: Literal['all','scope','self']
    allow_export: bool
    allow_write: bool                # 默认 False（只读模式）

class ColumnMasking(BaseModel, AuditMixin):
    column_id: FK(Column)
    role_code: str
    mask_type: Literal['full','partial','email','phone','id_card','bank_card','hash']

class AuditLog(BaseModel):
    user_id: FK(User)
    tenant_id: int
    action: str                      # 'query','export','metadata_update','etc'
    datasource_id: FK(Datasource) | None
    sql_hash: str | None
    row_count: int | None
    cost_ms: int | None
    ip: str
    user_agent: str
    detail: JSONField | None
    created_at: datetime             # 不复用 AuditMixin，自己加

class Tenant(BaseModel, AuditMixin):
    name: str
    code: str                        # 'tenant_a','tenant_b'
    is_active: bool
    default_datasource_id: FK(Datasource) | None
```

### 5.5 表命名

`bi_datasource` / `bi_table` / `bi_column` / `bi_relation` / `bi_synonym` / `bi_metric` / `bi_dataset` / `bi_chart` / `bi_chat_session` / `bi_chat_message` / `bi_query_execution` / `bi_datasource_grant` / `bi_column_masking` / `bi_audit_log` / `sys_tenant`

---

## 6. Agent 编排（LangGraph）

### 6.1 状态定义

```python
class AgentState(TypedDict):
    # 用户输入
    user_query: str
    user_id: int
    tenant_id: int
    session_id: int

    # 上下文
    dataset_id: int | None
    datasource_id: int | None
    history: list[dict]              # 最近 N 轮对话

    # 中间结果
    intent: dict | None              # {type, entities, filters}
    relevant_tables: list[dict]
    relevant_columns: list[dict]
    relevant_metrics: list[dict]
    sql_candidate: str | None
    sql_validated: str | None
    sql_error: str | None
    retry_count: int

    # 执行结果
    execution_result: dict | None    # {rows, columns, cost_ms}
    chart_config: dict | None
    final_response: str | None

    # 留痕
    agent_steps: list[dict]          # [{node, input, output, cost_ms, tokens}]
```

### 6.2 节点

| 节点 | 类型 | 输入 | 输出 | 备注 |
|---|---|---|---|---|
| **Intent Agent** | LLM | user_query | intent | 意图 + 实体抽取（时间、过滤、维度） |
| **Schema Select** | LLM + RAG | intent, dataset_id | relevant_tables/columns/metrics | 选 5-8 张表 + 同义词展开 |
| **SQL Gen** | LLM | user_query, schema, intent, history, samples | sql_candidate | 带 CoT |
| **SQL Validate** | 本地 sqlglot | sql_candidate, tenant_id, role_codes | sql_validated / error | 4 道闸 |
| **SQL Fix** | LLM（仅失败时） | sql_candidate, error, schema | sql_candidate (新) | 重试最多 2 次 |
| **Executor** | SQLAlchemy | sql_validated | execution_result | 沙箱执行 |
| **Chart Recommend** | LLM | execution_result | chart_config | 结果 schema → ECharts option |
| **Explain Agent** | LLM | user_query, intent, result, chart | final_response | 自然语言回答 |

### 6.3 图（DAG）

```
[START]
   ↓
[Intent] ────→ 闲聊/非查询 ────→ [Explain] → [END]
   ↓ 查询
[Schema Select]
   ↓
[SQL Gen] ────→ [SQL Validate] ────→ 失败 ──→ [SQL Fix] → [SQL Validate]
                                       ↓ 通过
                                  [Executor] ────→ 失败 ──→ [SQL Fix] → [SQL Validate]
                                       ↓ 成功
                                  [Chart Recommend]
                                       ↓
                                  [Explain]
                                       ↓
                                     [END]
```

---

## 7. SQL 沙箱 4 道闸

### 7.1 AST 白名单

```python
# sandbox/whitelist.py
ALLOWED_STATEMENTS = {'SELECT', 'WITH', 'EXPLAIN'}
FORBIDDEN_FUNCTIONS = {
    'pg_read_file', 'pg_ls_dir',     # PG 文件读取
    'lo_import', 'lo_export',         # PG 大对象
    'xp_cmdshell',                    # MSSQL 命令执行
    'load_file', 'into_outfile',      # MySQL 文件
}
FORBIDDEN_KEYWORDS = {'INTO', 'UNLOAD'}  # ClickHouse 导出
```

### 7.2 行级隔离

```python
# sandbox/tenant.py
def inject_tenant_filter(sql, tenant_id, tenant_id_field='tenant_id'):
    """对 SELECT 自动加 WHERE tenant_id = :scope"""
    tree = sqlglot.parse_one(sql, dialect=...)
    # 在最外层 WHERE 加 AND
    for select in tree.find_all(sqlglot.exp.Select):
        existing_where = select.args.get('where')
        tenant_cond = sqlglot.exp.EQ(
            this=sqlglot.exp.column(tenant_id_field),
            expression=sqlglot.exp.convert(tenant_id)
        )
        if existing_where:
            existing_where.set('this', sqlglot.exp.And(this=existing_where.args['this'], expression=tenant_cond))
        else:
            select.set('where', sqlglot.exp.Where(this=tenant_cond))
    return tree.sql(dialect=...)
```

### 7.3 列脱敏

```python
# sandbox/masking.py
MASK_RULES = {
    'phone': lambda c: f"CONCAT(LEFT({c},3),'****',RIGHT({c},4))",
    'email': lambda c: f"CONCAT(LEFT({c},1),'****',SUBSTRING_INDEX({c},'@',-1))",
    'id_card': lambda c: f"CONCAT(LEFT({c},4),'**********',RIGHT({c},4))",
}
```

### 7.4 配额熔断

```python
# sandbox/quota.py
@dataclass
class Quota:
    max_rows: int = 10000
    timeout_seconds: float = 30
    slow_query_threshold_ms: int = 5000
    rate_limit_per_minute: int = 30    # 每用户
```

---

## 8. LLM 抽象层

```python
# app/business/bi/llm/base.py
class BaseChatModel(Protocol):
    async def ainvoke(self, messages: list[dict], **kwargs) -> LLMResponse: ...
    async def astream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]: ...

# app/business/bi/llm/router.py
class LLMRouter:
    """基于任务类型 + 成本预算路由"""
    def __init__(self):
        self.providers = {
            'deepseek': DeepSeekClient(),
            'ollama': OllamaClient(),
            'qwen': QwenClient(),
            'openai': OpenAIClient(),
        }

    def route(self, task: Literal['intent','sql_gen','sql_fix','chart','explain']) -> BaseChatModel:
        # 配置式：intent → deepseek; sql_gen → deepseek; explain → ollama
        ...
```

**Provider 配置（.env）**：
```bash
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b
QWEN_API_KEY=sk-xxx
OPENAI_API_KEY=sk-xxx
LLM_DEFAULT_PROVIDER=deepseek
```

---

## 9. 前端 4 大工作台

| 页面 | 路径 | 核心组件 | 备注 |
|---|---|---|---|
| **对话工作台** | `/bi/chat` | ChatSessions + ChatMessages + MessageCard + SqlBlock + ChartBlock | SSE 流式 |
| **元数据中心** | `/bi/metadata` | DatasourceTree + ColumnEditor | 树形 + 描述编辑 |
| **SQL 工作台** | `/bi/sql-workbench` | SqlEditor (Monaco) + ExecutionHistory + ResultTable | 多 tab + EXPLAIN |
| **审计面板** | `/bi/audit` | AuditTable + SlowQueryChart + FilterBar | 表格 + ECharts |

### SSE 客户端

```typescript
// web/src/hooks/use-sse.ts
export function useSSE<T>(url: string, onMessage: (data: T) => void) {
  const eventSource = new EventSource(url, { withCredentials: true });
  eventSource.onmessage = (e) => onMessage(JSON.parse(e.data));
  return { close: () => eventSource.close() };
}
```

### ECharts 组件

```vue
<!-- web/src/components/echarts/echart-renderer.vue -->
<template>
  <div ref="chartRef" :style="{ height }" />
</template>
```

支持类型：bar / line / pie / funnel / sankey / radar / heatmap / scatter / area / map (中国地图)

---

## 10. 多租户实现

### 10.1 共享库 + tenant_id 列

```python
# app/business/bi/models.py
class Datasource(BaseModel, AuditMixin):
    # 显式字段
    tenant_id: int   # ← 通过 contextvar 注入；query 过滤用
```

### 10.2 全链路注入

```python
# app/business/bi/policies.py
DATASOURCE_READ = DataPolicy(
    name='bi.datasource.read',
    action='read',
    build_filter=lambda ctx: Q(tenant_id=ctx.tenant_id) & (
        Q(is_default=True) if ctx.is_super else Q(grants__role_code__in=ctx.role_codes)
    ),
)
```

### 10.3 SQL 沙箱注入

```python
# sandbox/tenant.py
def inject_tenant_filter(sql, ctx):
    """根据 ctx.tenant_id 注入 WHERE"""
    ...
```

---

## 11. 事件 & 审计

### 11.1 事件契约

```python
# app/business/bi/events.py
class ChatMessageCreatedPayload(BaseModel):
    message_id: int
    session_id: int
    user_id: int
    sql: str | None

CHAT_MESSAGE_CREATED = EventSpec(
    name='bi.chat.message.created',
    payload=ChatMessageCreatedPayload,
    delivery='local',
)
```

### 11.2 审计

- **Radar 自动记录**：HTTP/SQL/异常（已实现）
- **Agent 步骤留痕**：`ChatMessage.agent_steps_json` 存每节点耗时/token
- **AuditLog**：业务事件（query/export）— 由 sandbox 触发写
- **前端审计面板**：`/bi/audit` 查询

---

## 12. 演示数据

**SQLite** + 电商 demo，5 张表，1 万订单：

```sql
-- products
CREATE TABLE products (id, name, category, price, created_at);
-- customers
CREATE TABLE customers (id, name, city, registered_at, tenant_id);
-- orders
CREATE TABLE orders (id, customer_id, product_id, amount, status, ordered_at, tenant_id);
-- returns
CREATE TABLE returns (id, order_id, reason, refunded_at, tenant_id);
-- daily_stats (物化)
CREATE TABLE daily_stats (date, metric, value, tenant_id);
```

**种子脚本** `app/business/bi/demo_data.py`：
- 1 万订单 / 100 产品 / 1000 客户 / 50 退货
- 跨 12 个月、5 个产品类目、3 个城市

---

## 13. 阶段交付

| 阶段 | 周期 | 交付物 | 验收标准 |
|---|---|---|---|
| **Phase 1：MVP** | 2 周 | LLM 客户端（DeepSeek）+ 1 数据源 + 5 表元数据 + 单 Agent NL2SQL + SQL 沙箱 + 对话工作台 + 多租户 + 基础审计 | 演示"本月各产品线销售额排名"端到端成功 |
| **Phase 2：增强** | 2 周 | LangGraph 完整 7 节点 + 4 LLM 路由 + 5 数据源 + SQL 工作台 + 业务指标 + 列脱敏 + 5+ 图表类型 | 演示 5 个查询场景，列脱敏生效 |
| **Phase 3：生产化** | 2 周 | 性能优化（连接池/prompt 缓存/结果缓存）+ observability + 慢查询巡检 + Docker Compose + 完整文档 + E2E 测试 | p95 < 5s，单用户 30 qpm |

---

## 14. 风险 & 缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| LangGraph 与 FastAPI 异步整合 | agent 阻塞 | 用 `ainvoke`，超时 30s 自动 cancel |
| LLM 费用失控 | 成本 | prompt 缓存 + 结果缓存 + token 限额 + 路由低成本模型 |
| SQL 沙箱绕过 | 安全 | sqlglot AST 多层校验 + 列权限矩阵 + 拒绝 `INTO OUTFILE` 等 |
| 元数据同步延迟 | LLM 猜错 | 同步周期 1h + DDL 触发（Phase 3）+ 手动编辑界面 |
| 多租户数据泄露 | 致命 | data_scope + sandbox 双重注入 + 单元测试覆盖 |

---

## 15. 验收清单（总览）

- [ ] 自然语言查询"本月各产品线销售额排名"可端到端成功
- [ ] LLM 选 4 家可热切换
- [ ] 5 种数据源可连（PG/MySQL/CH/Trino/SQLite）
- [ ] 多租户隔离（A 租户查不到 B 租户数据）
- [ ] SQL 沙箱拦截 DELETE/UPDATE/INSERT
- [ ] 列脱敏（手机/身份证）
- [ ] 审计全链路（HTTP/SQL/Agent 步骤/导出）
- [ ] SSE 流式输出思维链
- [ ] ECharts 10+ 图表
- [ ] SQL 工作台 Monaco + EXPLAIN
- [ ] `just check` 全过
- [ ] 测试覆盖 > 80%

---

## Phase 1.x: Metric 模板系统 + LLM 意图识别（2026-07-17）

### 新增能力
- Metric CRUD（`/business/bi/metrics/*`）+ 5 个预置电商 metric
- `/bi/metrics` 管理页面（仅 `B_BI_METRIC_MANAGE` 可改）
- `intent_node` 升级为 LLM 必走，一次返回 `{intent, metrics: [{id, reason}], reasoning}`
- `sql_gen_node` 接受选中的 metric 模板作为强约束片段

### 行为变更
- 任何 LLM 失败 → `code=4001` 错误（SSE error 事件），前端跳 `/bi/models`
- `MockChatModel` 兜底彻底删除
- ChatWorkbench 不暴露"指标"概念（隐藏实现细节）

### 数据迁移
- `bi_metric` 表加 `datasource_id` FK（`just mm` 生成）
- DB 漂移修复：`migrations/app_system/0002_drift_fix_bi_fk_columns.py` 用 `RunSQL` 补齐 `bi_chat_session.dataset_id / datasource_id` 与 `bi_chat_message.session_id / chart_id`（早期 `generate_schemas()` baseline 漂移）
- SSE 序列化修复：`chat.py` 的 `_sse` 改用 `JSONServerSentEvent`，避免 sse_starlette 把字典 `data` 走 `str()` 单引号路径

---

**确认下一步后，依次产出 checklist.md / tasks.md / 代码。**
