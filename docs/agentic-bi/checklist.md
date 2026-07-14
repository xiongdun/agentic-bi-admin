# AgenticBI 实施 Checklist

> SPEC 落地需要做的**所有事项**，按 A-L 12 个域分组。每条都是可勾选、可验证的具体事项。

---

## A. 基础设施（必须先做，后续依赖）

- [ ] **A1.** `app/utils/llm.py` — LLM 抽象层入口（统一 re-export）
- [ ] **A2.** `app/business/bi/llm/base.py` — `BaseChatModel` Protocol + `LLMResponse` dataclass
- [ ] **A3.** `app/business/bi/llm/deepseek.py` — DeepSeek 客户端（OpenAI 兼容 SDK）
- [ ] **A4.** `app/business/bi/llm/ollama.py` — Ollama 客户端（httpx）
- [ ] **A5.** `app/business/bi/llm/qwen.py` — 通义千问客户端
- [ ] **A6.** `app/business/bi/llm/openai.py` — OpenAI 客户端（兼容 GPT-4o）
- [ ] **A7.** `app/business/bi/llm/router.py` — 多 provider 路由（按任务类型 + 降级）
- [ ] **A8.** `app/utils/sqlglot_utils.py` — 方言转换 / 格式化 / 差异比较
- [ ] **A9.** `app/utils/sse.py` — SSE 响应封装（`EventSourceResponse` + 心跳）
- [ ] **A10.** `app/utils/crypto.py` — Fernet 加密（Datasource 密码）
- [ ] **A11.** `pyproject.toml` — 新增依赖：`sqlglot`、`sqlalchemy[asyncio]`、`openai`、`cryptography`、`sse-starlette`
- [ ] **A12.** `.env.example` — LLM 4 个 provider 的 API key 占位 + `LLM_DEFAULT_PROVIDER=deepseek`

---

## B. 数据模型 & 迁移

- [ ] **B1.** `app/business/bi/models.py` — 15 张表 Tortoise 模型
- [ ] **B2.** `app/business/bi/__init__.py` — `BaseModel` / `AuditMixin` 复用
- [ ] **B3.** `just mm` 生成 `migrations/app_business_bi/0001_initial.py`
- [ ] **B4.** 迁移 apply（SQLite 自动）
- [ ] **B5.** `app/business/bi/init_data.py` — 种子（默认租户、默认 R_SUPER 数据源权限）
- [ ] **B6.** `app/business/bi/init_data.py` — 菜单种子（"智能 BI" 顶级 + 4 子菜单 + 按钮权限）
- [ ] **B7.** `app/business/bi/module.py` — manifest（autodiscover 注册）
- [ ] **B8.** `app/business/bi/events.py` — 事件契约（`CHAT_MESSAGE_CREATED` 等）
- [ ] **B9.** `app/business/bi/policies.py` — DataPolicy（`bi.datasource.read` 等）

---

## C. 元数据

- [ ] **C1.** `app/business/bi/services/datasource.py` — Datasource CRUD
- [ ] **C2.** `app/business/bi/services/datasource.py` — `test_connection()` 连通性测试
- [ ] **C3.** `app/business/bi/api/datasource.py` — REST 端点（CRUD + test_connection）
- [ ] **C4.** `app/business/bi/metadata/sync.py` — 拉 schema（按 dialect 分发到 5 个 driver）
- [ ] **C5.** `app/business/bi/metadata/sampler.py` — 列采样（前 10 行 + 5 个非空 distinct 值）
- [ ] **C6.** `app/business/bi/metadata/profiler.py` — 字段统计（min/max/distinct_count）
- [ ] **C7.** `app/business/bi/metadata/sync.py` — 自动发现 Relation（外键 + 命名规则）
- [ ] **C8.** `app/business/bi/api/metadata.py` — `POST /datasources/{id}/sync`
- [ ] **C9.** `app/business/bi/services/table.py` / `column.py` / `synonym.py` — 元数据 CRUD
- [ ] **C10.** `app/business/bi/api/table.py` / `column.py` / `synonym.py` — 元数据 REST

---

## D. SQL 沙箱

