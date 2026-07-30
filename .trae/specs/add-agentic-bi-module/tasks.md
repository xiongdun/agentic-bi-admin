# Tasks

按依赖顺序组织；同一阶段的子任务可并行。每个任务完成后必须勾选 `[x]`。

## 阶段 A：基础设施与依赖

- [x] Task 1: 添加后端依赖与模块骨架 ✅
  - [x] SubTask 1.1: `uv add sqlglot sqlalchemy[asyncio] cryptography sse-starlette langchain langchain-core langchain-community langchain-deepseek langchain-openai langgraph dashscope`
  - [x] SubTask 1.2: 创建 `app/business/bi/` 目录结构
  - [x] SubTask 1.3: 编写 `module.py` manifest
  - [x] SubTask 1.4: 验证 `just run backend` 启动无报错（granian 4 workers on :9999，autodiscover 识别 bi 模块）

- [x] Task 2: 添加前端依赖与 i18n 骨架 ✅
  - [x] SubTask 2.1: `pnpm add monaco-editor`
  - [x] SubTask 2.2: 创建 `web/src/locales/langs/_generated/bi/` 目录
  - [x] SubTask 2.3: 创建 `web/src/views/bi/` 6 个页面目录占位
  - [x] SubTask 2.4: 创建 `web/src/service/api/bi*.ts` 6 个 API 文件占位 + `web/src/typings/api/bi.d.ts`

- [x] Task 3: 更新 `.env.example` 与 `.env` ✅
  - [x] SubTask 3.1: 在 `.env.example` 追加 BI 配置项
  - [x] SubTask 3.2: `.env` 已存在但未修改（用户私有配置）

## 阶段 B：数据模型与种子

- [x] Task 4: 实现 13 个 Tortoise ORM 模型 ✅
  - [x] SubTask 4.1: 5 个 metadata 模型（BiDatasource 加 SoftDeleteMixin + tenant_id / BiTable / BiColumn / BiIndex / BiForeignKey）
  - [x] SubTask 4.2: BiMetric + BiChatSession（tenant_id）/ BiChatMessage + BiLLMProvider / BiLLMModel + BiAuditLog + BiMaskingRule / BiQuotaConfig
  - [x] SubTask 4.3: FK 上方声明 `<name>_id: int` 注解；字段写 description；类 docstring 中文资源名；文件头加 pyright 覆盖声明

- [x] Task 5: 生成迁移并应用 ✅
  - [x] SubTask 5.1: `just db-reset` 重建基线（用户授权）→ 生成 `0001_initial.py` 含 13 张 `biz_bi_*` 表
  - [x] SubTask 5.2: 应用迁移成功；启动后端无 "Module has no models" 警告；DB 验证 13 张表 + 7 菜单 + 2 角色写入

- [x] Task 6: 实现 `init_data.py` 种子 ✅
  - [x] SubTask 6.1: `BI_MENU_CHILDREN`（6 子菜单 + 20 按钮码）+ 顶级 `bi` 菜单（reconcile 启用 IaC）
  - [x] SubTask 6.2: 2 个角色（R_BI_ADMIN all / R_BI_ANALYST scope）+ 按钮码分配；apis 留空避免告警
  - [x] SubTask 6.3: `init()` 含 `await apply_init_data(INIT_DATA)`
  - [x] SubTask 6.4: 启动验证：菜单/角色全部 ensure 成功，无 missing 告警

## 阶段 C：后端安全与基础设施层

- [x] Task 7: 实现 `security/crypto.py`（Fernet 加解密）✅
  - [x] SubTask 7.1: 封装 `encrypt` / `decrypt` / `mask`，密钥来自 `BI_CRYPTO_KEY`（通过 BIZ_SETTINGS 单例读取）
  - [x] SubTask 7.2: 加解密往返测试通过；config.py 扩展为 BusinessSettings 暴露 BI 配置

- [x] Task 8: 实现 `sandbox/whitelist.py`（sqlglot AST 白名单）✅
  - [x] SubTask 8.1: `validate_sql` 仅允许 SELECT/WITH/UNION
  - [x] SubTask 8.2: 禁止写操作/文件操作/命令执行/导出函数（20 项测试通过）
  - [x] SubTask 8.3: 多语句拦截 + 注释拦截
  - [x] SubTask 8.4: 自动 LIMIT 1000（普通）/ LIMIT 100（聚合）

- [x] Task 9: 实现 `sandbox/dialect.py`（方言转换）✅
  - [x] SubTask 9.1: `to_dialect` / `get_dialect_name` / `format_sql`，支持 5 种方言

