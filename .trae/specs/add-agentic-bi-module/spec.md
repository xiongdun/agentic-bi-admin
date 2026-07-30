# Agentic BI 智能数据分析模块 Spec

## Why

AgenticBIAdmin 当前仅有 HR 示例业务模块，缺少项目核心价值承载——智能数据分析能力。本变更在 `app/business/bi/` 新增智能 BI 模块，让业务人员用自然语言对话数据库（NL2SQL），并为专业用户提供 SQL 工作台，覆盖"取数 → 分析 → 可视化 → 审计"全链路，实现项目从"通用后台模板"向"智能 BI 平台"的产品跃迁。

依据 [docs/bi/agentic-bi.md](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/docs/bi/agentic-bi.md) v2.0 PRD，一次性落地完整 v0.1 + v0.2 范围。

## What Changes

### 后端新增（`app/business/bi/`）

- **模块骨架**：`module.py` manifest 声明 `BusinessModule`，autodiscover 自动加载；`config.py` 模块配置；`init_data.py` 菜单/角色/按钮码种子（`reconcile_menu_subtree` 启用 IaC 单一数据源）；`events.py` 事件契约；`policies.py` 行级 DataPolicy。
- **13 个数据模型**（`models.py`，表名 `biz_bi_*`）：
  - metadata：`BiDatasource` / `BiTable` / `BiColumn` / `BiIndex` / `BiForeignKey`
  - semantic：`BiMetric`
  - conversation：`BiChatSession` / `BiChatMessage`
  - llm：`BiLLMProvider` / `BiLLMModel`
  - audit：`BiAuditLog`
  - security：`BiMaskingRule` / `BiQuotaConfig`
- **Agent 流水线**（`agent/`）：基于 **LangGraph StateGraph DAG** 实现 5 节点固定流水线（intent → sql_gen → sql_validate → executor → explain），保留 PRD "固定 LLM 调用次数" 原则；`runner.py` 用 `graph.astream()` 流式产出 step 事件。
- **LLM Provider 抽象**（`llm/`）：基于 **langchain BaseChatModel** 封装 `BaseLLMProvider`，实现 5 个 Provider（DeepSeek / Ollama / 通义 / OpenAI / Mock）；`router.py` 按 `LLM_DEFAULT_PROVIDER` 路由，默认 DeepSeek。
- **Sandbox 安全引擎**（`sandbox/`）：`whitelist.py`（sqlglot AST 白名单，仅 SELECT/WITH/EXPLAIN）+ `dialect.py`（方言转换）+ `masking.py`（列脱敏）+ `tenant.py`（多租户行级注入）+ `quota.py`（行数/超时/熔断）+ `executor.py`（SQLAlchemy 异步执行）。
- **Metadata 采集**（`metadata/`）：`sync.py`（schema 同步）+ `sampler.py`（列采样）+ `relations.py`（关系提取）；首启动 `init_data.init()` 自动触发默认数据源元数据同步（如已配置）。
- **SSE 封装**（`sse.py`）：基于 `sse_starlette`，事件类型 `step` / `final` / `error` / `heartbeat`；**必须使用 `JSONServerSentEvent` + `json.dumps`** 避免 `data:` 双前缀（来自项目历史教训）。
- **API 层**（`api/`）：7 个子模块路由（datasource / metadata / chat / sql_workbench / metric / llm / audit），聚合到 `api/__init__.py`；标准 CRUD 用 `CRUDRouter`，自定义动作用 `@crud.override` 或显式 `@router.*`。
- **Service / Controller 层**：`controllers.py`（继承 `CRUDBase` + `build_search`）+ `services.py`（跨模型编排、缓存、事件派发）。

### 前端新增（`web/src/`）

