# Checklist

## 阶段 A：基础设施与依赖

- [x] `pyproject.toml` 包含 sqlglot / sqlalchemy[asyncio] / cryptography / sse-starlette / langchain / langchain-core / langchain-community / langchain-deepseek / langchain-openai / langgraph / dashscope
- [x] `web/package.json` 包含 monaco-editor
- [x] `app/business/bi/` 目录结构完整（含 `api/` / `agent/` / `agent/nodes/` / `sandbox/` / `metadata/` / `llm/` / `security/` 子包）
- [x] `module.py` manifest 声明正确（BusinessModule + ENDPOINT_RATE_LIMITS + PermissionSpec）
- [x] `.env.example` 包含 BI 配置项（`LLM_DEFAULT_PROVIDER` / `DEEPSEEK_*` / `OLLAMA_*` / `BI_CRYPTO_KEY` / `BI_QUERY_*`）
- [x] 启动后端无报错，autodiscover 识别 bi 模块（granian 4 workers on :9999）

## 阶段 B：数据模型与种子

- [x] `models.py` 实现 13 个模型，表名 `biz_bi_*`，继承 `BaseModel + AuditMixin`
- [x] 每个 `ForeignKeyField` 上方声明 `<name>_id: int` 注解
- [x] 字段写 `description`，类 docstring 写中文资源名
- [x] 文件头有 `# pyright: reportIncompatibleVariableOverride=false`
- [x] `just db-reset` 重建基线并应用迁移成功（13 张 `biz_bi_*` 表）
- [x] `init_data.py` 声明 6 个子菜单 + 20 个按钮码 + 2 个角色
- [x] 顶级 `bi` 菜单 `reconcile={"menus": True, "buttons": True}` 启用 IaC
- [x] `init()` 函数包含 `await apply_init_data(INIT_DATA)`
- [x] 启动后菜单/角色/按钮码写入数据库，无 `ensure_role` 解析失败告警

## 阶段 C：后端安全与基础设施层

- [x] `security/crypto.py` 实现 Fernet `encrypt` / `decrypt`，密钥来自 `BI_CRYPTO_KEY`
- [x] `sandbox/whitelist.py` 仅允许 SELECT/WITH/UNION，禁止写操作/文件操作/命令执行/导出函数
- [x] `sandbox/whitelist.py` 拦截多语句（分号）与注释（`--` / `/* */`）
- [x] `sandbox/whitelist.py` 自动添加 LIMIT 1000（普通 SELECT）或 LIMIT 100（聚合查询）
- [x] `sandbox/dialect.py` 支持 PostgreSQL/MySQL/ClickHouse/Trino/SQLite 方言转换
- [x] `sandbox/masking.py` 支持手机号/身份证/邮箱/银行卡脱敏
- [x] `sandbox/tenant.py` 给 SELECT 注入 `WHERE tenant_id = :scope`
- [x] `sandbox/tenant.py` **跳过无 FROM 子句的 SELECT 节点**（兼容 sqlglot 30.x 的 `from_` key 变更）
- [x] `sandbox/quota.py` 实现行数/超时/熔断检查，默认值从环境变量读取
- [x] `sandbox/executor.py` 用 SQLAlchemy async engine 执行 SQL，按 datasource_id 缓存引擎

## 阶段 D：LLM Provider 抽象

- [x] `llm/base.py` 定义 `BaseLLMProvider`，封装 langchain BaseChatModel
- [x] 5 个 Provider 实现（deepseek/ollama/qwen/openai/mock），配置优先 DB 回退 .env
- [x] `llm/router.py` 按 `LLM_DEFAULT_PROVIDER` 路由，默认 DeepSeek
- [x] **测试路径与正式路径使用相同 fallback 逻辑**（共用 `_resolve_provider()`，项目历史教训）
- [x] Provider 不可用时返回 `BizError(4200)`

## 阶段 E：Metadata 采集

- [x] `metadata/sync.py` 分批采集（默认 100 张表），结果写入 4 个元数据表，支持 5 种数据库
- [x] `metadata/sampler.py` 默认采样 5 行样例数据
- [x] `metadata/relations.py` 提取外键关系，按 db_type 分发
- [x] `init_data.init()` 在 `BiTable` 为空时自动触发默认数据源同步（项目历史教训）

## 阶段 F：Agent 流水线（LangGraph DAG）

- [x] `agent/state.py` 定义 `AgentState` + `StepTrace` TypedDict
- [x] `intent.py` LLM 识别意图 + 规则兜底
- [x] `sql_gen.py` 实现 `_resolve_placeholders`（精确/复数/单数/子串匹配，项目历史教训）
- [x] `sql_gen.py` 实现 `_build_schema_text`，空 schema 返回提示文本
- [x] `sql_gen.py` LLM 输出后做防御性二次占位符替换
- [x] `sql_validate.py` 调用 whitelist + tenant 注入
- [x] `executor.py` 调用 quota + executor，失败时通过条件边跳过 explain
- [x] `explain.py` LLM 生成中文解读 + 推荐图表类型
- [x] `runner.py` 用 LangGraph StateGraph 构建 5 节点 DAG
- [x] `runner.py` 条件边：executor 成功 → explain；失败 → END
- [x] `runner.py` 用 `graph.astream(stream_mode="updates")` 流式产出
- [x] `runner.py` 错误处理：`_persist_error_message` 在节点级和 runner 级错误路径调用（项目历史教训）
- [x] 固定 LLM 调用次数最多 3 次（intent + sql_gen + explain）