- [x] Task 10: 实现 `sandbox/masking.py`（列脱敏）✅
  - [x] SubTask 10.1: `mask_columns` 批量脱敏，正则预编译，不修改原数据
  - [x] SubTask 10.2: 手机号/身份证/邮箱/银行卡/自定义 5 种脱敏类型

- [x] Task 11: 实现 `sandbox/tenant.py`（多租户行级注入）✅
  - [x] SubTask 11.1: `inject_tenant_filter` 基于 sqlglot AST
  - [x] SubTask 11.2: 跳过无 FROM 子句的 SELECT 节点（**发现 sqlglot 30.x key 从 "from" 改为 "from_"**，已兼容两种 key）

- [x] Task 12: 实现 `sandbox/quota.py` + `sandbox/executor.py` ✅
  - [x] SubTask 12.1: `quota.py` 熔断/行数/超时检查，默认值从环境变量读取
  - [x] SubTask 12.2: `executor.py` 用 SQLAlchemy async engine + `asyncio.wait_for` 真正应用超时
  - [x] SubTask 12.3: 引擎按 `datasource_id` 缓存复用

## 阶段 D：LLM Provider 抽象

- [x] Task 13: 实现 `llm/base.py` + 5 个 Provider + `router.py` ✅
  - [x] SubTask 13.1: `base.py` 定义 `BaseLLMProvider` + `ChatResult`，封装 langchain BaseChatModel，`async chat()` / `test_connection()`
  - [x] SubTask 13.2: `deepseek.py` 用 `langchain_deepseek.ChatDeepSeek`，配置优先 DB 回退 .env
  - [x] SubTask 13.3: `ollama.py` 双路径导入（langchain_ollama 优先，回退 langchain_community）
  - [x] SubTask 13.4: `qwen.py` 用 `ChatTongyi`，temperature 通过 `model_kwargs` 传递
  - [x] SubTask 13.5: `openai.py` 用 `langchain_openai.ChatOpenAI`
  - [x] SubTask 13.6: `mock.py` 关键词匹配预设响应
  - [x] SubTask 13.7: `router.py` 三路径（get_default / get_default_from_db / get_provider_by_id）共用 `_resolve_provider()` 确保 fallback 一致（项目历史教训）

## 阶段 E：Metadata 采集

- [x] Task 14: 实现 `metadata/sync.py` + `sampler.py` + `relations.py` ✅
  - [x] SubTask 14.1: `sync.py` 实现 `sync_datasource`，分批采集（BI_METADATA_BATCH_SIZE 默认 100），支持 5 种数据库
  - [x] SubTask 14.2: `sampler.py` 实现 `sample_table_data` / `sample_column_values`
  - [x] SubTask 14.3: `relations.py` 实现 `extract_foreign_keys`，按 db_type 分发
  - [x] SubTask 14.4: `init_data.init()` 调用 `_ensure_default_datasource_metadata`（项目历史教训）

## 阶段 F：Agent 流水线（LangGraph DAG）

- [x] Task 15: 实现 `agent/state.py` ✅
  - [x] SubTask 15.1: `AgentState` TypedDict（question / intent_type / sql_text / sql_result / explanation / chart_type / steps / error / token_usage 等）
  - [x] SubTask 15.2: `StepTrace` TypedDict（node / status / data / elapsed_ms / error）

- [x] Task 16: 实现 `agent/nodes/intent.py`（意图识别）✅
  - [x] SubTask 16.1: `intent_node` LLM 识别 + `_rule_based_intent` 关键词兜底
  - [x] SubTask 16.2: 推送 step 事件（通过 runner 的 astream）

- [x] Task 17: 实现 `agent/nodes/sql_gen.py`（SQL 生成）✅
  - [x] SubTask 17.1: `_resolve_placeholders` 精确/复数/单数/子串匹配（项目历史教训）
  - [x] SubTask 17.2: `_build_schema_text` 空表返回提示文本（项目历史教训）
  - [x] SubTask 17.3: `sql_gen_node` 注入 Schema + 替换占位符 + LLM 生成 + 防御性二次替换 + markdown 清理

- [x] Task 18: 实现 `agent/nodes/sql_validate.py`（SQL 校验）✅
  - [x] SubTask 18.1: 调用 `validate_sql` AST 白名单 + 自动 LIMIT
  - [x] SubTask 18.2: 调用 `mask_columns`（在 executor 后对结果脱敏，本节点准备规则）
  - [x] SubTask 18.3: 调用 `inject_tenant_filter` 行级注入（跳过无 FROM 的 SELECT，Task 11 已处理）