- **6 个页面**（`views/bi/`）：`chat` / `metadata` / `sql-workbench` / `metrics` / `models` / `audit`，由 Elegant Router 自动生成路由（路由名 `bi_chat` / `bi_metadata` / `bi_sql-workbench` / `bi_metrics` / `bi_models` / `bi_audit`，连字符格式与 elegant-router 一致）。
- **SQL 编辑器**：使用 **Monaco Editor**（`pnpm add monaco-editor`），集成到 `sql-workbench`。
- **图表**：ECharts 6 + `useEcharts` hook，自动判断柱状/折线/饼图/表格。
- **API 服务**：`service/api/bi*.ts`（6 个文件）+ `typings/api/bi.d.ts` 类型定义。
- **i18n**：`locales/langs/_generated/bi/`（zh-cn.ts / en-us.ts / types.d.ts）。
- **请求库**：必须使用 `@sa/axios` 或 `getServiceBaseURL` 保证代理前缀正确（项目历史教训）。

### 依赖新增

后端（`uv add`）：
- `sqlglot` — SQL 解析 + 方言转换 + AST 白名单
- `sqlalchemy[asyncio]` — 外部数据源异步执行
- `cryptography` — Fernet 加解密（数据源密码 / LLM API Key）
- `sse-starlette` — SSE 流式输出
- `langchain` / `langchain-core` / `langchain-community` / `langchain-deepseek` / `langchain-openai` / `langgraph` — Agent 框架
- `dashscope` — 通义千问 langchain 集成依赖
- 可选：`clickhouse-connect` / `trino` — 按需安装对应数据源驱动

前端（`pnpm add`）：
- `monaco-editor` — SQL 工作台编辑器

### 配置新增（`.env.example`）

```bash
# BI LLM Provider
LLM_DEFAULT_PROVIDER=deepseek
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b
# BI 加密密钥（Fernet）
BI_CRYPTO_KEY=  # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# BI 配额
BI_QUERY_MAX_ROWS=10000
BI_QUERY_TIMEOUT=30
BI_QUERY_BREAKER_THRESHOLD=10
```

### 复用现有框架

- **RBAC**：复用 `app/core/dependency.py` 的 `DependAuth` / `DependPermission` / `require_buttons`，BI 模块不在业务里硬判 `role_code`。
- **行级 data_scope**：复用 `app/core/data_scope.py` 的 `build_scope_filter`，`scope_id_field` 映射为 `tenant_id`。
- **审计 Radar**：关键节点、权限拒绝、安全事件通过 `radar_log(...)` 写入系统 Radar，BI 模块 `biz_bi_audit_log` 表做业务级留痕。
- **init_helper**：`ensure_menu` / `ensure_role` / `reconcile_menu_subtree` / `refresh_api_list`，BI 模块允许从这里 import。
- **响应契约**：统一用 `Success` / `SuccessExtra` / `Fail`；业务失败用 `BizError(code, msg)`，码段 4000-4499。
- **缓存 / 事件总线**：复用 `app/core/cache.py` + `app/core/event_bus.py`。

## Impact

- **Affected specs**：新增 BI 模块完整规格；不修改系统层 spec。
- **Affected code**：
  - 新增：`app/business/bi/` 全量（~40 个文件）、`web/src/views/bi/` 全量（~12 个文件）、`web/src/service/api/bi*.ts`、`web/src/typings/api/bi.d.ts`、`web/src/locales/langs/_generated/bi/`、`migrations/` 新增迁移文件。
  - 修改：`pyproject.toml`（新增依赖）、`web/package.json`（新增 monaco-editor）、`.env.example`（新增 BI 配置项）。
  - 不动：`app/core/*`、`app/system/*`、`app/business/hr/*`、`justfile`、`deploy/`、`docker-compose.yml`。
- **Breaking changes**：无（纯新增模块，可独立开关 `BUSINESS_MODULES_DISABLED=bi`）。

## ADDED Requirements

### Requirement: BI 模块 manifest 注册与自动加载

