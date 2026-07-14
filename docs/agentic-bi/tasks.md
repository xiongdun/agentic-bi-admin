# AgenticBI 实施 Tasks

> 按 Phase 1/2/3 拆分的实施任务，每个任务都有明确的产出物和验收标准。
> 每完成一个任务，勾选并报告进度。

---

## Phase 1：MVP（2 周）

**目标**：演示"本月各产品线销售额排名"端到端成功  
**依赖**：现有 FastSoyAdmin（AgenticBIAdmin）环境 + Python 3.12 + uv + pnpm

---

### Week 1（基础 + 沙箱 + 元数据）

#### Day 1-2：A. 基础设施
- [ ] **T1.** 创建 `app/business/bi/` 目录 + 空 `module.py`（manifest 骨架）
- [ ] **T2.** `pyproject.toml` 添加依赖：`sqlglot`、`sqlalchemy[asyncio]`、`openai`、`cryptography`、`sse-starlette`、`httpx`
- [ ] **T3.** `uv sync` 安装成功
- [ ] **T4.** `app/utils/llm.py` re-export LLM 抽象入口
- [ ] **T5.** `app/utils/sqlglot_utils.py` 工具函数（方言转换/格式化/差异）
- [ ] **T6.** `app/utils/sse.py` SSE 响应工具
- [ ] **T7.** `app/utils/crypto.py` Fernet 加密
- [ ] **T8.** `.env.example` 加 4 个 LLM provider 占位
- [ ] **T9.** `just check backend` 仍全过

**验收**：新增依赖安装成功，工具函数单元测试通过

#### Day 3-4：B. 数据模型
- [ ] **T10.** `app/business/bi/models.py` — 15 张表 Tortoise 模型（按 SPEC §5）
- [ ] **T11.** `app/business/bi/__init__.py` 复用 `BaseModel` / `AuditMixin`
- [ ] **T12.** `just mm` 生成 `migrations/app_business_bi/0001_initial.py`
- [ ] **T13.** 迁移 apply（SQLite 自动）
- [ ] **T14.** `app/business/bi/init_data.py` — 默认租户 + 默认数据源授权
- [ ] **T15.** `app/business/bi/init_data.py` — 菜单种子（"智能 BI" 顶级 + 4 子菜单 + 按钮权限）
- [ ] **T16.** `app/business/bi/module.py` — 完整 manifest（autodiscover 注册）
- [ ] **T17.** `app/business/bi/events.py` — 事件契约
- [ ] **T18.** `app/business/bi/policies.py` — DataPolicy
- [ ] **T19.** 重启后端，启动日志看到 bi 模块被加载

**验收**：自动发现 bi 模块 + 菜单在 Web UI 可见

#### Day 5-7：C+D. 元数据 + 沙箱
- [ ] **T20.** `app/business/bi/services/datasource.py` — CRUD
- [ ] **T21.** `app/business/bi/services/datasource.py` — `test_connection()`
- [ ] **T22.** `app/business/bi/api/datasource.py` — REST 端点
- [ ] **T23.** `app/business/bi/sandbox/executor.py` — SQLAlchemy 异步连接池
- [ ] **T24.** `app/business/bi/sandbox/executor.py` — SQLite 适配
- [ ] **T25.** `app/business/bi/sandbox/whitelist.py` — sqlglot AST 白名单
- [ ] **T26.** `app/business/bi/sandbox/whitelist.py` — 禁用函数列表
- [ ] **T27.** `app/business/bi/sandbox/tenant.py` — `inject_tenant_filter()`
- [ ] **T28.** `app/business/bi/sandbox/masking.py` — phone/email/id_card 脱敏
- [ ] **T29.** `app/business/bi/sandbox/quota.py` — Quota 配置 + 限流
- [ ] **T30.** `app/business/bi/sandbox/pipeline.py` — validate → mask → tenant → execute
- [ ] **T31.** `app/business/bi/metadata/sync.py` — 拉 schema（SQLite 实现）
- [ ] **T32.** `app/business/bi/metadata/sampler.py` — 列采样
- [ ] **T33.** `app/business/bi/metadata/sync.py` — Relation 自动发现
- [ ] **T34.** `app/business/bi/api/metadata.py` — `POST /datasources/{id}/sync`

**验收**：能在 UI 添加 SQLite 数据源 → 测试连接 → 同步 → 看到表/列

---

### Week 2（Agent + 对话 + 演示）