- [x] Task 19: 实现 `agent/nodes/executor.py`（执行）✅
  - [x] SubTask 19.1: 调用 `execute_sql` 配额检查 + 异步执行
  - [x] SubTask 19.2: 失败时通过条件边跳过 explain（runner 实现）

- [x] Task 20: 实现 `agent/nodes/explain.py`（结果解释）✅
  - [x] SubTask 20.1: `explain_node` LLM 生成中文解读 + `_infer_chart_type` 推荐图表类型

- [x] Task 21: 实现 `agent/runner.py`（LangGraph StateGraph 编排）✅
  - [x] SubTask 21.1: `StateGraph(AgentState)` 构建 5 节点 DAG
  - [x] SubTask 21.2: 条件边：executor 成功 → explain；失败 → END
  - [x] SubTask 21.3: `run_chat_turn` 用 `graph.astream(stream_mode="updates")` 流式产出
  - [x] SubTask 21.4: `_persist_error_message` 在两处错误路径调用（项目历史教训）

## 阶段 G：SSE 与 API 层

- [x] Task 22: 实现 `sse.py`（SSE 事件封装）✅
  - [x] SubTask 22.1: 基于 `EventSourceResponse(ping=15)`，不使用 asyncio.wait_for（项目历史教训）
  - [x] SubTask 22.2: 事件类型 step / final / error / heartbeat
  - [x] SubTask 22.3: 用 `JSONServerSentEvent` + `json.dumps` 避免双 data: 前缀（项目历史教训）

- [x] Task 23: 实现 schemas + controllers + services ✅
  - [x] SubTask 23.1: `schemas.py` 13 个模型的 SchemaBase/PageQuery/Create/Update/Out + 自定义 ChatSend/SqlRun/AuditSearch schema
  - [x] SubTask 23.2: `controllers.py` CRUDBase 子类 + build_search 过滤
  - [x] SubTask 23.3: `services.py` 跨模型编排（test/sync/send/run/preview/generate-select/test_metric/test_llm/search_audit/export）

- [x] Task 24: 实现 `api/datasource.py` + `api/metadata.py` ✅
  - [x] SubTask 24.1: datasource.py CRUDRouter + /test + /sync，按钮码 B_BI_DS_*
  - [x] SubTask 24.2: metadata.py 表/列详情接口

- [x] Task 25: 实现 `api/chat.py`（SSE 流式对话）✅
  - [x] SubTask 25.1: 会话 CRUD + 消息列表
  - [x] SubTask 25.2: /chat/send 返回 SSE 流，调用 agent/runner.run_chat_turn
  - [x] SubTask 25.3: 持久化用户与 assistant 消息

- [x] Task 26: 实现 `api/sql_workbench.py` + `api/metric.py` + `api/llm.py` + `api/audit.py` ✅
  - [x] SubTask 26.1: sql_workbench.py 6 个端点（run/explain/format/history/preview/generate-select）
  - [x] SubTask 26.2: metric.py CRUDRouter + /test
  - [x] SubTask 26.3: llm.py CRUDRouter + /test
  - [x] SubTask 26.4: audit.py CRUDRouter + 统计/导出

- [x] Task 27: 聚合 router 与路由权限校验 ✅
  - [x] SubTask 27.1: api/__init__.py 聚合 7 个子路由
  - [x] SubTask 27.2: 写接口挂载 require_buttons
  - [x] SubTask 27.3: 48 条 BI 路由注册，权限对齐 0 缺失，`just check` 通过

## 阶段 H：前端实现

- [x] Task 28: 前端类型定义与 API 服务 ✅
  - [x] SubTask 28.1: `typings/api/bi.d.ts` 定义 `Api.Bi.*` 完整类型（13 个实体 + SSE 事件 + 分页 + 详情）
  - [x] SubTask 28.2: 6 个 `service/api/bi*.ts` 实现 API 调用，用 `@sa/axios` / `request` 保证代理前缀

- [x] Task 29: 前端 i18n 完整翻译 ✅
  - [x] SubTask 29.1: `zh-cn.ts` / `en-us.ts` 完整翻译（6 个路由名 + 表单字段 + 按钮文案）
  - [x] SubTask 29.2: `types.d.ts` 通过 `GeneratedPages` 接口声明合并