系统 SHALL 通过 autodiscover 自动发现 `app/business/bi/module.py` 的 `BusinessModule` 声明，注册路由前缀 `/api/v1/business/bi/`，并在启动时由 leader worker 串行执行 `init_data.init()` 写入菜单/角色/按钮码种子。

#### Scenario: 首次启动初始化

- **WHEN** 系统首次启动且 BI 模块未被 `BUSINESS_MODULES_DISABLED` 禁用
- **THEN** leader worker 执行 `init()`，写入 `bi` 顶级菜单 + 6 个子菜单 + ~20 个按钮码 + 2 个角色（`R_BI_ADMIN` / `R_BI_ANALYST`）
- **AND** `reconcile_menu_subtree` 启用 IaC 模式，BI 子树作为单一数据源
- **AND** API 列表通过 `refresh_api_list()` 同步 BI 路由的 `(method, path)` 元数据
- **AND** 启动日志无 `ensure_role` 解析失败告警

### Requirement: 数据源加密存储与管理

系统 SHALL 用 `cryptography.fernet` 加密数据源密码与 LLM API Key，密钥来自 `.env` 的 `BI_CRYPTO_KEY`。

#### Scenario: 创建数据源

- **WHEN** 用户通过 `POST /api/v1/business/bi/datasources` 提交包含明文密码的数据源
- **THEN** 系统用 Fernet 加密密码后存入 `biz_bi_datasource.password`
- **AND** 任何 API 响应不返回密码字段（仅返回脱敏占位符 `***`）

#### Scenario: 测试数据源连接

- **WHEN** 用户调用 `POST /api/v1/business/bi/datasources/{id}/test`
- **THEN** 系统解密密码，用 SQLAlchemy 异步建立连接
- **AND** 连接成功返回 `Success`，失败返回 `BizError(4001, "数据源连接失败: ...")`

### Requirement: 元数据自动采集

系统 SHALL 支持通过 `POST /api/v1/business/bi/datasources/{id}/sync` 触发数据源元数据采集，结果存入 `biz_bi_table` / `biz_bi_column` / `biz_bi_index` / `biz_bi_foreign_key` 表。

#### Scenario: 采集元数据

- **WHEN** 用户调用 sync API
- **THEN** 系统连接目标数据源，分批采集（每次 100 张表）
- **AND** 采集字段：表名/表注释/行数、列名/数据类型/主键/可空/注释、索引、外键、前 5 行样例数据
- **AND** 采集完成后更新 `BiDatasource.last_synced_at`
- **AND** 单数据源采集 < 60 秒

### Requirement: NL2SQL Agent 流水线（LangGraph DAG）

系统 SHALL 用 LangGraph StateGraph 实现 5 节点固定 DAG 流水线：`intent → sql_gen → sql_validate → executor → explain`，固定 LLM 调用次数最多 3 次（intent + sql_gen + 可选 explain）。

#### Scenario: 完整 NL2SQL 流程

- **WHEN** 用户通过 `POST /api/v1/business/bi/chat/send` 发送自然语言问题
- **THEN** 系统通过 SSE 流式推送 `step` 事件（含 `node` + `status` + `data`）
- **AND** Node 1（intent）：LLM 识别意图类型，规则兜底
- **AND** Node 2（sql_gen）：注入 Schema 元数据 + 替换 `{xxx}` 占位符为真实表名（项目历史教训）+ LLM 生成 SQL
- **AND** Node 3（sql_validate）：sqlglot AST 白名单 + 列脱敏 + 行级 `tenant_id` 注入（跳过无 FROM 的 SELECT，项目历史教训）
- **AND** Node 4（executor）：配额限制 + SQLAlchemy 异步执行
- **AND** Node 5（explain）：执行成功才进入，LLM 生成中文解读 + 推荐图表类型
- **AND** 流程结束推送 `final` 事件，含最终结果 + 图表推荐
- **AND** 任何节点失败推送 `error` 事件，**并持久化 assistant 消息到 `biz_bi_chat_message`**（项目历史教训：避免用户看到"无结果"）