#### Day 8-10：E+F. Agent + 对话
- [ ] **T35.** `app/business/bi/llm/base.py` — `BaseChatModel` Protocol
- [ ] **T36.** `app/business/bi/llm/deepseek.py` — DeepSeek 客户端
- [ ] **T37.** `app/business/bi/llm/router.py` — 多 provider 路由
- [ ] **T38.** `app/business/bi/agent/state.py` — `AgentState` TypedDict
- [ ] **T39.** `app/business/bi/agent/nodes/intent.py` — Intent Agent
- [ ] **T40.** `app/business/bi/agent/nodes/sql_gen.py` — SQL Gen Agent（单 Agent 起步）
- [ ] **T41.** `app/business/bi/agent/nodes/sql_validate.py` — Validate Node
- [ ] **T42.** `app/business/bi/agent/nodes/executor_node.py` — 沙箱执行
- [ ] **T43.** `app/business/bi/agent/nodes/explain.py` — Explain Agent
- [ ] **T44.** `app/business/bi/agent/prompts/` — 5 个 prompt 模板
- [ ] **T45.** `app/business/bi/agent/runner.py` — FastAPI 异步桥接
- [ ] **T46.** `app/business/bi/services/chat.py` — ChatSession / ChatMessage service
- [ ] **T47.** `app/business/bi/api/chat.py` — 会话/消息 REST
- [ ] **T48.** `app/business/bi/api/chat.py` — SSE 端点
- [ ] **T49.** `app/business/bi/api/chat.py` — SSE 心跳 + 中断

**验收**：单 Agent NL2SQL 可工作，输入"本月销售额"返回 SQL

#### Day 11-12：G+H+I. 权限 + 审计
- [ ] **T50.** `app/business/bi/services/grant.py` — DatasourceGrant
- [ ] **T51.** `app/business/bi/services/masking.py` — ColumnMasking
- [ ] **T52.** `app/business/bi/sandbox/pipeline.py` — 集成 grant 过滤
- [ ] **T53.** `app/business/bi/sandbox/pipeline.py` — 集成 masking
- [ ] **T54.** `app/business/bi/services/audit.py` — AuditLog 写入
- [ ] **T55.** `app/business/bi/sandbox/pipeline.py` — 执行时自动写 AuditLog
- [ ] **T56.** `app/business/bi/api/grant.py` + `api/masking.py` + `api/audit.py`

**验收**：租户 A 不能查租户 B 的数据；执行被审计

#### Day 13-14：J+K+L+M. 前端 + 演示 + 测试 + 文档
- [ ] **T57.** `web/src/service/api/bi-*.ts` + `bi-*.d.ts` — 4 套 API
- [ ] **T58.** `web/src/hooks/use-sse.ts` — SSE 客户端封装
- [ ] **T59.** `web/src/views/bi/chat/index.vue` — 对话工作台
- [ ] **T60.** `web/src/views/bi/chat/modules/chat-sessions.vue` + `chat-messages.vue`
- [ ] **T61.** `web/src/views/bi/chat/modules/message-card.vue` — 消息卡片
- [ ] **T62.** `web/src/components/echarts/echart-renderer.vue` — ECharts 渲染
- [ ] **T63.** `web/src/components/echarts/charts/{bar,line,pie}.vue` — 3 图表
- [ ] **T64.** `web/src/views/bi/metadata/index.vue` — 元数据中心
- [ ] **T65.** `app/business/bi/demo_data.py` — SQLite 电商 demo 生成器
- [ ] **T66.** `tests/test_bi_datasource.py` — CRUD + 连接
- [ ] **T67.** `tests/test_bi_sandbox.py` — 白名单/脱敏/配额/租户
- [ ] **T68.** `tests/test_bi_agent.py` — Mock LLM 跑全链路
- [ ] **T69.** `tests/test_bi_e2e.py` — 端到端
- [ ] **T70.** `docs/agentic-bi/user-guide.md` — 用户使用指南
- [ ] **T71.** `just check` 全部通过

**Phase 1 演示场景**：
1. 登录 → 进入"智能 BI"
2. 创建 SQLite 数据源（连接 demo.db）→ 测试连接
3. 同步元数据 → 看到 5 张表
4. 进入"对话工作台" → 新建会话
5. 输入"本月各产品线销售额排名" → SSE 流式输出
6. 自动生成 SQL → 沙箱执行 → 返回柱状图
7. 点击 SQL 折叠展开 → 看到生成的 SQL
8. 查看审计 → 看到这次查询

**Phase 1 验收**：演示场景端到端成功 + `just check` 全过

