# Agentic BI 智能数据分析模块 产品需求文档（PRD）

| 文档版本 | v2.0 |
|---------|------|
| 文档状态 | 设计规格（待实现） |
| 适用项目 | AgenticBIAdmin（FastSoyAdmin 全栈模板 + AgenticBI 业务模块） |
| 落地参考 | [app/business/hr/](file:///d:/code/python/agentic-bi-admin/app/business/hr)（HR Demo，manifest 模式范例） |

> 本文档为 `app/business/bi/` 业务模块的设计规格。所有架构、命名、分层、响应契约、权限模型均严格遵循 [AGENTS.md](file:///d:/code/python/agentic-bi-admin/AGENTS.md) 与 [docs/standard/](file:///d:/code/python/agentic-bi-admin/docs/standard)。本文档不保留原 TRAE SOLO 项目的技术栈（Element Plus 作为 UI / Celery / TailwindCSS / 自建 RAG / 知识图谱页等），统一对齐到 AgenticBIAdmin 框架。BI 特有的 SQL 解析（sqlglot）、外部库执行（SQLAlchemy async，仅用于对外部数据源执行用户 SQL，系统库仍用 Tortoise ORM）、加密（cryptography）、SSE（sse-starlette）作为业务依赖按需引入。

---

## 目录

1. [模块概述](#1-模块概述)
2. [背景与痛点](#2-背景与痛点)
3. [产品目标](#3-产品目标)
4. [用户角色与使用场景](#4-用户角色与使用场景)
5. [架构设计](#5-架构设计)
6. [功能需求详细说明](#6-功能需求详细说明)
7. [企业级特性](#7-企业级特性)
8. [技术栈选型](#8-技术栈选型)
9. [数据模型设计](#9-数据模型设计)
10. [API 接口设计](#10-api-接口设计)
11. [UI/UX 设计规范](#11-uiux-设计规范)
12. [非功能需求](#12-非功能需求)
13. [模块文件结构](#13-模块文件结构)
14. [核心数据指标](#14-核心数据指标)
15. [开发中关键问题及应对](#15-开发中关键问题及应对)
16. [可复用方法论](#16-可复用方法论)
17. [未来规划](#17-未来规划)
18. [风险与应对](#18-风险与应对)

---

## 1. 模块概述

### 1.1 产品定义

**Agentic BI** 是 AgenticBIAdmin 的智能数据分析业务模块（`app/business/bi/`），基于多 Agent 架构 + 多 LLM Provider 抽象，业务分析师只需输入中文自然语言问题（如"本月各产品线的销售额排名"），系统即可自动完成 **意图识别 → SQL 生成 → 安全校验 → 沙箱执行 → 结果可视化** 全流程，实现"让业务人员用自然语言对话数据库"。

### 1.2 产品定位

- **核心价值**：降低数据分析门槛，提升取数效率，实现业务自助式数据分析
- **目标用户**：业务分析师、运营人员、财务人员、市场人员、数据分析师、DBA、系统管理员
- **产品形态**：作为 AgenticBIAdmin 的内置业务模块（manifest 模式 autodiscover 自动加载），可独立开关（`BUSINESS_MODULES_DISABLED=bi`）
- **核心能力**：NL2SQL + SQL 工作台 + 元数据管理 + 多 LLM 切换 + 多数据源接入 + 行级权限 + 审计日志

### 1.3 版本演进

| 版本 | 阶段 | 核心内容 |
|------|------|---------|
| v0.1 | Phase 1 基础版 | 核心 NL2SQL 能力 + 元数据管理 + SQL 工作台 + 多 LLM 抽象 |
| v0.2 | Phase 2 增强 | 多租户行级注入 + 列脱敏 + 审计日志增强 + 指标管理 |
| v0.3 | Phase 3 规划 | Context Agent 上下文继承 + 更多数据源 + 异常预警 |

---

## 2. 背景与痛点

### 2.1 核心痛点

| 序号 | 痛点 | 具体描述 | 影响 |
|------|------|---------|------|
| 1 | **业务人员不会 SQL** | 运营、财务、市场团队每天需要取数分析，但完全依赖 IT 写 SQL | 一个简单查询平均等待数小时 |
| 2 | **数据源分散** | 公司有 PostgreSQL、MySQL、ClickHouse、Trino 等多种数据库 | 每次切换需要重新理解表结构 |
| 3 | **元数据管理混乱** | 表结构变更无通知，字段含义靠口口相传 | LLM 生成 SQL 时经常"猜错"列名 |
| 4 | **缺乏可解释性** | 传统 NL2SQL 工具是黑盒 | 生成的 SQL 出错了不知道哪里出了问题 |
| 5 | **专业用户受限** | 分析师和 DBA 有 SQL 能力但被 NL2SQL 管道束缚 | 无法直接执行自定义复杂查询 |
| 6 | **权限管理缺失** | 企业内不同角色应有不同的数据访问范围 | 安全风险高 |
| 7 | **操作无审计** | 谁查了什么、改了什么、删了什么，全无记录 | 合规风险高 |

### 2.2 解决思路

依托 AgenticBIAdmin 框架已有的 RBAC + 行级 `data_scope` + 审计基础设施，BI 模块只需专注 NL2SQL / Agent 流水线 / SQL 沙箱 / LLM 抽象四件事，权限与审计不在业务模块自建，复用 `app/system/` 与 `app/core/` 能力。

---

## 3. 产品目标

### 3.1 总体目标

让非技术人员也能用自然语言自助完成数据分析，同时为专业用户提供 SQL 工作台，保证安全可控、权限清晰、操作可追溯。

### 3.2 具体目标

| 目标维度 | 具体指标 | 目标值 |
|---------|---------|--------|
| **效率提升** | 取数等待时间 | 从数小时 → < 10 秒（NL2SQL）/ 即时（Direct SQL） |
| **用户覆盖** | 支持用户类型 | 业务人员 + 专业分析师 + DBA + 管理员 |
| **数据源支持** | 支持数据库类型 | 5 种（PostgreSQL / MySQL / ClickHouse / Trino / SQLite） |
| **LLM 支持** | Provider 数量 | 5 种（DeepSeek / Ollama / 通义 / OpenAI / Mock） |
| **安全合规** | 权限控制 | RBAC 菜单 + 按钮码 + 行级 `data_scope`（复用系统层） |
| **安全合规** | 审计日志 | 5 类核心操作日志（复用系统 Radar + BI 审计表） |
| **成本可控** | LLM 调用次数/查询 | 固定 2 次（intent + sql_gen） |

---

## 4. 用户角色与使用场景

### 4.1 用户角色定义

| 角色 | 角色码 | data_scope | 核心需求 | 技术能力 |
|------|--------|-----------|---------|---------|
| **超级管理员** | `R_SUPER`（系统内置） | all | 全部功能 + 用户/角色管理 | 精通技术 |
| **BI 管理员** | `R_BI_ADMIN` | all | 数据源管理、元数据同步、LLM 配置、审计查看 | 中等技术 |
| **数据分析师** | `R_BI_ANALYST` | scope | NL2SQL 对话、SQL 工作台、指标查看 | 基础 SQL |
| **业务运营人员** | `R_BI_ANALYST` | self | NL2SQL 对话、查看自己范围内的数据 | 不会 SQL |

> 角色与按钮码均通过 `init_data.py` 的 `ensure_role` 声明，启动时由 leader worker 幂等写入；不在代码里硬判 `role_code == "..."`。

### 4.2 典型使用场景

#### 场景 1：业务人员自助取数

- **用户**：运营专员（`R_BI_ANALYST`）
- **场景**：想知道"本月销售额 TOP10 的产品"
- **操作**：在 Chat 界面输入自然语言问题
- **结果**：系统自动生成 SQL 并执行，返回柱状图展示结果
- **耗时**：< 10 秒

#### 场景 2：分析师复杂查询

- **用户**：高级数据分析师（`R_BI_ANALYST`，`data_scope=scope`）
- **场景**：需要编写多表关联的复杂 SQL 进行深度分析
- **操作**：使用 SQL 工作台编写 SQL，查看执行计划
- **结果**：在数据范围内执行复杂查询并可视化

#### 场景 3：管理员配置 LLM Provider

- **用户**：BI 管理员（`R_BI_ADMIN`）
- **场景**：切换默认 LLM 从 DeepSeek 到本地 Ollama
- **操作**：在 LLM Provider 管理页面切换默认 Provider
- **结果**：所有 Chat 请求改用 Ollama

#### 场景 4：合规审计

- **用户**：合规部门（`R_BI_ADMIN`）
- **场景**：需要排查某用户的数据访问记录
- **操作**：在审计日志页面按用户、时间、操作类型筛选
- **结果**：查看完整的操作记录，包括 SQL 内容、执行结果、IP 地址等

---

## 5. 架构设计

### 5.1 整体架构

系统采用 **Multi-Agent Pipeline 架构**，5 个节点串行执行：

```
用户输入: "本月销售额TOP10的产品"
 ↓
┌─────────────────────────────────────────────┐
│ Node 1: Intent Recognition                 │ ← 意图识别
│ 判断是"数据查询"/"指标分析"/"趋势对比"...   │ LLM + 规则兜底
└─────────────────┬───────────────────────────┘
 ↓
┌─────────────────────────────────────────────┐
│ Node 2: SQL Generation                     │ ← SQL 生成
│ Schema 注入 + 用户问题 → SQL               │ LLM + 方言适配
└─────────────────┬───────────────────────────┘
 ↓
┌─────────────────────────────────────────────┐
│ Node 3: SQL Validate                       │ ← 安全校验
│ sqlglot AST 白名单 + 脱敏 + 行级注入        │ sqlglot
└─────────────────┬───────────────────────────┘
 ↓
┌─────────────────────────────────────────────┐
│ Node 4: Executor                           │ ← 沙箱执行
│ 行数/超时/熔断 + SQLAlchemy 异步执行         │
└─────────────────┬───────────────────────────┘
 ↓ （执行失败不进入 Node 5）
┌─────────────────────────────────────────────┐
│ Node 5: Explain                            │ ← 结果解释
│ 生成中文解读 + 推荐图表类型                  │ LLM
└─────────────────────────────────────────────┘
```

**关键原则**：固定 LLM 调用次数（intent + sql_gen + 可选 explain，最多 3 次），不引入动态重试循环，保证稳定性与成本可控。

### 5.2 模块分层

完全遵循 AgenticBIAdmin 业务模块分层：

| 层 | 模块 | 说明 |
|------|------|------|
| **API 层** | `app/business/bi/api/` | URL 接线、依赖注入、`Success`/`Fail` 封装 |
| **Service 层** | `app/business/bi/services.py` | 事务、跨模型编排、缓存、事件派发 |
| **Controller 层** | `app/business/bi/controllers.py` | 单模型 CRUD（继承 `CRUDBase`）、`build_search` |
| **Model 层** | `app/business/bi/models.py` | Tortoise ORM 模型，表名 `biz_bi_*` |
| **Schema 层** | `app/business/bi/schemas.py` | Pydantic DTO，继承 `SchemaBase` |
| **Agent 层** | `app/business/bi/agent/nodes/` | 5 个独立 Agent 节点 + `runner.py` 编排 |
| **Sandbox 层** | `app/business/bi/sandbox/` | SQL 安全校验、脱敏、租户注入、配额、执行 |
| **LLM 层** | `app/business/bi/llm/` | Provider 抽象 + 多 Provider 实现 + 路由 |
| **Metadata 层** | `app/business/bi/metadata/` | schema 同步、列采样、关系提取 |
| **Security 层** | `app/business/bi/security/` | Fernet 加解密 |

### 5.3 Agent 节点说明

#### Node 1: Intent Recognition（意图识别）

- **职责**：识别用户问题的意图类型
- **技术实现**：LLM + 规则兜底
- **输出**：意图类型标签（数据查询 / 指标分析 / 趋势对比等）

#### Node 2: SQL Generation（SQL 生成）

- **职责**：注入 Schema 元数据 + 用户问题生成 SQL
- **技术实现**：LLM + sqlglot 方言适配
- **支持方言**：PostgreSQL / MySQL / ClickHouse / Trino / SQLite（5 种）

#### Node 3: SQL Validate（SQL 校验）

- **职责**：sqlglot AST 白名单校验 + 列脱敏 + 多租户行级注入
- **技术实现**：`sandbox/whitelist.py` + `sandbox/masking.py` + `sandbox/tenant.py`
- **白名单规则**：仅允许 `SELECT` / `WITH` / `EXPLAIN`；禁止文件操作 / 命令执行 / 导出函数

#### Node 4: Executor（执行器）

- **职责**：配额限制（行数 / 超时 / 熔断）+ SQLAlchemy 异步执行
- **技术实现**：`sandbox/quota.py` + `sandbox/executor.py`

#### Node 5: Explain（结果解释）

- **职责**：生成中文解读 + 推荐图表类型
- **技术实现**：LLM
- **触发条件**：执行成功才进入；失败直接返回错误

---

## 6. 功能需求详细说明

### 6.1 功能 1：自然语言对话（Chat）— 核心交互

**定位**：整个模块的核心入口，业务人员通过自然语言与数据库对话。

**前端文件**：[web/src/views/bi/chat/index.vue](file:///d:/code/python/agentic-bi-admin/web/src/views/bi/chat/index.vue) + `modules/*.vue`

#### 6.1.1 功能清单

| 功能点 | 优先级 | 详细说明 |
|--------|--------|---------|
| **流式输出（SSE）** | P0 | 每个节点完成时推送 `step` 事件，结束推送 `final` 事件，使用 `sse_starlette` |
| **自动图表渲染** | P0 | AI 返回结果后，自动判断最佳图表类型（柱状 / 折线 / 饼图 / 表格），用 ECharts 渲染 |
| **状态追踪** | P0 | 实时显示 "意图识别 → SQL 生成 → 校验 → 执行 → 解释" |
| **对话历史** | P0 | 侧边栏展示历史会话，支持删除和切换 |
| **快捷提问** | P1 | 根据当前数据源自动推荐常用问题 |
| **Chat 直连 SQL 执行** | P0 | 支持 `执行sql SELECT ...` 等触发模式，绕过 LLM 直接执行 |
| **图表导出 PNG** | P1 | 一键导出图表为 PNG（ECharts `getDataURL`） |
| **图表导出 CSV** | P1 | 一键导出数据为 CSV（带 BOM 头兼容中文 Excel） |

#### 6.1.2 关键 Prompt 设计

```
你是一个 SQL 专家。请根据以下数据库 Schema 和用户问题，生成安全的 {dialect} 查询语句。

## Schema 信息
- 表名: {table_name}
- 字段: [{column_name, data_type, is_primary, comment}, ...]
- 示例数据: {sample_rows}

## 用户问题
{user_question}

## 要求
1. 只输出一条 SELECT 语句，不要解释
2. 使用正确的列名和表名
3. 对于聚合查询，添加 LIMIT 100
4. 优先使用已知的索引列作为 WHERE 条件
```

#### 6.1.3 交互流程

1. 用户在输入框输入自然语言问题
2. 系统显示"思考中"状态，SSE 推送 `step: intent`
3. 意图识别节点分析用户意图
4. SQL 生成节点加载相关 Schema 并生成 SQL，SSE 推送 `step: sql_gen`
5. SQL 校验节点做 AST 白名单 + 脱敏 + 行级注入，SSE 推送 `step: sql_validate`
6. 执行节点安全执行 SQL，SSE 推送 `step: executor`
7. 解释节点生成中文解读，SSE 推送 `step: explain`
8. SSE 推送 `final` 事件，前端渲染结果与图表
9. 用户可导出图表或数据

---

### 6.2 功能 2：元数据自动采集

**定位**：让 AI "懂"你的数据库，自动采集和管理数据库元数据。

**后端文件**：`app/business/bi/services.py`（元数据服务函数）+ `app/business/bi/metadata/sync.py`（采集逻辑）

#### 6.2.1 功能清单

| 功能点 | 优先级 | 详细说明 |
|--------|--------|---------|
| **自动连接采集** | P0 | 自动连接目标数据库，采集完整元数据 |
| **元数据内容** | P0 | 表名、列名、数据类型、主键、外键、注释、索引、统计信息、样例数据 |
| **本地存储** | P0 | 存储到 BI 模块表（`biz_bi_*`），供 LLM Prompt 动态注入 |
| **手动触发同步** | P0 | 通过 API 手动触发同步 |
| **采集规模** | P0 | 支持单数据源上百张表的完整采集 |

#### 6.2.2 采集字段明细

| 元数据类型 | 包含字段 |
|-----------|---------|
| **表信息** | 表名、表注释、行数、创建时间、更新时间 |
| **列信息** | 列名、数据类型、是否主键、是否可空、默认值、列注释 |
| **索引信息** | 索引名、索引类型、包含列、是否唯一 |
| **外键信息** | 外键名、源列、目标表、目标列 |
| **统计信息** | 基数、空值数量 |
| **样例数据** | 前 N 行样例数据（默认 5 行，可通过配置调整） |

---

### 6.3 功能 3：数据源管理

**定位**：多数据源的接入、测试、元数据同步、连接信息加密存储。

**后端文件**：`app/business/bi/api/datasource.py`（`CRUDRouter` + 自定义路由）+ `app/business/bi/services.py`（数据源服务函数）

#### 6.3.1 功能清单

| 功能点 | 优先级 | 详细说明 |
|--------|--------|---------|
| **数据源 CRUD** | P0 | 标准 `CRUDRouter` 6 路由（POST /search、GET/PATCH/DELETE /{id}、POST、DELETE 批量） |
| **连接测试** | P0 | `POST /api/v1/business/bi/datasources/{id}/test` 测试连接 |
| **元数据同步** | P0 | `POST /api/v1/business/bi/datasources/{id}/sync` 触发元数据采集 |
| **密码加密存储** | P0 | 用 `cryptography.fernet`（需 `uv add cryptography`）加密数据源密码，封装在 `app/business/bi/security/crypto.py` |
| **支持数据源类型** | P0 | PostgreSQL / MySQL / ClickHouse / Trino / SQLite |
| **方言适配** | P0 | 用 `sqlglot`（需 `uv add sqlglot`）做 SQL 方言转换与校验，封装在 `app/business/bi/sandbox/dialect.py` |

#### 6.3.2 数据源详情页

**前端文件**：[web/src/views/bi/metadata/index.vue](file:///d:/code/python/agentic-bi-admin/web/src/views/bi/metadata/index.vue) + `modules/datasource-operate-modal.vue` + `modules/column-detail-drawer.vue`

| 区域 | 内容 |
|------|------|
| **基本信息** | 数据源名称、类型、连接信息（脱敏显示） |
| **统计卡片** | 表数 / 列数 / 索引数 / 最后同步时间 |
| **Tab 布局** | 表卡片网格 / 字段搜索表 |
| **表卡片** | 表名、列数、行数 |
| **右侧抽屉** | 点击表卡片弹出抽屉，展示完整列信息和示例数据 |

---

### 6.4 功能 4：SQL 工作台

**定位**：面向有 SQL 能力的分析师和 DBA 用户提供专业查询工具。

**前端文件**：[web/src/views/bi/sql-workbench/index.vue](file:///d:/code/python/agentic-bi-admin/web/src/views/bi/sql-workbench/index.vue)

#### 6.4.1 功能清单

| 功能模块 | 优先级 | 详细说明 |
|---------|--------|---------|
| **数据源选择器** | P0 | 下拉选择 + 连接状态指示 |
| **表列表展示** | P0 | 从元数据加载表列表 + 搜索过滤 |
| **表右键 Popup 菜单** | P0 | 查看表结构 / 生成 SELECT 语句 / 预览前 100 行 |
| **SQL 编辑器** | P0 | 语法高亮 + 行号（需新增 `monaco-editor` 或 `@codemirror/*`，v0.1 可先用 Naive UI `NInput` textarea） |
| **执行按钮** | P0 | `POST /api/v1/business/bi/sql/run` |
| **结果表格** | P0 | 分页控件（20/50/100/200） |
| **执行耗时** | P0 | 实时显示 |
| **图表配置** | P1 | ECharts 预览 + 配置面板（柱状 / 折线 / 饼图 / 散点 / 表格 / 热力图） |
| **SQL 安全检查** | P0 | 复用 `sandbox/whitelist.py` |
| **PNG 导出** | P1 | ECharts `getDataURL(pixelRatio=2)` |
| **CSV 导出** | P1 | 带 BOM 头中文 Excel 兼容 |
| **执行历史** | P1 | 查看历史执行记录，支持快速复用 |
| **写操作开关** | P0 | 通过环境变量 / 数据源配置控制是否允许 DML/DDL |

---

### 6.5 功能 5：LLM Provider 管理

**定位**：多 LLM Provider 抽象层，可在线切换默认 Provider。

**后端文件**：`app/business/bi/api/llm.py`（`CRUDRouter`）+ `app/business/bi/llm/`

#### 6.5.1 功能清单

| 功能点 | 优先级 | 详细说明 |
|--------|--------|---------|
| **Provider CRUD** | P0 | 标准 `CRUDRouter` 6 路由 |
| **多 Provider 支持** | P0 | DeepSeek / Ollama / 通义千问 / OpenAI / Mock / Custom（OpenAI 兼容协议） |
| **Provider 测试连接** | P0 | `POST /api/v1/business/bi/llm/providers/{id}/test` |
| **默认 Provider 切换** | P0 | 修改 `.env` 的 `LLM_DEFAULT_PROVIDER` 或通过 API 切换 |
| **参数配置** | P0 | Temperature / Max Tokens / Top P 等参数可调 |
| **API Key 加密存储** | P0 | 用 `cryptography.fernet` 加密（复用 `app/business/bi/security/crypto.py`） |

#### 6.5.2 Provider 抽象

```
app/business/bi/llm/
  ├── base.py        # BaseLLMProvider 抽象基类
  ├── deepseek.py    # DeepSeek 实现
  ├── ollama.py      # Ollama 本地模型实现
  ├── qwen.py        # 通义千问实现
  ├── openai.py      # OpenAI 实现
  ├── mock.py        # Mock 实现（开发测试用）
  └── router.py      # 多 Provider 路由，按 LLM_DEFAULT_PROVIDER 切换
```

Provider 配置通过 `.env`：

```bash
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b
# ... 其他 Provider
LLM_DEFAULT_PROVIDER=deepseek
```

---

### 6.6 功能 6：指标管理

**定位**：把常用 SQL 模板化为指标，业务用户可直接调用。

**前端文件**：[web/src/views/bi/metrics/index.vue](file:///d:/code/python/agentic-bi-admin/web/src/views/bi/metrics/index.vue) + `modules/metric-operate-modal.vue` + `modules/metric-test-modal.vue`

#### 6.6.1 功能清单

| 功能点 | 优先级 | 详细说明 |
|--------|--------|---------|
| **指标 CRUD** | P0 | 标准 `CRUDRouter` 6 路由 |
| **SQL 模板** | P0 | 指标绑定 SQL 模板，支持参数化 |
| **数据源绑定** | P0 | 每个指标绑定一个数据源 |
| **指标测试** | P0 | `POST /api/v1/business/bi/metrics/{id}/test` 执行测试 |
| **指标查看** | P0 | 业务用户通过 `B_BI_METRIC_VIEW` 按钮码控制可见性 |

---

### 6.7 功能 7：审计日志

**定位**：合规必备 — 5 类核心日志的记录与查询。

**前端文件**：[web/src/views/bi/audit/index.vue](file:///d:/code/python/agentic-bi-admin/web/src/views/bi/audit/index.vue)

#### 6.7.1 5 类日志类型

| 日志类型 | 编码 | 采集点 |
|---------|------|--------|
| **用户行为日志** | USER_BEHAVIOR | 登录 / 登出 / 页面访问 |
| **查询操作日志** | QUERY_OPERATION | NL2SQL 查询 / SQL 直连查询 |
| **系统操作日志** | SYSTEM_OPERATION | 数据源 CRUD / LLM 配置 / 角色权限变更 |
| **权限变更日志** | PERMISSION_CHANGE | 角色分配 / 权限授予撤销 |
| **按钮操作日志** | BUTTON_CLICK | 删除数据源 / 清空缓存等关键按钮 |

#### 6.7.2 审计页面功能

| 功能点 | 优先级 | 详细说明 |
|--------|--------|---------|
| **统计卡片** | P0 | 总数 / 成功 / 失败 / 成功率 |
| **多维度筛选** | P0 | 按日志类型、操作人、时间范围筛选 |
| **日志详情展开** | P0 | TraceID / IP / 资源信息 / JSON 详情 / 错误信息 |
| **分页查询** | P0 | 每页 20/50/100 条 |
| **CSV 导出** | P1 | 支持导出审计日志 |

> 关键节点、权限拒绝、重要安全事件同时通过 `radar_log(...)` 写入 Radar 监控面板（`/manage/radar/*`），与系统层 Radar 复用。

---

## 7. 企业级特性

### 7.1 特性总览

| 特性 | 说明 | 实现方式 |
|------|------|---------|
| **RBAC 权限控制** | JWT 认证 + 角色权限 + 按钮权限 | 复用 `app/core/dependency.py` 的 `DependAuth` / `DependPermission` / `require_buttons` |
| **行级 data_scope** | BI 模块数据按用户范围过滤 | 复用 `app/core/data_scope.py` 的 `build_scope_filter`，`scope_id_field` 映射为 `tenant_id` |
| **审计日志** | `radar_log` + BI 审计表双层记录 | 复用系统 Radar + BI 模块 `biz_bi_audit_log` 表 |
| **SQL 安全引擎** | sqlglot AST 白名单 + 行级注入 + 配额 | `app/business/bi/sandbox/` |
| **数据脱敏** | 列脱敏 + 数据源密码 Fernet 加密 | `app/business/bi/sandbox/masking.py` + `app/business/bi/security/crypto.py`（基于 `cryptography.fernet`） |
| **LLM 成本控制** | 固定 LLM 调用次数（最多 3 次/查询） | Agent 流水线设计 |
| **多 LLM Provider** | 5 种 Provider 切换 | `app/business/bi/llm/` |
| **多数据源** | 5 种数据库方言适配 | `app/business/bi/sandbox/dialect.py`（基于 `sqlglot`） |
| **多租户** | 共享库 + `tenant_id` 列注入 | 复用 `data_scope` + `sandbox/tenant.py` |

### 7.2 SQL 安全引擎

#### 7.2.1 AST 白名单（`sandbox/whitelist.py`）

- **允许**：`SELECT` / `WITH` / `EXPLAIN`
- **禁止**：`INSERT` / `UPDATE` / `DELETE` / `DROP` / `TRUNCATE` / `ALTER` / `CREATE` / 文件操作（`LOAD_FILE` / `INTO OUTFILE`）/ 命令执行（`pg_read_file` 等）/ 导出函数
- **多语句拦截**：分号检测
- **注释拦截**：`--` / `/* */` 检测
- **自动 LIMIT**：SELECT 语句无 LIMIT 时自动添加 LIMIT 1000；聚合查询自动添加 LIMIT 100

#### 7.2.2 列脱敏（`sandbox/masking.py`）

- 按列名规则匹配，支持手机号 / 身份证 / 邮箱 / 银行卡 等敏感字段脱敏
- 脱敏规则可在 `init_data.py` 中声明种子

#### 7.2.3 行级注入（`sandbox/tenant.py`）

- 自动给 SELECT 添加 `WHERE tenant_id = :scope` 条件
- `scope` 来自当前用户的 `data_scope` + `scope_id`
- 复用 `app/core/data_scope.py` 的 `build_scope_filter`

#### 7.2.4 配额限制（`sandbox/quota.py`）

| 限制项 | 默认值 | 说明 |
|--------|--------|------|
| **最大行数** | 10000 | 单次查询返回上限 |
| **超时** | 30 秒 | 单次查询超时 |
| **熔断** | 10 次/分钟 | 单用户失败次数超限后熔断 |

---

## 8. 技术栈选型

### 8.1 技术栈总览

| 层 | 技术选型 | 选型理由 |
|----|---------|---------|
| **前端框架** | Vue 3.5 + TypeScript 6 + Naive UI 2.44 + UnoCSS 66 | 与 AgenticBIAdmin 模板一致 |
| **前端路由** | Elegant Router 0.3.8 | 文件式路由自动生成 |
| **前端状态** | Pinia 3 | setup store |
| **前端请求** | `@sa/axios`（扁平 `[data, error]` 返回） | 与模板一致 |
| **前端图表** | ECharts 6 | 自动检测柱状 / 折线 / 饼图 / 表格并渲染 |
| **前端编辑器** | 需新增 SQL 编辑器依赖（`monaco-editor` 或 `@codemirror/*`，v0.1 可先用 Naive UI `NInput` textarea） | SQL 工作台使用 |
| **后端框架** | FastAPI | 原生异步，自动生成 API 文档 |
| **后端 ORM** | Tortoise ORM + asyncpg / aiosqlite（系统库，BI 元数据表） | 与模板一致 |
| **外部库执行** | SQLAlchemy async（需 `uv add sqlalchemy[asyncio]`）+ 对应 asyncpg/asyncmy 等驱动 | 对外部数据源执行用户 SQL（Tortoise 不支持任意 SQL 执行） |
| **数据库** | SQLite（开发）/ PostgreSQL（生产） | 与模板一致 |
| **大模型** | 多 Provider 抽象（DeepSeek / Ollama / 通义 / OpenAI / Mock） | 灵活切换，避免厂商锁定 |
| **SQL 解析** | sqlglot（需 `uv add sqlglot`） | 方言转换 + AST 白名单校验 |
| **加密** | `cryptography.fernet`（需 `uv add cryptography`），封装在 `app/business/bi/security/crypto.py` | 数据源密码 / LLM API Key 加密 |
| **SSE** | `sse_starlette`（需 `uv add sse-starlette`），封装在 `app/business/bi/sse.py` | 流式输出 |
| **任务调度** | manifest 的 `PeriodicTask`（进程内） | 不引入 Celery |

### 8.2 新增依赖

落地 BI 模块前需通过 `uv add` 安装以下依赖（当前 `pyproject.toml` 未包含）：

```bash
uv add sqlglot                    # SQL 解析 + 方言转换 + AST 白名单
uv add "sqlalchemy[asyncio]"      # 外部数据源异步执行（ClickHouse/Trino 需额外驱动）
uv add cryptography               # Fernet 加解密
uv add sse-starlette              # SSE 流式输出
# 可选：按需安装外部数据源驱动
uv add clickhouse-connect          # ClickHouse
uv add trino                       # Trino
```

> 前端 SQL 编辑器依赖按需添加：`pnpm add monaco-editor` 或 `pnpm add @codemirror/lang-sql @codemirror/view`。

### 8.3 选型考量

- **与模板一致优先**：不引入 Element Plus / TailwindCSS / Celery / 自建 RAG / 自建知识图谱等模板未集成的依赖；BI 必需的 SQL 解析（sqlglot）、外部库执行（SQLAlchemy async）、加密（cryptography）、SSE（sse-starlette）、SQL 编辑器（monaco/codemirror）作为业务依赖按需 `uv add` / `pnpm add`
- **复用框架能力**：RBAC / 审计 / 缓存 / 事件总线 / `init_helper` 全部复用 `app/core/` 与 `app/system/`，不在业务模块自建
- **稳定性优先**：固定 LLM 调用次数，不引入动态重试循环
- **多 LLM 抽象**：避免厂商锁定，支持本地 Ollama 离线场景

---

## 9. 数据模型设计

### 9.1 模型总览

所有模型位于 `app/business/bi/models.py`，表名统一 `biz_bi_*` 前缀，继承 `BaseModel + AuditMixin`（需要软删的加 `SoftDeleteMixin`）。

| 子模块 | 模型 | 表名 | 说明 |
|------|------|------|------|
| **metadata** | `BiDatasource` | `biz_bi_datasource` | 数据源配置（连接信息加密存储） |
| **metadata** | `BiTable` | `biz_bi_table` | 采集到的表元数据 |
| **metadata** | `BiColumn` | `biz_bi_column` | 采集到的列元数据 |
| **metadata** | `BiIndex` | `biz_bi_index` | 索引元数据 |
| **metadata** | `BiForeignKey` | `biz_bi_foreign_key` | 外键关系元数据 |
| **semantic** | `BiMetric` | `biz_bi_metric` | 指标定义（SQL 模板） |
| **conversation** | `BiChatSession` | `biz_bi_chat_session` | 对话会话 |
| **conversation** | `BiChatMessage` | `biz_bi_chat_message` | 对话消息（含 SQL / 执行结果 / agent_steps_json） |
| **llm** | `BiLLMProvider` | `biz_bi_llm_provider` | LLM Provider 配置 |
| **llm** | `BiLLMModel` | `biz_bi_llm_model` | LLM 模型配置 |
| **audit** | `BiAuditLog` | `biz_bi_audit_log` | BI 业务审计日志 |
| **security** | `BiMaskingRule` | `biz_bi_masking_rule` | 列脱敏规则 |
| **security** | `BiQuotaConfig` | `biz_bi_quota_config` | 配额配置 |

### 9.2 模型约定

- 每个 `ForeignKeyField` / `OneToOneField` 上方显式声明 `<name>_id: int`（或 `int | None`）类型注解
- 字段写 `description="..."`（CLI 生成 schema 时作 i18n 中文名）
- 类 docstring 写中文资源名（用作 API summary 前缀）
- `Meta.table = "biz_bi_<entity>"`
- 文件头加 `# pyright: reportIncompatibleVariableOverride=false`
- `BaseModel.to_dict()` 自动 camelCase + sqid 编码（id 与 `*_id` 字段对外不暴露真实 int）

### 9.3 关键表结构示例

#### 9.3.1 `biz_bi_datasource` 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Int64 | 主键（sqid 编码对外） |
| name | CharField | 数据源名称 |
| db_type | CharEnumField | 数据库类型（postgresql / mysql / clickhouse / trino / sqlite） |
| host | CharField | 主机 |
| port | Int16 | 端口 |
| username | CharField | 用户名 |
| password | CharField | 密码（Fernet 加密存储） |
| database | CharField | 数据库名 |
| extra_params | JSONField | 额外连接参数 |
| status_type | CharEnumField | 状态（启用 / 禁用） |
| last_synced_at | DatetimeField | 最后同步时间 |
| created_by / created_at / updated_by / updated_at | AuditMixin 字段 | 审计字段 |

#### 9.3.2 `biz_bi_chat_message` 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Int64 | 主键 |
| session_id | Int64 | 会话 ID（FK） |
| role | CharEnumField | user / assistant / system |
| content | TextField | 消息内容 |
| sql_text | TextField | 生成的 SQL |
| sql_result | JSONField | 执行结果 |
| agent_steps_json | JSONField | Agent 流水线步骤留痕 |
| intent_type | CharField | 意图类型 |
| execution_time_ms | Int32 | 执行耗时 |
| token_usage | JSONField | Token 用量统计 |
| status | CharEnumField | 成功 / 失败 |
| error_message | TextField | 错误信息 |
| created_by / created_at | AuditMixin 字段 | 审计字段 |

#### 9.3.3 `biz_bi_audit_log` 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Int64 | 主键 |
| trace_id | CharField | 链路追踪 ID |
| event_type | CharEnumField | 5 类事件类型 |
| action | CharField | 具体操作 |
| user_id | Int64 | 操作用户 ID |
| username | CharField | 操作用户名 |
| ip_address | CharField | 操作 IP |
| resource_type | CharField | 资源类型 |
| resource_id | CharField | 资源 ID（sqid 编码） |
| detail | JSONField | 详细信息 |
| status | CharEnumField | 成功 / 失败 |
| error_message | TextField | 错误信息 |
| execution_time_ms | Int32 | 执行耗时 |
| created_at | DatetimeField | 创建时间 |

---

## 10. API 接口设计

### 10.1 API 总览

所有路由前缀 `/api/v1/business/bi/`，autodiscover 自动加 `/business/bi`，业务 router 内不要重复带模块前缀。

| 模块 | 路由文件 | 路径前缀 | 路由类型 |
|------|---------|---------|---------|
| **数据源** | `api/datasource.py` | `/datasources` | `CRUDRouter` + 自定义（test/sync） |
| **元数据** | `api/metadata.py` | `/metadata` | `CRUDRouter` + 自定义（表/列详情） |
| **对话** | `api/chat.py` | `/chat` | 自定义（SSE 流式） |
| **SQL 工作台** | `api/sql_workbench.py` | `/sql` | 自定义（run/explain/format） |
| **指标** | `api/metric.py` | `/metrics` | `CRUDRouter` + 自定义（test） |
| **LLM** | `api/llm.py` | `/llm` | `CRUDRouter` + 自定义（test） |
| **审计** | `api/audit.py` | `/audit` | `CRUDRouter` + 自定义（统计/导出） |

### 10.2 标准 CRUD 路由（`CRUDRouter` 自动生成）

每个资源生成 6 个路由，`route_key_prefix="bi.<resource>"` → 生成 `APIRoute.name`：

```
POST   /resources/search        bi.<resource>.list
GET    /resources/{item_id}      bi.<resource>.get
POST   /resources                bi.<resource>.create
PATCH  /resources/{item_id}      bi.<resource>.update
DELETE /resources/{item_id}      bi.<resource>.delete
DELETE /resources                bi.<resource>.batch_delete
```

按钮权限通过 `action_dependencies` 挂载：

```python
action_dependencies={
    "create": [require_buttons("B_BI_DS_CREATE")],
    "update": [require_buttons("B_BI_DS_EDIT")],
    "delete": [require_buttons("B_BI_DS_DELETE")],
}
```

### 10.3 自定义路由示例

#### 10.3.1 对话 API（SSE 流式）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/business/bi/chat/sessions` | GET | 会话列表 |
| `/api/v1/business/bi/chat/sessions` | POST | 创建会话 |
| `/api/v1/business/bi/chat/sessions/{id}` | DELETE | 删除会话 |
| `/api/v1/business/bi/chat/sessions/{id}/messages` | GET | 会话消息列表 |
| `/api/v1/business/bi/chat/send` | POST | 发送消息（SSE 流式响应） |

**SSE 事件类型**（基于 `sse_starlette`，需 `uv add sse-starlette`，封装在 `app/business/bi/sse.py`）：

| 事件 | 说明 |
|------|------|
| `step` | 节点执行进度（payload 含 `node` + `status` + `data`） |
| `final` | 流水线结束（payload 含最终结果 + 图表推荐） |
| `error` | 错误（payload 含错误码 + 消息） |
| `heartbeat` | 心跳保活（用 `sse_heartbeat_wrapper`） |

#### 10.3.2 SQL 工作台 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/business/bi/sql/run` | POST | 执行 SQL |
| `/api/v1/business/bi/sql/explain` | POST | 执行计划 |
| `/api/v1/business/bi/sql/format` | POST | SQL 格式化 |
| `/api/v1/business/bi/sql/history` | GET | 执行历史 |
| `/api/v1/business/bi/sql/preview/{table_name}` | GET | 预览表数据（前 100 行） |
| `/api/v1/business/bi/sql/generate-select/{table_name}` | GET | 生成 SELECT 语句 |

#### 10.3.3 数据源 API（CRUDRouter + 自定义）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/business/bi/datasources/search` | POST | 数据源列表（标准 CRUD） |
| `/api/v1/business/bi/datasources/{id}` | GET | 详情 |
| `/api/v1/business/bi/datasources` | POST | 创建 |
| `/api/v1/business/bi/datasources/{id}` | PATCH | 更新 |
| `/api/v1/business/bi/datasources/{id}` | DELETE | 删除 |
| `/api/v1/business/bi/datasources` | DELETE | 批量删除 |
| `/api/v1/business/bi/datasources/{id}/test` | POST | 测试连接（自定义） |
| `/api/v1/business/bi/datasources/{id}/sync` | POST | 同步元数据（自定义） |

### 10.4 响应契约

所有响应统一用 `Success` / `SuccessExtra` / `Fail`，HTTP 恒 200，格式：

```json
{
  "code": "0000",
  "msg": "success",
  "data": { ... }
}
```

分页响应用 `SuccessExtra`，额外含 `total` / `current` / `size`：

```json
{
  "code": "0000",
  "msg": "success",
  "data": {
    "records": [...],
    "total": 100,
    "current": 1,
    "size": 20
  }
}
```

业务失败用 `raise BizError(code, msg)`，响应码从 4000 起按业务场景分配：

| 码段 | 含义 |
|------|------|
| `4000-4099` | 数据源相关（连接失败 / 元数据同步失败） |
| `4100-4199` | SQL 相关（校验失败 / 执行失败 / 配额超限） |
| `4200-4299` | LLM 相关（Provider 不可用 / 调用失败 / 配置缺失） |
| `4300-4399` | Agent 流水线相关（节点失败 / 状态异常） |
| `4400-4499` | 元数据相关（采集失败 / 表不存在 / 列不存在） |

---

## 11. UI/UX 设计规范

### 11.1 设计语言

完全复用 AgenticBIAdmin 模板的设计系统，不引入自定义风格：

- **UI 框架**：Naive UI 2.44 + pro-naive-ui（ProTable / ProForm）
- **样式系统**：UnoCSS 66 原子化 CSS
- **主题预设**：[web/src/theme/preset/](file:///d:/code/python/agentic-bi-admin/web/src/theme/preset) 下的 `default` / `dark` / `compact` / `azir` 四套预设
- **图标**：Iconify（通过 `web/src/plugins/iconify.ts` 自动注册）
- **国际化**：vue-i18n 11，BI 模块 i18n 放 `web/src/locales/langs/_generated/bi/`

### 11.2 布局规范

复用模板的 `base-layout`（含 header / sider / menu / tab / breadcrumb 子模块），BI 模块页面放在 `web/src/views/bi/<feature>/index.vue`，由 Elegant Router 自动生成路由。

### 11.3 组件规范

| 组件 | 用法 |
|------|------|
| **表格** | `pro-naive-ui` 的 `ProTable`，配合 `useTable` hook（`web/src/hooks/common/table.ts`） |
| **表单** | `pro-naive-ui` 的 `ProForm`，配合 `useForm` hook |
| **图表** | ECharts 6，配合 `useEcharts` hook（`web/src/hooks/common/echarts.ts`） |
| **抽屉** | Naive UI 的 `NDrawer`，宽度 520px（右侧） |
| **对话框** | Naive UI 的 `NModal` |
| **按钮** | Naive UI 的 `NButton`，按钮可见性用 `useAuth().hasAuth("B_BI_XXX")` |

### 11.4 页面清单

| 页面 | 路径 | 路由名 | 文件 |
|------|------|--------|------|
| **智能对话** | `/bi/chat` | `bi_chat` | [web/src/views/bi/chat/index.vue](file:///d:/code/python/agentic-bi-admin/web/src/views/bi/chat/index.vue) |
| **元数据管理** | `/bi/metadata` | `bi_metadata` | [web/src/views/bi/metadata/index.vue](file:///d:/code/python/agentic-bi-admin/web/src/views/bi/metadata/index.vue) |
| **SQL 工作台** | `/bi/sql-workbench` | `bi_sql-workbench` | [web/src/views/bi/sql-workbench/index.vue](file:///d:/code/python/agentic-bi-admin/web/src/views/bi/sql-workbench/index.vue) |
| **指标管理** | `/bi/metrics` | `bi_metrics` | [web/src/views/bi/metrics/index.vue](file:///d:/code/python/agentic-bi-admin/web/src/views/bi/metrics/index.vue) |
| **LLM 配置** | `/bi/models` | `bi_models` | [web/src/views/bi/models/index.vue](file:///d:/code/python/agentic-bi-admin/web/src/views/bi/models/index.vue) |
| **审计日志** | `/bi/audit` | `bi_audit` | [web/src/views/bi/audit/index.vue](file:///d:/code/python/agentic-bi-admin/web/src/views/bi/audit/index.vue) |

### 11.5 i18n 约定

BI 模块 i18n 文件放在 `web/src/locales/langs/_generated/bi/`：

```
_generated/bi/
  ├── zh-cn.ts       # 中文
  ├── en-us.ts       # 英文
  └── types.d.ts     # 类型声明（通过 GeneratedPages 接口声明合并）
```

`web/src/locales/locale.ts` 用 `import.meta.glob('./langs/_generated/*/zh-cn.ts', { eager: true })` 自动合并到基础语言包，无需手工修改基础包。

新增路由必须补 `route.bi_chat` 等翻译键，否则菜单显示空白。

---

## 12. 非功能需求

### 12.1 性能需求

| 指标 | 目标值 | 说明 |
|------|--------|------|
| **NL2SQL 响应时间** | < 10 秒 | 从输入到图表渲染完成 |
| **Direct SQL 响应时间** | 即时 | 直连 SQL 执行 |
| **页面加载时间** | < 3 秒 | 首屏加载 |
| **API 响应时间** | < 500ms | 普通接口（不含 SQL 执行） |
| **并发用户数** | 100+ | 支持同时在线用户 |
| **元数据采集** | < 60 秒 | 单数据源百张表 |

### 12.2 安全需求

| 需求 | 说明 |
|------|------|
| **身份认证** | JWT Token 认证（复用 `app/core/dependency.py`） |
| **权限控制** | RBAC 菜单 + 按钮权限 + 行级 `data_scope` |
| **SQL 安全** | sqlglot AST 白名单 + 自动 LIMIT + 行级注入 |
| **数据加密** | Fernet 加密数据源密码 / LLM API Key |
| **数据脱敏** | 列脱敏引擎 |
| **审计日志** | 5 类操作日志全记录 + Radar 监控 |
| **配额限制** | 行数 / 超时 / 熔断 |

### 12.3 可用性需求

| 需求 | 说明 |
|------|------|
| **系统可用性** | 99.9% |
| **错误处理** | 友好的错误提示，不暴露技术细节；用 `BizError` 穿透 |
| **容错能力** | LLM 调用失败时降级（Mock Provider 或规则兜底） |
| **数据备份** | 复用模板的数据库备份策略 |

### 12.4 兼容性需求

| 需求 | 说明 |
|------|------|
| **浏览器兼容** | Chrome / Firefox / Safari / Edge 最新两个版本 |
| **数据库兼容** | PostgreSQL / MySQL / ClickHouse / Trino / SQLite |
| **部署方式** | Docker 部署 / 私有化部署（复用 `deploy/`） |

### 12.5 可维护性需求

| 需求 | 说明 |
|------|------|
| **代码规范** | 遵循 [docs/standard/backend.md](file:///d:/code/python/agentic-bi-admin/docs/standard/backend.md) 与 [docs/standard/vue.md](file:///d:/code/python/agentic-bi-admin/docs/standard/vue.md) |
| **文档完整** | API 文档自动生成（FastAPI Swagger） |
| **日志完善** | 关键节点 `radar_log`，高频调试 `log.debug` |
| **提交门禁** | `just check`（前后端统一） |

---

## 13. 模块文件结构

遵循 AgenticBIAdmin 业务模块约定（参考 [app/business/hr/](file:///d:/code/python/agentic-bi-admin/app/business/hr)）：标准分层用**扁平文件**（`models.py` / `schemas.py` / `controllers.py` / `services.py`，与 CLI 生成器一致），BI 特有能力（agent / sandbox / llm / metadata / security）用子包。

```
app/business/bi/
├── __init__.py
├── module.py                         # manifest 声明（BusinessModule）
├── config.py                         # 模块配置（可选独立 DB_URL + LLM/quota 默认值）
├── init_data.py                      # 菜单/角色/按钮/脱敏规则种子
├── events.py                         # EventSpec 事件契约
├── policies.py                       # DataPolicy 行级策略
├── models.py                         # Tortoise ORM 模型（13 个，表名 biz_bi_*）
├── schemas.py                        # Pydantic DTO（继承 SchemaBase）
├── controllers.py                    # 单模型 CRUD（继承 CRUDBase）+ build_search
├── services.py                       # 跨模型编排、缓存、事件派发
├── sse.py                            # SSE 事件封装（基于 sse_starlette）
├── api/                              # 路由目录（多个 router 文件）
│   ├── __init__.py                   # 聚合 router
│   ├── datasource.py                 # 数据源 CRUD + 自定义（test/sync）
│   ├── metadata.py                   # 元数据 CRUD + 自定义（表/列详情）
│   ├── chat.py                       # 对话 SSE
│   ├── sql_workbench.py              # SQL 工作台（run/explain/format）
│   ├── metric.py                     # 指标 CRUD + 测试
│   ├── llm.py                        # LLM Provider CRUD + 测试
│   └── audit.py                      # 审计日志 CRUD + 导出
├── agent/                            # BI 特有：Agent 流水线
│   ├── __init__.py
│   ├── state.py                      # AgentState TypedDict + StepTrace
│   ├── runner.py                     # run_chat_turn 编排
│   └── nodes/
│       ├── intent.py                 # 意图识别
│       ├── sql_gen.py                # SQL 生成
│       ├── sql_validate.py           # SQL 校验
│       ├── executor.py               # 执行
│       └── explain.py                # 结果解释
├── sandbox/                          # BI 特有：SQL 安全引擎
│   ├── whitelist.py                  # sqlglot AST 白名单
│   ├── dialect.py                    # 方言转换（基于 sqlglot）
│   ├── masking.py                    # 列脱敏
│   ├── tenant.py                     # 多租户行级注入
│   ├── quota.py                      # 配额限制
│   └── executor.py                   # SQLAlchemy 异步执行器
├── metadata/                         # BI 特有：元数据采集
│   ├── sync.py                       # schema 同步
│   ├── sampler.py                    # 列采样
│   └── relations.py                  # 关系提取
├── llm/                              # BI 特有：LLM Provider 抽象
│   ├── __init__.py
│   ├── base.py                       # BaseLLMProvider 抽象基类
│   ├── deepseek.py                   # DeepSeek
│   ├── ollama.py                     # Ollama 本地模型
│   ├── qwen.py                       # 通义千问
│   ├── openai.py                     # OpenAI
│   ├── mock.py                       # Mock（开发测试用）
│   └── router.py                     # Provider 路由（按 LLM_DEFAULT_PROVIDER 切换）
└── security/                         # BI 特有：安全工具
    └── crypto.py                     # Fernet 加解密（基于 cryptography）
```

> **结构约定**：`models.py` / `schemas.py` / `controllers.py` / `services.py` 保持扁平文件，与 [app/cli/](file:///d:/code/python/agentic-bi-admin/app/cli) 生成器输出一致，便于 `just cli-crud` 增量生成。BI 特有能力（agent / sandbox / llm / metadata / security）作为子包，不参与 CLI 生成。

### 13.1 manifest 声明（`module.py`）

参考 [app/business/hr/module.py](file:///d:/code/python/agentic-bi-admin/app/business/hr/module.py)：

```python
from app.business.bi.api import router
from app.business.bi.events import BI_EVENTS
from app.business.bi.init_data import INIT_DATA, init
from app.business.bi.policies import BI_DATA_POLICIES
from app.utils import BusinessModule, BusinessRouter, PermissionSpec

# BI 模块对 SSE / SQL 执行路径设置更宽松的限流配额；
# autodiscover 会自动合并到 fastapi-guard 的 endpoint_rate_limits。
ENDPOINT_RATE_LIMITS = {
    "/api/v1/business/bi/chat/send": (30, 60),       # SSE 流式：每 60 秒 30 次
    "/api/v1/business/bi/sql/run": (60, 60),          # SQL 执行：每 60 秒 60 次
}

module = BusinessModule(
    name="bi",
    title="智能 BI",
    version="0.1.0",
    routers=[
        BusinessRouter(router=router, auth="permission", tags=["智能 BI"]),
    ],
    init=init,
    permissions=PermissionSpec(init_data=INIT_DATA),
    events=BI_EVENTS,
    data_policies=BI_DATA_POLICIES,
)
```

### 13.2 前端文件结构

```
web/src/
├── views/bi/
│   ├── chat/
│   │   ├── index.vue
│   │   └── modules/
│   │       ├── session-list.vue
│   │       └── message-renderer.vue
│   ├── metadata/
│   │   ├── index.vue
│   │   └── modules/
│   │       ├── datasource-operate-modal.vue
│   │       └── column-detail-drawer.vue
│   ├── sql-workbench/
│   │   └── index.vue
│   ├── metrics/
│   │   ├── index.vue
│   │   └── modules/
│   │       ├── metric-operate-modal.vue
│   │       └── metric-test-modal.vue
│   ├── models/
│   │   ├── index.vue
│   │   └── modules/
│   │       ├── model-operate-modal.vue
│   │       └── provider-operate-modal.vue
│   └── audit/
│       └── index.vue
├── service/api/
│   ├── bi.ts                         # 数据源 / 元数据
│   ├── bi-chat.ts                    # 对话
│   ├── bi-sql.ts                     # SQL 工作台
│   ├── bi-metric.ts                  # 指标
│   ├── bi-llm.ts                     # LLM
│   └── bi-audit.ts                   # 审计
├── typings/api/
│   └── bi.d.ts                       # Api.Bi.<Entity> 类型
└── locales/langs/_generated/bi/
    ├── zh-cn.ts
    ├── en-us.ts
    └── types.d.ts
```

---

## 14. 核心数据指标

### 14.1 模块规模预估

| 指标 | 目标值 |
|------|--------|
| **后端 API 路由** | ~30 个（7 个子模块，每模块标准 6 + 自定义 1-3） |
| **后端 Agent 节点** | 5 个 |
| **后端 LLM Provider** | 5 个 |
| **后端 ORM 模型** | 13 个 |
| **前端页面** | 6 个 |
| **支持数据库** | 5 种 |
| **支持 LLM** | 5 种 |
| **角色码** | 2 个（`R_BI_ADMIN` / `R_BI_ANALYST`）+ 复用系统 `R_SUPER` |
| **按钮码** | ~20 个（`B_BI_<RESOURCE>_<ACTION>`） |

### 14.2 BI 角色与按钮码清单

#### 14.2.1 角色码

| 角色码 | 角色名 | data_scope | 菜单范围 |
|--------|--------|-----------|---------|
| `R_BI_ADMIN` | BI 管理员 | all | 全部 BI 菜单 + 审计 |
| `R_BI_ANALYST` | 数据分析师 | scope | 对话 + 工作台 + 指标查看 |

#### 14.2.2 按钮码（`B_BI_<RESOURCE>_<ACTION>`）

| 按钮码 | 说明 |
|--------|------|
| `B_BI_CHAT_NEW` | 新建对话 |
| `B_BI_CHAT_DELETE` | 删除对话 |
| `B_BI_DS_CREATE` | 创建数据源 |
| `B_BI_DS_EDIT` | 编辑数据源 |
| `B_BI_DS_DELETE` | 删除数据源 |
| `B_BI_DS_TEST` | 测试数据源连接 |
| `B_BI_DS_SYNC` | 同步元数据 |
| `B_BI_SQL_RUN` | 执行 SQL |
| `B_BI_METRIC_VIEW` | 查看指标 |
| `B_BI_METRIC_CREATE` | 创建指标 |
| `B_BI_METRIC_EDIT` | 编辑指标 |
| `B_BI_METRIC_DELETE` | 删除指标 |
| `B_BI_METRIC_TEST` | 测试指标 |
| `B_BI_MODEL_PROVIDER_VIEW` | 查看 LLM Provider |
| `B_BI_MODEL_PROVIDER_CREATE` | 创建 LLM Provider |
| `B_BI_MODEL_PROVIDER_EDIT` | 编辑 LLM Provider |
| `B_BI_MODEL_PROVIDER_DELETE` | 删除 LLM Provider |
| `B_BI_MODEL_PROVIDER_TEST` | 测试 LLM Provider |
| `B_BI_AUDIT_VIEW` | 查看审计日志 |
| `B_BI_AUDIT_EXPORT` | 导出审计日志 |

### 14.3 菜单结构（`init_data.py` 声明）

```python
BI_MENU_CHILDREN = [
    {
        "menu_name": "智能对话",
        "route_name": "bi_chat",
        "route_path": "/bi/chat",
        "component": "view.bi_chat",
        "icon": "mdi:chat-outline",
        "order": 1,
        "buttons": [
            {"button_code": "B_BI_CHAT_NEW", "button_desc": "新建对话"},
            {"button_code": "B_BI_CHAT_DELETE", "button_desc": "删除对话"},
        ],
    },
    {
        "menu_name": "元数据管理",
        "route_name": "bi_metadata",
        "route_path": "/bi/metadata",
        "component": "view.bi_metadata",
        "icon": "mdi:database-search-outline",
        "order": 2,
        "buttons": [
            {"button_code": "B_BI_DS_CREATE", "button_desc": "创建数据源"},
            {"button_code": "B_BI_DS_EDIT", "button_desc": "编辑数据源"},
            {"button_code": "B_BI_DS_DELETE", "button_desc": "删除数据源"},
            {"button_code": "B_BI_DS_TEST", "button_desc": "测试数据源连接"},
            {"button_code": "B_BI_DS_SYNC", "button_desc": "同步元数据"},
        ],
    },
    # ... 其他菜单
]

INIT_DATA = {
    "menus": [
        {
            "menu_name": "智能 BI",
            "route_name": "bi",
            "route_path": "/bi",
            "icon": "mdi:chart-line",
            "order": 30,
            "children": BI_MENU_CHILDREN,
            "reconcile": {"menus": True, "buttons": True},  # IaC 单一数据源
        },
    ],
    "roles": [
        {
            "role_name": "BI管理员",
            "role_code": "R_BI_ADMIN",
            "role_desc": "BI 管理员，负责数据源、LLM、审计全量管理",
            "data_scope": DataScopeType.all,
            "menus": ["home", "bi", "bi_chat", "bi_metadata", "bi_sql-workbench", "bi_metrics", "bi_models", "bi_audit"],
            "buttons": [...],  # 全部按钮
            "apis": [...],    # 全部 route key
        },
        {
            "role_name": "数据分析师",
            "role_code": "R_BI_ANALYST",
            "role_desc": "数据分析师，可对话、SQL 查询、查看指标",
            "data_scope": DataScopeType.scope,
            "menus": ["home", "bi", "bi_chat", "bi_sql-workbench", "bi_metrics"],
            "buttons": [
                "B_BI_CHAT_NEW", "B_BI_CHAT_DELETE",
                "B_BI_SQL_RUN",
                "B_BI_METRIC_VIEW",
            ],
            "apis": [...],
        },
    ],
    "users": [],
    "dictionaries": [],
}
```

> ⚠️ **IaC 陷阱**：`reconcile_menu_subtree` 启用后，BI 子树是单一数据源，Web UI 在该子树下手工创建的菜单/按钮会在下次重启时被清除。允许用户动态创建菜单的子树不要启用 reconcile。

---

## 15. 开发中关键问题及应对

### 15.1 LLM 调用稳定性

**问题**：LLM 调用可能超时 / 返回格式不符 / 限流。

**应对**：

- 固定调用次数（intent + sql_gen + 可选 explain，最多 3 次），不引入动态重试循环
- 每个 Provider 实现统一的超时与错误处理（继承 `BaseLLMProvider`）
- Mock Provider 作为兜底，开发测试环境不依赖外部 LLM
- LLM 不可用时通过 `BizError(4200, "LLM Provider 不可用")` 友好提示

### 15.2 SQL 注入与危险操作

**问题**：用户输入或 LLM 生成的 SQL 可能包含危险操作。

**应对**：

- sqlglot AST 白名单校验（仅允许 `SELECT` / `WITH` / `EXPLAIN`）
- 禁止文件操作 / 命令执行 / 导出函数
- 多语句拦截（分号检测）
- 自动 LIMIT（无 LIMIT 的 SELECT 自动添加 LIMIT 1000）
- 行级注入（自动添加 `WHERE tenant_id = :scope`）
- 配额限制（行数 / 超时 / 熔断）

### 15.3 多租户行级权限

**问题**：不同用户只能看自己范围内的数据。

**应对**：

- 复用 `app/core/data_scope.py` 的 `build_scope_filter`
- `BiDatasource` 等业务表加 `tenant_id` 字段
- `sandbox/tenant.py` 自动给 SQL 注入 `WHERE tenant_id = :scope`
- 角色声明 `data_scope`（all / scope / self / custom）

### 15.4 元数据同步性能

**问题**：大数据库元数据采集慢。

**应对**：

- 异步执行（`async def sync_metadata(...)`）
- 分批采集（每次 100 张表）
- 采样数据量可配（默认 5 行）
- 采集结果缓存到 `biz_bi_table` / `biz_bi_column` 表，避免重复查询源库

### 15.5 SSE 流式输出的稳定性

**问题**：长连接可能被代理 / 网关中断。

**应对**：

- 用 `sse_starlette`（封装在 `app/business/bi/sse.py`）的心跳保活机制维持连接
- 每个节点完成时推送 `step` 事件，让前端感知进度
- 错误时推送 `error` 事件并关闭连接
- BI 模块在 `module.py` 声明 `ENDPOINT_RATE_LIMITS`（autodiscover 自动合并到 Guard），为 SSE / SQL 执行路径设置更宽松的限流配额；如需完全跳过 Guard 校验，需在 [app/core/init_app.py](file:///d:/code/python/agentic-bi-admin/app/core/init_app.py) 的 `_make_guard_config()` `exclude_paths` 中添加路径（框架级变更，需用户确认）

### 15.6 Windows 平台兼容性

**问题**：Windows + ProactorEventLoop 与某些异步库不兼容。

**应对**：

- 已知 Guard 中间件在 Windows 上 Redis 连接有问题，已在 [app/core/init_app.py](file:///d:/code/python/agentic-bi-admin/app/core/init_app.py) 用 `sys.platform != "win32"` 回退进程内限流
- BI 模块开发时需在 Windows 上验证（本机开发环境就是 Windows）
- 生产环境部署到 Linux 不受此限制

---

## 16. 可复用方法论

### 16.1 "Prompt First" 开发模式

先设计 LLM 的 Prompt 结构（Schema 注入格式、输出约束），再写代码。

- Prompt 是 LLM 应用的核心，决定了输出质量
- 先把 Prompt 调优到最佳状态，再围绕它构建代码
- 避免代码写完后才发现 Prompt 效果不好需要大改

### 16.2 "Metadata as Code"

把数据库元数据当作一等公民管理，自动采集、版本化、注入 Prompt。

- 元数据是 NL2SQL 的基础，质量直接影响 SQL 生成准确率
- 自动采集 + 版本化管理，确保元数据始终最新
- 结构化注入 Prompt，让 LLM 充分理解数据库结构

### 16.3 "Defense in Depth" 安全体系

SQL 安全检测 → 权限校验 → 审计日志 → 数据脱敏，多层防护。

- 单一安全措施不够，需要多层防护
- 每层都有独立的安全机制，一层被绕过还有下一层
- 从输入到输出，全链路安全控制

### 16.4 "Stability First" 架构原则

不要为了架构炫技而牺牲稳定性；直接调用 > 过度抽象；固定 LLM 调用次数 > 动态重试循环。

- 稳定性是企业级产品的第一要务
- 简单直接的架构比复杂的架构更可靠
- 可控的成本和性能比"智能"但不稳定的方案更好

### 16.5 "Framework First" 复用原则

**AgenticBIAdmin 特有**：优先复用框架能力，不在业务模块自建。

- RBAC / 审计 / 缓存 / 事件总线 / `init_helper` 全部复用 `app/core/` 与 `app/system/`
- 业务模块只专注业务逻辑（NL2SQL / Agent / SQL 沙箱 / LLM 抽象）
- 跨模块联动走事件总线 `emit` / `on`，不直接 import 兄弟业务模块
- 标准资源用 `CRUDRouter` + `CRUDBase`，自定义动作用 `@crud.override`

---

## 17. 未来规划

### 17.1 Phase 3 远期规划

| 功能 | 说明 | 优先级 |
|------|------|--------|
| **Context Agent 对话管理** | 代词消解 / 省略补全 / 上下文继承 | 高 |
| **更多数据源支持** | Doris / Hive / API / 文件 / 数据湖 | 中 |
| **自然语言创建 Dashboard** | 用自然语言创建仪表盘和报告 | 中 |
| **异常检测和智能预警** | 自动检测数据异常，智能预警 | 低 |
| **LLM 成本追踪** | 真实 Token 用量统计 + 仪表盘 | 中 |
| **报表 CRUD** | SQL 工作台结果保存为可复用报表 | 中 |

### 17.2 优先级排序

1. **高优先级**：Context Agent 对话管理（提升对话体验）
2. **中优先级**：更多数据源接入、LLM 成本追踪、报表 CRUD
3. **低优先级**：自然语言创建 Dashboard、异常检测预警

---

## 18. 风险与应对

### 18.1 技术风险

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|---------|
| **LLM 生成 SQL 不准确** | 高 | 中 | 优化 Prompt + 元数据增强 + 人工审核机制 |
| **SQL 注入风险** | 高 | 低 | sqlglot AST 白名单 + 自动 LIMIT + 权限控制 + 行级注入 |
| **大并发性能问题** | 中 | 中 | 异步架构 + 连接池 + 缓存 + Guard 限流 |
| **元数据同步延迟** | 中 | 低 | 异步采集 + 手动触发 + 版本标记 |
| **LLM 厂商限流** | 中 | 中 | 多 Provider 切换 + Mock 兜底 + 固定调用次数 |

### 18.2 产品风险

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|---------|
| **用户接受度低** | 高 | 中 | 优化 UX + 提供培训 + 快捷提问引导 |
| **功能过于复杂** | 中 | 中 | 分层设计 + 权限控制 + 渐进式披露 |
| **成本不可控** | 中 | 低 | 固定调用次数 + 成本监控 + 限额告警 |

### 18.3 项目风险

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|---------|
| **需求蔓延** | 高 | 中 | 明确 MVP 范围 + 分阶段交付 |
| **技术债务** | 中 | 中 | 遵循 [docs/standard/](file:///d:/code/python/agentic-bi-admin/docs/standard) + 提交前 `just check` |
| **人员依赖** | 中 | 低 | 文档完善 + 知识共享 + 代码规范 |

---

## 附录

### 附录 A：术语表

| 术语 | 说明 |
|------|------|
| **NL2SQL** | Natural Language to SQL，自然语言转 SQL |
| **Agentic BI** | 基于 Agent 架构的商业智能模块 |
| **RBAC** | Role-Based Access Control，基于角色的访问控制 |
| **SSE** | Server-Sent Events，服务器推送事件 |
| **sqlglot** | Python SQL 解析与方言转换库 |
| **Provider** | LLM 提供方（DeepSeek / Ollama / 通义 / OpenAI / Mock） |
| **data_scope** | 行级数据范围（all / scope / self / custom） |
| **manifest** | 业务模块声明式注册（`BusinessModule`） |
| **CRUDRouter** | 框架自动生成标准 6 路由的工具 |
| **BizError** | 业务错误异常，穿透任意层返回统一响应 |

### 附录 B：参考资料

- [AGENTS.md](file:///d:/code/python/agentic-bi-admin/AGENTS.md) — AI 协作指南
- [docs/standard/backend.md](file:///d:/code/python/agentic-bi-admin/docs/standard/backend.md) — 后端规范
- [docs/standard/vue.md](file:///d:/code/python/agentic-bi-admin/docs/standard/vue.md) — 前端规范
- [docs/standard/naming.md](file:///d:/code/python/agentic-bi-admin/docs/standard/naming.md) — 命名规范
- [docs/getting-started/architecture.md](file:///d:/code/python/agentic-bi-admin/docs/getting-started/architecture.md) — 架构总览
- [docs/develop/](file:///d:/code/python/agentic-bi-admin/docs/develop) — 开发指南
- [app/business/hr/](file:///d:/code/python/agentic-bi-admin/app/business/hr) — 业务模块 manifest 范例
- 在线文档：https://sleep1223.github.io/fast-soy-admin-docs/

---

**文档结束**

> 本文档为 AgenticBIAdmin 项目的 BI 业务模块设计规格，所有架构与约定严格遵循 [AGENTS.md](file:///d:/code/python/agentic-bi-admin/AGENTS.md)。