## 阶段 G：SSE 与 API 层

- [x] `sse.py` 用 `EventSourceResponse(ping=15)`，不使用 `asyncio.wait_for` 包 `__anext__`（项目历史教训）
- [x] `sse.py` 用 `JSONServerSentEvent` + `json.dumps` 避免双 `data:` 前缀（项目历史教训）
- [x] 事件类型完整：step / final / error / heartbeat
- [x] `schemas.py` 所有对外 ID 用 `SqidId` / `SqidPath`
- [x] `schemas.py` SQID 参数在 request schema 中定义为 str 类型，API 层解码（项目历史教训）
- [x] `schemas.py` Update schema 用 `make_optional`
- [x] `controllers.py` 继承 `CRUDBase` + `build_search`
- [x] `services.py` 实现跨模型编排与缓存
- [x] `api/datasource.py` CRUDRouter + test/sync，按钮码 `B_BI_DS_*`
- [x] `api/metadata.py` CRUDRouter + 表/列详情
- [x] `api/chat.py` SSE 流式 `/chat/send`，持久化用户与 assistant 消息
- [x] `api/sql_workbench.py` 实现 6 个端点（run/explain/format/history/preview/generate-select）
- [x] `api/metric.py` CRUDRouter + test
- [x] `api/llm.py` CRUDRouter + test
- [x] `api/audit.py` CRUDRouter + 统计/导出
- [x] `api/__init__.py` 聚合 7 个子路由
- [x] 所有写接口挂载 `require_buttons(...)` 依赖
- [x] 48 条 BI 路由注册，权限对齐 0 缺失，`just check` 通过

## 阶段 H：前端实现

- [x] `typings/api/bi.d.ts` 定义 13 个实体类型 + SSE 事件类型
- [x] `service/api/bi*.ts` 用 `@sa/axios` / `request`（项目历史教训）
- [x] `_generated/bi/zh-cn.ts` 与 `en-us.ts` 翻译完整
- [x] `_generated/bi/types.d.ts` 通过 `GeneratedPages` 接口声明合并
- [x] 路由名 `bi_chat` / `bi_metadata` / `bi_sql-workbench` / `bi_metrics` / `bi_models` / `bi_audit`（连字符格式）
- [x] 智能对话页面：SSE 流式（fetch+ReadableStream）+ 节点状态实时显示 + ECharts 自动图表 + 会话历史 + PNG/CSV 导出
- [x] 元数据管理页面：数据源选择 + 统计卡片 + Tab 布局 + 表/列视图 + 字段详情抽屉
- [x] SQL 工作台页面：Monaco Editor + 表列表 + 右键菜单 + 结果分页 + ECharts 配置面板
- [x] 指标管理页面：列表 + CRUD + 测试
- [x] LLM 配置页面：Provider 列表 + CRUD（API Key 遮蔽）
- [x] 审计日志页面：统计卡片 + 多维筛选 + 详情展开 + CSV 导出
- [x] 所有按钮可见性用 `useAuth().hasAuth` 控制
- [x] `pnpm typecheck` + `pnpm lint` 通过

## 阶段 I：端到端验证

- [x] 后端 + 前端启动无报错
- [x] 配置一个数据源并触发元数据同步成功
- [x] Provider 测试通过（注：因未提供 DeepSeek API Key，暂用 Mock Provider 验证；DeepSeek 真实 LLM 验证待 API Key）
- [x] 在 chat 页面输入自然语言问题，NL2SQL 完整流程跑通（intent → sql_gen → validate → executor → explain）
- [x] SSE 流式输出正常，无连接断开
- [x] 在 SQL 工作台执行直连 SQL 成功
- [x] 在审计页面查看操作记录
- [x] `just check` 通过（前后端门禁）
- [ ] 多租户场景：`data_scope != all` 的用户只能看到自己范围内的数据（待手工验证）
- [ ] 错误场景：LLM 不可用时返回 `BizError(4200)`；SQL 校验失败返回 `BizError(4101)`（待手工验证）

### 端到端验证过程中修复的 bug

1. **sqlite 数据源 password 为空时 `decrypt("")` 崩溃** — `app/business/bi/sandbox/executor.py::_build_connection_url` 改为对 sqlite 跳过 decrypt
2. **Guard 把 BI 的合法 SQL/Question 当成 SQL 注入拦截** — `app/core/init_app.py::_make_guard_config` 添加 `excluded_detection_body_fields={"sql","sql_template","question","api_key"}`
3. **.env 缺少 BI_CRYPTO_KEY** — 追加 BI 模块配置段（Fernet 密钥 + 查询配额 + 元数据采样参数）

### 已知待改进项（非阻塞）

- SQL 结果未配置 BiMaskingRule 时会返回敏感字段（如 password 哈希）— 用户需在元数据管理页面配置脱敏规则
- Mock Provider 的 LLM 响应为预设关键词匹配，真实 NL2SQL 质量需配置 DeepSeek API Key 后验证