---

## Phase 2：增强（2 周）

**目标**：5 数据源 + 4 LLM + LangGraph 完整 7 节点 + SQL 工作台 + 业务指标 + 列脱敏

### Week 3

#### Day 15-16：E 扩展（多 Agent + LangGraph）
- [ ] **T72.** `app/business/bi/agent/graph.py` — LangGraph DAG 编排
- [ ] **T73.** `app/business/bi/agent/nodes/schema_select.py` — Schema Select Agent
- [ ] **T74.** `app/business/bi/agent/nodes/sql_fix.py` — SQL Fix Agent + retry
- [ ] **T75.** `app/business/bi/agent/nodes/chart_recommend.py` — Chart Recommend Agent
- [ ] **T76.** `app/business/bi/agent/prompts/sql_gen.py` — 增强 few-shot
- [ ] **T77.** `app/business/bi/agent/runner.py` — 集成 LangGraph `ainvoke`

#### Day 17-18：D 扩展（5 数据源）
- [ ] **T78.** `app/business/bi/sandbox/executor.py` — PostgreSQL 适配
- [ ] **T79.** `app/business/bi/sandbox/executor.py` — MySQL 适配
- [ ] **T80.** `app/business/bi/sandbox/executor.py` — ClickHouse 适配
- [ ] **T81.** `app/business/bi/sandbox/executor.py` — Trino 适配
- [ ] **T82.** `app/business/bi/sandbox/whitelist.py` — 各方言特殊禁用
- [ ] **T83.** `app/business/bi/metadata/sync.py` — 各方言 schema 拉取

#### Day 19-21：F 扩展（SQL 工作台 + 历史）
- [ ] **T84.** `app/business/bi/api/sql_workbench.py` — `POST /bi/sql/execute`
- [ ] **T85.** `app/business/bi/api/sql_workbench.py` — `POST /bi/sql/explain`
- [ ] **T86.** `app/business/bi/api/sql_workbench.py` — `GET /bi/sql/history`
- [ ] **T87.** `app/business/bi/api/sql_workbench.py` — `POST /bi/sql/save`（保存为视图）
- [ ] **T88.** `web/src/views/bi/sql-workbench/index.vue` — 主页面
- [ ] **T89.** `web/src/views/bi/sql-workbench/modules/sql-editor.vue` — Monaco 集成
- [ ] **T90.** `web/src/views/bi/sql-workbench/modules/execution-history.vue`
- [ ] **T91.** `web/src/views/bi/sql-workbench/modules/result-table.vue` — 虚拟滚动

**Week 3 验收**：5 数据源可连 + LangGraph 跑全链路 + SQL 工作台可用

---

### Week 4

#### Day 22-23：LLM 扩展（4 provider）
- [ ] **T92.** `app/business/bi/llm/ollama.py` — Ollama 客户端
- [ ] **T93.** `app/business/bi/llm/qwen.py` — 通义千问客户端
- [ ] **T94.** `app/business/bi/llm/openai.py` — OpenAI 客户端
- [ ] **T95.** `app/business/bi/llm/router.py` — 任务级路由 + 降级
- [ ] **T96.** `app/business/bi/llm/router.py` — token 限额 + 成本统计

#### Day 24-25：G 业务指标
- [ ] **T97.** `app/business/bi/services/metric.py` — Metric service
- [ ] **T98.** `app/business/bi/services/dataset.py` — Dataset service
- [ ] **T99.** `app/business/bi/services/chart.py` — Chart service
- [ ] **T100.** `app/business/bi/api/metric.py` + `api/dataset.py` + `api/chart.py`
- [ ] **T101.** SQL Gen Agent 集成 Metric 注入
- [ ] **T102.** `web/src/views/bi/metadata/modules/synonym-editor.vue`
- [ ] **T103.** Metric 编辑 UI

#### Day 26-28：ECharts 扩展
- [ ] **T104.** `web/src/components/echarts/charts/funnel.vue`
- [ ] **T105.** `web/src/components/echarts/charts/sankey.vue`
- [ ] **T106.** `web/src/components/echarts/charts/radar.vue`
- [ ] **T107.** `web/src/components/echarts/charts/heatmap.vue`
- [ ] **T108.** `web/src/components/echarts/charts/scatter.vue`
- [ ] **T109.** `web/src/components/echarts/charts/area.vue`
- [ ] **T110.** `web/src/components/echarts/charts/map-china.vue`

**Week 4 验收**：4 LLM 可切换 + 业务指标可用 + 10+ 图表类型