- [ ] **D1.** `app/business/bi/sandbox/whitelist.py` — sqlglot AST 白名单（仅 SELECT/WITH/EXPLAIN）
- [ ] **D2.** `app/business/bi/sandbox/whitelist.py` — 禁用函数列表（`pg_read_file` 等）
- [ ] **D3.** `app/business/bi/sandbox/whitelist.py` — 禁用关键字（INTO/UNLOAD/LOAD_FILE）
- [ ] **D4.** `app/business/bi/sandbox/tenant.py` — `inject_tenant_filter()` 自动 WHERE 注入
- [ ] **D5.** `app/business/bi/sandbox/masking.py` — 列脱敏（phone/email/id_card/bank_card）
- [ ] **D6.** `app/business/bi/sandbox/masking.py` — `apply_masks()` SQL 改写
- [ ] **D7.** `app/business/bi/sandbox/quota.py` — Quota 配置（max_rows/timeout/rate_limit）
- [ ] **D8.** `app/business/bi/sandbox/quota.py` — Redis 限流 + 慢查询熔断
- [ ] **D9.** `app/business/bi/sandbox/executor.py` — SQLAlchemy 异步连接池
- [ ] **D10.** `app/business/bi/sandbox/executor.py` — 5 种方言 driver 适配
- [ ] **D11.** `app/business/bi/sandbox/executor.py` — 自动 `LIMIT N` 注入
- [ ] **D12.** `app/business/bi/sandbox/pipeline.py` — validate → mask → tenant → execute 流水线

---

## E. Agent 编排（LangGraph）

- [ ] **E1.** `app/business/bi/agent/state.py` — `AgentState` TypedDict
- [ ] **E2.** `app/business/bi/agent/nodes/intent.py` — Intent Agent（LLM）
- [ ] **E3.** `app/business/bi/agent/nodes/schema_select.py` — Schema Select Agent（LLM + RAG）
- [ ] **E4.** `app/business/bi/agent/nodes/sql_gen.py` — SQL Gen Agent（LLM, CoT）
- [ ] **E5.** `app/business/bi/agent/nodes/sql_validate.py` — Validate Node（本地 sqlglot）
- [ ] **E6.** `app/business/bi/agent/nodes/sql_fix.py` — SQL Fix Agent（LLM, retry 2x）
- [ ] **E7.** `app/business/bi/agent/nodes/executor_node.py` — 沙箱执行 + 失败重试
- [ ] **E8.** `app/business/bi/agent/nodes/chart_recommend.py` — Chart Recommend Agent
- [ ] **E9.** `app/business/bi/agent/nodes/explain.py` — Explain Agent
- [ ] **E10.** `app/business/bi/agent/prompts/intent.py` — Intent prompt
- [ ] **E11.** `app/business/bi/agent/prompts/sql_gen.py` — SQL Gen prompt（few-shot）
- [ ] **E12.** `app/business/bi/agent/prompts/sql_fix.py` — Fix prompt
- [ ] **E13.** `app/business/bi/agent/prompts/chart.py` — Chart prompt
- [ ] **E14.** `app/business/bi/agent/prompts/explain.py` — Explain prompt
- [ ] **E15.** `app/business/bi/agent/graph.py` — LangGraph DAG 编排
- [ ] **E16.** `app/business/bi/agent/runner.py` — FastAPI 异步桥接
- [ ] **E17.** `app/business/bi/agent/runner.py` — 步骤留痕到 `agent_steps_json`

---

## F. 对话 & 执行

- [ ] **F1.** `app/business/bi/services/chat.py` — ChatSession / ChatMessage service
- [ ] **F2.** `app/business/bi/api/chat.py` — 会话/消息 REST
- [ ] **F3.** `app/business/bi/api/chat.py` — SSE 端点 `POST /bi/chat/{session_id}/messages` (streaming)
- [ ] **F4.** `app/business/bi/api/chat.py` — SSE 心跳 / 中断处理
- [ ] **F5.** `app/business/bi/services/execution.py` — QueryExecution service
- [ ] **F6.** `app/business/bi/api/sql_workbench.py` — `POST /bi/sql/execute`（专业用户直执行）
- [ ] **F7.** `app/business/bi/api/sql_workbench.py` — `POST /bi/sql/explain`（EXPLAIN 计划）
- [ ] **F8.** `app/business/bi/api/sql_workbench.py` — `GET /bi/sql/history`（历史）
- [ ] **F9.** `app/business/bi/api/sql_workbench.py` — `POST /bi/sql/save`（保存为视图/snippet）

---

## G. 业务指标

- [ ] **G1.** `app/business/bi/services/metric.py` — Metric service
- [ ] **G2.** `app/business/bi/api/metric.py` — Metric REST
- [ ] **G3.** `app/business/bi/services/dataset.py` — Dataset service
- [ ] **G4.** `app/business/bi/api/dataset.py` — Dataset REST
- [ ] **G5.** `app/business/bi/services/chart.py` — Chart service
- [ ] **G6.** `app/business/bi/api/chart.py` — Chart REST
- [ ] **G7.** SQL Gen Agent 集成 Metric 注入（让 LLM 知道业务定义）

---

## H. 权限