#### Scenario: SQL 占位符替换（防 LLM 字面量复制）

- **WHEN** `BiMetric.sql_template` 含 `{order}` 等 Jinja 风格占位符
- **THEN** `sql_gen.py::_resolve_placeholders` 在调用 LLM 前匹配 `BiTable.name`（精确/复数/子串）替换为真实表名
- **AND** LLM 输出后做防御性二次替换
- **AND** 替换失败的 SQL 在校验节点拒绝并返回 `BizError(4101, "SQL 校验失败: 占位符未替换")`

#### Scenario: 多租户行级注入

- **WHEN** 当前用户 `data_scope != all`
- **THEN** `sandbox/tenant.py` 给 SELECT 自动注入 `WHERE tenant_id = :scope`
- **AND** 跳过无 FROM 子句的 SELECT 节点（避免 `SELECT ... WHERE ...` 无 FROM 语法错误，项目历史教训）
- **AND** `scope` 值来自用户的 `scope_id`

### Requirement: SQL 安全引擎

系统 SHALL 通过 `sandbox/whitelist.py` 实施 sqlglot AST 白名单校验。

#### Scenario: 白名单校验

- **WHEN** 任何 SQL 进入校验节点（NL2SQL 生成或 SQL 工作台直连）
- **THEN** 仅允许 `SELECT` / `WITH` / `EXPLAIN`
- **AND** 禁止 `INSERT` / `UPDATE` / `DELETE` / `DROP` / `TRUNCATE` / `ALTER` / `CREATE`
- **AND** 禁止文件操作（`LOAD_FILE` / `INTO OUTFILE`）/ 命令执行（`pg_read_file`）/ 导出函数
- **AND** 多语句拦截（分号检测）
- **AND** 注释拦截（`--` / `/* */`）
- **AND** 无 LIMIT 的 SELECT 自动添加 `LIMIT 1000`；聚合查询自动添加 `LIMIT 100`

#### Scenario: 配额限制

- **WHEN** 单次查询执行
- **THEN** 最大行数 10000（`BI_QUERY_MAX_ROWS` 可配）
- **AND** 超时 30 秒（`BI_QUERY_TIMEOUT` 可配）
- **AND** 单用户失败次数 > 10 次/分钟触发熔断（`BI_QUERY_BREAKER_THRESHOLD` 可配）

### Requirement: LLM Provider 抽象与切换

系统 SHALL 提供 5 种 LLM Provider（DeepSeek / Ollama / 通义千问 / OpenAI / Mock），基于 langchain `BaseChatModel` 实现，按 `LLM_DEFAULT_PROVIDER` 路由，默认 DeepSeek。

#### Scenario: 默认 Provider 调用

- **WHEN** Agent 节点调用 LLM
- **THEN** `BiLLMRouter.get_default()` 返回 `LLM_DEFAULT_PROVIDER` 对应的 Provider 实例
- **AND** Provider 不可用时返回 `BizError(4200, "LLM Provider 不可用")`
- **AND** 测试路径与正式路径**使用相同的 fallback 逻辑**（项目历史教训：`order_by("order", "id")` fallback，避免"测试通过但聊天 404"）

#### Scenario: Provider 测试

- **WHEN** 用户调用 `POST /api/v1/business/bi/llm/providers/{id}/test`
- **THEN** 系统用 Provider 配置发送测试 prompt
- **AND** 返回响应内容 + 耗时 + token 用量

### Requirement: SQL 工作台

系统 SHALL 提供面向分析师/DBA 的 SQL 工作台，前端使用 Monaco Editor。

#### Scenario: 执行 SQL

- **WHEN** 用户在工作台编写 SQL 并点击执行
- **THEN** `POST /api/v1/business/bi/sql/run` 接收 SQL + 数据源 ID
- **AND** 复用 `sandbox/whitelist.py` 安全检查
- **AND** 执行结果分页返回（20/50/100/200 条/页）
- **AND** 实时显示执行耗时
- **AND** 写操作开关通过环境变量 / 数据源配置控制