---

## Phase 3：生产化（2 周）

**目标**：p95 < 5s + observability + Docker + 完整文档

### Week 5（性能 + observability）

#### Day 29-30：性能
- [ ] **T111.** `app/business/bi/sandbox/executor.py` — 连接池调优
- [ ] **T112.** `app/business/bi/agent/nodes/sql_gen.py` — Prompt 缓存
- [ ] **T113.** `app/business/bi/services/execution.py` — 结果缓存（Redis, 5min TTL）
- [ ] **T114.** `app/business/bi/sandbox/quota.py` — 慢查询熔断

#### Day 31-32：Observability
- [ ] **T115.** `app/business/bi/agent/runner.py` — 自定义 LangGraph tracer
- [ ] **T116.** `app/business/bi/agent/runner.py` — 步骤耗时/Token 入 Radar
- [ ] **T117.** `app/business/bi/api/audit.py` — 慢查询聚合
- [ ] **T118.** `app/business/bi/api/audit.py` — 异常 SQL 聚合
- [ ] **T119.** `app/business/bi/audit_panel` — 周期任务（异常告警）
- [ ] **T120.** `web/src/views/bi/audit/index.vue` — 审计面板
- [ ] **T121.** `web/src/views/bi/audit/modules/audit-table.vue`
- [ ] **T122.** `web/src/views/bi/audit/modules/slow-query-chart.vue`

#### Day 33-35：压测
- [ ] **T123.** `tests/locustfile.py` — 压测脚本
- [ ] **T124.** p95 < 5s 验证
- [ ] **T125.** 单用户 30 qpm 验证

**Week 5 验收**：性能指标达成 + observability 完整

---

### Week 6（部署 + 文档 + 收尾）

#### Day 36-37：Docker
- [ ] **T126.** `docker-compose.yml` — PostgreSQL + MySQL + ClickHouse + Trino
- [ ] **T127.** `deploy/bi.Dockerfile` — bi 服务镜像
- [ ] **T128.** `deploy/bi-worker.Dockerfile` — bi 异步 worker
- [ ] **T129.** `scripts/dev.py` — 加 `bi-demo` 子命令

#### Day 38-40：E2E + 文档
- [ ] **T130.** `tests/e2e/test_bi_flow.py` — playwright E2E
- [ ] **T131.** `docs/agentic-bi/architecture.md` — 架构说明
- [ ] **T132.** `docs/agentic-bi/sandbox.md` — SQL 沙箱使用
- [ ] **T133.** `docs/agentic-bi/llm-providers.md` — LLM Provider 配置
- [ ] **T134.** `docs/agentic-bi/security.md` — 多租户与权限
- [ ] **T135.** `docs/agentic-bi/multi-tenant.md` — 多租户数据隔离
- [ ] **T136.** `docs/agentic-bi/deploy.md` — 部署文档
- [ ] **T137.** `docs/agentic-bi/troubleshooting.md` — 排错指南
- [ ] **T138.** `README.md` 更新
- [ ] **T139.** `docs/advanced/agentic-bi.md` + en 镜像

#### Day 41-42：收尾
- [ ] **T140.** `just check` 全过
- [ ] **T141.** 测试覆盖率 ≥ 80%
- [ ] **T142.** Phase 3 演示：
  - 多租户隔离演示
  - 5 数据源连接演示
  - 4 LLM 切换演示
  - SQL 工作台 EXPLAIN
  - 审计面板查询
  - 列脱敏演示
- [ ] **T143.** 提交 + push

**Phase 3 验收**：所有 P0 需求覆盖 + 性能达标 + 文档完整

---

## 任务统计

| 阶段 | 任务数 | 周期 | 关键验收 |
|---|---|---|---|
| Phase 1 | 71 | 2 周 | 演示场景端到端成功 + `just check` 全过 |
| Phase 2 | 39 | 2 周 | 5 数据源 + 4 LLM + SQL 工作台 + 业务指标 |
| Phase 3 | 33 | 2 周 | p95 < 5s + observability + Docker + 完整文档 |
| **合计** | **143** | **6 周** | **全需求覆盖** |

---

## 当前进度

```
Phase 1 ░░░░░░░░░░ 0%   (T1-T71)
Phase 2 ░░░░░░░░░░ 0%   (T72-T110)
Phase 3 ░░░░░░░░░░ 0%   (T111-T143)
```

**当前阶段**：等待用户拍板 SPEC + checklist + tasks，开始 Phase 1。