- [ ] **H1.** `app/business/bi/services/grant.py` — DatasourceGrant service
- [ ] **H2.** `app/business/bi/api/grant.py` — Grant REST
- [ ] **H3.** `app/business/bi/services/masking.py` — ColumnMasking service
- [ ] **H4.** `app/business/bi/api/masking.py` — Masking REST
- [ ] **H5.** `app/business/bi/sandbox/pipeline.py` — 沙箱集成 grant 过滤
- [ ] **H6.** `app/business/bi/sandbox/pipeline.py` — 沙箱集成 masking
- [ ] **H7.** `app/business/bi/policies.py` — `bi.datasource.read` DataPolicy（自动按租户 + 角色过滤）
- [ ] **H8.** `app/business/bi/sandbox/tenant.py` — 多租户 tenant_id 注入

---

## I. 审计

- [ ] **I1.** `app/business/bi/services/audit.py` — AuditLog 写入服务
- [ ] **I2.** `app/business/bi/sandbox/pipeline.py` — 沙箱执行时自动写 AuditLog
- [ ] **I3.** `app/business/bi/agent/runner.py` — Agent 步骤入 Radar `user_log`
- [ ] **I4.** `app/business/bi/api/audit.py` — 审计查询 REST
- [ ] **I5.** `app/business/bi/api/audit.py` — 慢查询 / 异常 SQL 聚合
- [ ] **I6.** 数据导出审批（如未来开启写操作时使用）

---

## J. 前端

### J.1 对话工作台
- [ ] **J1.1.** `web/src/views/bi/chat/index.vue` — 主页面
- [ ] **J1.2.** `web/src/views/bi/chat/modules/chat-sessions.vue` — 左侧会话历史
- [ ] **J1.3.** `web/src/views/bi/chat/modules/chat-messages.vue` — 中间消息流
- [ ] **J1.4.** `web/src/views/bi/chat/modules/message-card.vue` — 消息卡片（支持 CoT/SQL/图表折叠）
- [ ] **J1.5.** `web/src/views/bi/chat/modules/sql-block.vue` — SQL 高亮 + 复制 + 格式化
- [ ] **J1.6.** `web/src/views/bi/chat/modules/chart-block.vue` — ECharts 渲染
- [ ] **J1.7.** `web/src/hooks/use-sse.ts` — SSE 客户端封装
- [ ] **J1.8.** `web/src/service/api/bi-chat.ts` — 对话 API
- [ ] **J1.9.** `web/src/typings/api/bi-chat.d.ts` — TS 类型

### J.2 元数据中心
- [ ] **J2.1.** `web/src/views/bi/metadata/index.vue` — 主页面
- [ ] **J2.2.** `web/src/views/bi/metadata/modules/datasource-tree.vue` — 树形
- [ ] **J2.3.** `web/src/views/bi/metadata/modules/column-editor.vue` — 列编辑
- [ ] **J2.4.** `web/src/views/bi/metadata/modules/synonym-editor.vue` — 同义词编辑
- [ ] **J2.5.** `web/src/service/api/bi-metadata.ts` + typings

### J.3 SQL 工作台
- [ ] **J3.1.** `web/src/views/bi/sql-workbench/index.vue` — 主页面
- [ ] **J3.2.** `web/src/views/bi/sql-workbench/modules/sql-editor.vue` — Monaco + 语法高亮
- [ ] **J3.3.** `web/src/views/bi/sql-workbench/modules/execution-history.vue` — 历史侧栏
- [ ] **J3.4.** `web/src/views/bi/sql-workbench/modules/result-table.vue` — 结果表（10 万行虚拟滚动）
- [ ] **J3.5.** `web/src/views/bi/sql-workbench/modules/datasource-switcher.vue` — 数据源切换
- [ ] **J3.6.** `web/src/service/api/bi-sql.ts` + typings

### J.4 审计面板
- [ ] **J4.1.** `web/src/views/bi/audit/index.vue` — 主页面
- [ ] **J4.2.** `web/src/views/bi/audit/modules/audit-table.vue` — 审计表
- [ ] **J4.3.** `web/src/views/bi/audit/modules/slow-query-chart.vue` — 慢查询 ECharts
- [ ] **J4.4.** `web/src/service/api/bi-audit.ts` + typings

### J.5 ECharts 组件
- [ ] **J5.1.** `web/src/components/echarts/echart-renderer.vue` — 通用 ECharts 渲染
- [ ] **J5.2.** `web/src/components/echarts/charts/` — 10+ 图表类型
  - [ ] bar.vue, line.vue, pie.vue, funnel.vue, sankey.vue
  - [ ] radar.vue, heatmap.vue, scatter.vue, area.vue, map-china.vue