#### Scenario: 表右键菜单

- **WHEN** 用户在表列表右键
- **THEN** 提供"查看表结构 / 生成 SELECT 语句 / 预览前 100 行"
- **AND** 调用 `/sql/preview/{table_name}` 与 `/sql/generate-select/{table_name}`

### Requirement: 审计日志双层记录

系统 SHALL 通过 `radar_log(...)` 与 `biz_bi_audit_log` 表双层记录 5 类核心操作。

#### Scenario: 审计查询

- **WHEN** BI 管理员通过 `POST /api/v1/business/bi/audit/search` 查询
- **THEN** 支持按日志类型、操作人、时间范围筛选
- **AND** 返回统计卡片（总数 / 成功 / 失败 / 成功率）
- **AND** 日志详情含 TraceID / IP / 资源信息 / JSON 详情 / 错误信息
- **AND** 支持分页（20/50/100 条/页）

### Requirement: 指标管理

系统 SHALL 提供指标 CRUD + 测试能力，指标绑定 SQL 模板与数据源。

#### Scenario: 指标测试

- **WHEN** 用户调用 `POST /api/v1/business/bi/metrics/{id}/test`
- **THEN** 系统用指标的 SQL 模板在绑定的数据源上执行
- **AND** 返回执行结果 + 耗时
- **AND** 业务用户通过 `B_BI_METRIC_VIEW` 按钮码控制可见性

### Requirement: 前端 6 个 BI 页面

系统 SHALL 在 `web/src/views/bi/` 提供 6 个页面，由 Elegant Router 自动生成路由。

#### Scenario: 页面路由

- **WHEN** 用户访问 BI 菜单
- **THEN** 6 个页面可访问：`/bi/chat` / `/bi/metadata` / `/bi/sql-workbench` / `/bi/metrics` / `/bi/models` / `/bi/audit`
- **AND** 路由名分别为 `bi_chat` / `bi_metadata` / `bi_sql-workbench` / `bi_metrics` / `bi_models` / `bi_audit`（连字符格式匹配 elegant-router 生成规则）
- **AND** i18n 翻译键完整，无 raw key 显示

#### Scenario: 智能对话页面

- **WHEN** 用户在 chat 页面输入自然语言问题
- **THEN** SSE 流式接收 step/final/error 事件
- **AND** 实时显示节点状态（意图识别 → SQL 生成 → 校验 → 执行 → 解释）
- **AND** 自动渲染 ECharts 图表（柱状/折线/饼图/表格）
- **AND** 侧边栏展示历史会话，支持删除和切换
- **AND** 支持 PNG 导出（`getDataURL(pixelRatio=2)`）+ CSV 导出（带 BOM 头）

### Requirement: RBAC 角色与按钮码

系统 SHALL 通过 `init_data.py` 声明 2 个 BI 角色 + ~20 个按钮码，启动时幂等写入。

#### Scenario: 角色权限

- **WHEN** 用户分配 `R_BI_ADMIN` 角色
- **THEN** 拥有全部 BI 菜单 + 全部按钮码 + `data_scope=all`
- **AND** 用户分配 `R_BI_ANALYST` 角色
- **THEN** 拥有 `bi_chat` / `bi_sql-workbench` / `bi_metrics` 菜单 + 对应按钮码 + `data_scope=scope` 或 `self`

## MODIFIED Requirements

### Requirement: 业务模块 autodiscover

[现有] autodiscover 自动发现 `app/business/*/module.py` 的 `BusinessModule` 声明。

[修改] 同上，新增 `bi` 模块自动纳入发现范围；可通过 `BUSINESS_MODULES_DISABLED=bi` 禁用。

## REMOVED Requirements

无移除项。