- [x] Task 30: 智能对话页面 ✅
  - [x] SubTask 30.1: `chat/index.vue` 主布局（左侧会话列表 + 右侧消息流 + 输入框）
  - [x] SubTask 30.2: `modules/session-list.vue` 历史会话（删除/切换/折叠）
  - [x] SubTask 30.3: `modules/message-renderer.vue` 消息渲染（SSE step 实时显示 + ECharts 自动图表）
  - [x] SubTask 30.4: SSE 接入用 `fetch` + `ReadableStream`，处理 step/final/error/heartbeat 事件
  - [x] SubTask 30.5: 图表导出 PNG（`getDataURL(pixelRatio=2)`）+ CSV 导出带 BOM 头

- [x] Task 31: 元数据管理页面 ✅
  - [x] SubTask 31.1: `metadata/index.vue` 数据源选择 + 统计卡片 + 表/列 Tab 视图
  - [x] SubTask 31.2: `modules/datasource-operate-modal.vue` 数据源 CRUD 表单（密码 `***` 遮蔽）
  - [x] SubTask 31.3: `modules/column-detail-drawer.vue` 字段详情抽屉
  - [x] SubTask 31.4: test/sync 按钮挂载 `B_BI_DS_TEST` / `B_BI_DS_SYNC`

- [x] Task 32: SQL 工作台页面 ✅
  - [x] SubTask 32.1: `sql-workbench/index.vue` 主布局（左侧表列表 + 右侧编辑器 + 结果区）
  - [x] SubTask 32.2: 集成 Monaco Editor（语法高亮 + 行号 + 自动布局 + dispose 清理）
  - [x] SubTask 32.3: 表右键菜单（查看表结构 / 生成 SELECT / 预览前 100 行）
  - [x] SubTask 32.4: 结果表格分页（20/50/100/200）+ 执行耗时显示
  - [x] SubTask 32.5: ECharts 配置面板（柱状/折线/饼图/散点）

- [x] Task 33: 指标管理页面 ✅
  - [x] SubTask 33.1: `metrics/index.vue` 指标列表 + CRUD
  - [x] SubTask 33.2: `modules/metric-operate-modal.vue` 指标表单
  - [x] SubTask 33.3: `modules/metric-test-modal.vue` 指标测试结果展示

- [x] Task 34: LLM 配置页面 ✅
  - [x] SubTask 34.1: `models/index.vue` Provider 列表 + CRUD
  - [x] SubTask 34.2: `modules/provider-operate-modal.vue` Provider 表单（API Key `***` 遮蔽）

- [x] Task 35: 审计日志页面 ✅
  - [x] SubTask 35.1: `audit/index.vue` 统计卡片（总数/成功/失败/成功率）+ 多维度筛选
  - [x] SubTask 35.2: 日志详情展开（TraceID/IP/资源/JSON 详情/错误信息）
  - [x] SubTask 35.3: CSV 导出按钮挂载 `B_BI_AUDIT_EXPORT`

## 阶段 I：端到端验证

- [x] Task 36: 端到端验证 ✅
  - [x] SubTask 36.1: 启动后端 + 前端，无报错
  - [x] SubTask 36.2: 配置一个数据源（如本地 SQLite 或测试 PostgreSQL），触发元数据同步
  - [x] SubTask 36.3: 配置 DeepSeek Provider 并测试通过（注：因未提供 DeepSeek API Key，暂用 Mock Provider 验证 CRUD + /test 链路通过；DeepSeek 真实 LLM 质量验证待 API Key）
  - [x] SubTask 36.4: 在 chat 页面输入"今天销售情况"或类似问题，验证 NL2SQL 完整流程（intent → sql_gen → validate → executor → explain）
  - [x] SubTask 36.5: 在 SQL 工作台执行直连 SQL
  - [x] SubTask 36.6: 在审计页面查看操作记录
  - [x] SubTask 36.7: 运行 `just check` 通过（前后端门禁）

# Task Dependencies

- Task 2 / Task 3 可与 Task 1 并行
- Task 4 依赖 Task 1
- Task 5 依赖 Task 4
- Task 6 依赖 Task 4
- Task 7-12（后端基础设施层）可并行（依赖 Task 1）
- Task 13（LLM）依赖 Task 7（crypto）
- Task 14（metadata）依赖 Task 8-12（sandbox）
- Task 15-21（Agent）依赖 Task 13 + Task 14
- Task 22（SSE）依赖 Task 21
- Task 23-27（API）依赖 Task 22
- Task 28-35（前端）依赖 Task 27（API 稳定）
- Task 36 依赖所有前置任务完成