### J.6 SSE / Web 通用
- [ ] **J6.1.** `web/src/hooks/use-sse.ts` — 通用 SSE 客户端
- [ ] **J6.2.** `web/src/views/bi/chat/__tests__/chat.test.ts` — vitest

---

## K. 演示数据

- [ ] **K1.** `app/business/bi/demo_data.py` — SQLite 电商 demo 数据生成器
- [ ] **K2.** `app/business/bi/demo_data.py` — 5 张表 schema（products/customers/orders/returns/daily_stats）
- [ ] **K3.** `app/business/bi/demo_data.py` — 1 万订单 / 100 产品 / 1000 客户 / 50 退货
- [ ] **K4.** `app/business/bi/init_data.py` — demo 数据源预置
- [ ] **K5.** `just bi-demo` CLI 命令包装

---

## L. 测试

- [ ] **L1.** `tests/test_bi_datasource.py` — CRUD + test_connection
- [ ] **L2.** `tests/test_bi_metadata.py` — sync + sampler
- [ ] **L3.** `tests/test_bi_sandbox.py` — 白名单 / 脱敏 / 配额 / 租户注入
- [ ] **L4.** `tests/test_bi_llm.py` — 4 个 provider + 路由
- [ ] **L5.** `tests/test_bi_agent.py` — Mock LLM 跑全链路（Intent → Explain）
- [ ] **L6.** `tests/test_bi_chat.py` — 会话/消息 CRUD + SSE
- [ ] **L7.** `tests/test_bi_e2e.py` — 端到端查询 → SQL → 结果
- [ ] **L8.** `web/src/views/bi/__tests__/chat.test.ts` — vitest
- [ ] **L9.** `web/src/views/bi/__tests__/sql-workbench.test.ts` — vitest
- [ ] **L10.** 覆盖率报告（pytest-cov + vitest coverage）≥ 80%

---

## M. 文档

- [ ] **M1.** `docs/agentic-bi/SPEC.md`（已完成）
- [ ] **M2.** `docs/agentic-bi/checklist.md`（本文件）
- [ ] **M3.** `docs/agentic-bi/tasks.md`（实施任务）
- [ ] **M4.** `docs/agentic-bi/user-guide.md` — 用户使用指南
- [ ] **M5.** `docs/agentic-bi/architecture.md` — 架构说明
- [ ] **M6.** `docs/agentic-bi/sandbox.md` — SQL 沙箱使用
- [ ] **M7.** `docs/agentic-bi/llm-providers.md` — LLM Provider 配置
- [ ] **M8.** `docs/agentic-bi/security.md` — 多租户与权限
- [ ] **M9.** `docs/agentic-bi/multi-tenant.md` — 多租户数据隔离
- [ ] **M10.** `README.md` — 项目说明更新
- [ ] **M11.** `docs/advanced/agentic-bi.md` — 中英双语
- [ ] **M12.** `docs/en/advanced/agentic-bi.md`

---

## N. 集成 & 部署

- [ ] **N1.** `docker-compose.yml` — demo 数据库（PostgreSQL + ClickHouse + MySQL + Trino）
- [ ] **N2.** `deploy/bi.Dockerfile` — bi 服务镜像
- [ ] **N3.** `deploy/bi-worker.Dockerfile` — bi 异步 worker
- [ ] **N4.** `docs/agentic-bi/deploy.md` — 部署文档
- [ ] **N5.** `docs/agentic-bi/troubleshooting.md` — 排错指南
- [ ] **N6.** `scripts/dev.py` — 加 `bi-demo` 子命令
- [ ] **N7.** `scripts/seed-bi-demo.py` — 独立种子脚本

---

## O. Phase 3 生产化

- [ ] **O1.** 连接池调优（SQLAlchemy + Tortoise）
- [ ] **O2.** Prompt 缓存（LangChain 内置）
- [ ] **O3.** 查询结果缓存（Redis, 5min TTL）
- [ ] **O4.** LangGraph observability（自定义 tracer）
- [ ] **O5.** 慢查询巡检（周期任务）
- [ ] **O6.** 告警（执行失败率 / p95 / 限流触发）
- [ ] **O7.** 性能压测（locust）
- [ ] **O8.** E2E 集成测试（playwright）

---

**总计**：
- A: 12 项
- B: 9 项
- C: 10 项
- D: 12 项
- E: 17 项
- F: 9 项
- G: 7 项
- H: 8 项
- I: 6 项
- J: 30+ 项
- K: 5 项
- L: 10 项
- M: 12 项
- N: 7 项
- O: 8 项

**合计约 150+ 任务**。Phase 1 完成 ~50 项，Phase 2 完成 ~60 项，Phase 3 完成 ~40 项。
