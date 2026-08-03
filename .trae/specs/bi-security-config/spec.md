# BI 安全配置（脱敏规则 + 配额配置）Spec — Batch D-1

## 目标

补齐 `BiMaskingRule` 与 `BiQuotaConfig` 两个已存在模型的 CRUD API + 前端管理页，并把它们真正接入 sandbox 执行链路，让管理员在 UI 配置的脱敏规则与配额策略对查询实际生效。这是 BI 安全闭环的"最后一公里"。

## 背景

- `BiMaskingRule` / `BiQuotaConfig` 模型 + schemas + controllers 在 `0001_initial.py` 已建表，但**零 API 路由、零按钮码、零前端页面**
- `mask_columns` 函数已实现但**全代码库无调用点**
- `BiQuotaConfig` 模型**未被 sandbox/quota.py 引用**，后者用 env 变量驱动的本地 dataclass
- 前端 typings 已预留 `BiMaskingRule` / `BiQuotaConfig` 基础类型（缺 statusType / OperateParams / SearchParams / List）

## 功能边界

### 做

1. **后端 CRUD**：两个模型各 6 路由（list/get/create/update/delete/batch_delete），用 `CRUDRouter` 生成
2. **接入脱敏**：`mask_columns` 在智能对话 `executor_node` + 图表 `refresh_chart` 路径接入；SQL 工作台/异步查询/仪表盘预览**不接入**（管理员调试需要原始数据；异步查询结果落 CSV 不脱敏避免歧义）
3. **接入配额**：`load_quota_config(scope_type, scope_id)` 链式查找（datasource > user > global），在 `sandbox/executor.py` 的 `execute_sql` 中替换 `_default_config`
4. **缓存**：脱敏规则与配额配置用 Redis 缓存（TTL 60s），变更时主动失效
5. **菜单/按钮/角色**：新增 2 个菜单（脱敏规则 order=10、配额配置 order=11）+ 8 个按钮码，仅分配给 `R_BI_ADMIN`
6. **前端**：2 个管理页（列表 + 增改模态框）+ i18n + service API
7. **错误码**：新增 4120-4121 两个 NOT_FOUND 码（sandbox 已硬编码的 4102/4103/4104 顺带登记进 Code 类）

### 不做

- 不给 `BiMaskingRule` 加 `tenant_id`（全局配置语义，避免新迁移）
- 不做配额配置的"测试"接口（配额是防御性配置，无明确测试语义）
- 不做脱敏规则的"试运行"接口（脱敏是展示层逻辑，在 SQL 工作台预览即可）
- 不接入 SQL 工作台 / 异步查询 / 仪表盘预览的脱敏（调试与落盘场景）

## 架构决策

### 1. BiMaskingRule 全局配置

模型无 `tenant_id` / `scope_id`，作为**全局配置**：所有 BI 管理员可见可编辑，对所有查询生效。符合"脱敏规则全租户统一"的安全语义。若未来要做租户隔离，再加字段 + 迁移。

### 2. BiQuotaConfig 三层作用域

模型已有 `scope_type`（global/user/datasource）+ `scope_id`。查询时按优先级链式查找：
1. `scope_type='datasource' AND scope_id={datasource_id}` — 最具体
2. `scope_type='user' AND scope_id={user_id}`
3. `scope_type='global' AND scope_id IS NULL` — 兜底
4. 都没命中 → 回退 env 变量的 `_default_config`

同一 `(scope_type, scope_id)` 组合只允许一条启用配置（DB 层不强制，service 层校验）。

### 3. 脱敏接入点

在"结果返回给用户"的边界接入，而非 `execute_sql` 层：
- `agent/nodes/executor.py` 的 `executor_node`：智能对话路径，结果直接展示给用户 → **接入**
- `services_chart.py` 的 `refresh_chart`：图表刷新，快照展示给用户 → **接入**
- `api/sql_workbench.py` 的 run：管理员调试 → **不接入**
- `services_async_query.py`：结果落 CSV → **不接入**
- `services_dashboard.py` 的 `refresh_dashboard`：复用 `_rerun_chart_sql`，天然继承图表刷新的脱敏 → 自动接入

### 4. 配额接入点

在 `sandbox/executor.py` 的 `execute_sql` 中接入：把 `scope=f"user:{user_id}"` 拆成 `(scope_type='user', scope_id=user_id)`，调 `load_quota_config` 链式查找，转成 `QuotaConfig` dataclass 传给 `check_quota` / `check_row_limit` / `get_timeout`。

### 5. 缓存策略

- 脱敏规则缓存 key：`bi:masking:rules:enabled`，TTL 60s，存启用规则的 JSON 列表
- 配额配置缓存 key：`bi:quota:config:{scope_type}:{scope_id}`，TTL 60s
- 变更（create/update/delete）时主动 DEL 对应 key
- 读流程：cache → miss → DB → 写 cache → 返回

### 6. 错误码

```
4120 BI_MASKING_RULE_NOT_FOUND  脱敏规则不存在
4121 BI_QUOTA_CONFIG_NOT_FOUND  配额配置不存在
```

顺带把 sandbox 硬编码的幽灵码登记进 `Code` 类（追加新码不需用户确认）：
```
4102 BI_QUERY_BREAKER_OPEN      查询熔断
4103 BI_QUERY_ROW_LIMIT         行数超限
4104 BI_QUERY_EXEC_FAILED       SQL 执行失败
```

## 数据模型影响

**无新迁移**。两个模型在 `0001_initial.py` 已建表。

## API 设计

### BiMaskingRule（6 路由）

| Method | Path | Name | Button |
|---|---|---|---|
| POST | `/masking/search` | `bi.masking.list` | `B_BI_MASKING_VIEW` |
| GET | `/masking/{id}` | `bi.masking.get` | `B_BI_MASKING_VIEW` |
| POST | `/masking` | `bi.masking.create` | `B_BI_MASKING_CREATE` |
| PUT | `/masking/{id}` | `bi.masking.update` | `B_BI_MASKING_EDIT` |
| DELETE | `/masking/{id}` | `bi.masking.delete` | `B_BI_MASKING_DELETE` |
| DELETE | `/masking/batch_delete` | `bi.masking.batch_delete` | `B_BI_MASKING_DELETE` |

搜索字段：`name`（contains）、`mask_type`（exact）、`status_type`（exact）。

### BiQuotaConfig（6 路由）

| Method | Path | Name | Button |
|---|---|---|---|
| POST | `/quota/search` | `bi.quota.list` | `B_BI_QUOTA_VIEW` |
| GET | `/quota/{id}` | `bi.quota.get` | `B_BI_QUOTA_VIEW` |
| POST | `/quota` | `bi.quota.create` | `B_BI_QUOTA_CREATE` |
| PUT | `/quota/{id}` | `bi.quota.update` | `B_BI_QUOTA_EDIT` |
| DELETE | `/quota/{id}` | `bi.quota.delete` | `B_BI_QUOTA_DELETE` |
| DELETE | `/quota/batch_delete` | `bi.quota.batch_delete` | `B_BI_QUOTA_DELETE` |

搜索字段：`name`（contains）、`scope_type`（exact）、`status_type`（exact）。

### 额外服务函数（非路由）

- `load_masking_rules() -> list[BiMaskingRule]`：从缓存/DB 加载启用规则
- `invalidate_masking_cache() -> None`：CRUD 变更时调用
- `load_quota_config(scope_type, scope_id) -> QuotaConfig`：链式查找 + 缓存
- `invalidate_quota_cache(scope_type, scope_id) -> None`：CRUD 变更时调用

## 前端设计

### 页面

- `web/src/views/bi/masking/index.vue` — 脱敏规则列表（表格 + 搜索 + 增改模态框）
- `web/src/views/bi/masking/modules/masking-operate-modal.vue` — 增改模态框
- `web/src/views/bi/quota/index.vue` — 配额配置列表
- `web/src/views/bi/quota/modules/quota-operate-modal.vue` — 增改模态框

### 路由

由 elegant-router 自动生成：
- `bi_masking` → `/bi/masking`
- `bi_quota` → `/bi/quota`

### i18n

在 `_generated/bi/zh-cn.ts` / `en-us.ts` / `types.d.ts` 追加 `page.bi.masking.*` 和 `page.bi.quota.*` 命名空间。在 `langs/zh-cn.ts` / `en-us.ts` 的 `route` 区块追加 `bi_masking` / `bi_quota` 路由名。

## 安全考量

1. **权限隔离**：脱敏/配额配置仅 `R_BI_ADMIN` 可见可编辑，`R_BI_ANALYST` 只消费配置
2. **脱敏不可绕过**：智能对话与图表刷新路径强制脱敏，分析师无法看到原始敏感数据
3. **配额熔断**：按用户/数据源维度熔断，防止单用户拖垮数据库
4. **缓存失效**：配置变更后 60s 内全网生效（TTL + 主动 DEL 双保险）
5. **SQL 工作台豁免**：管理员调试需要原始数据，但 SQL 工作台本身有 `B_BI_SQL_RUN` 按钮权限门槛

## 测试策略

- **后端**：模型/服务/API 三层测试
  - `tests/test_bi_masking.py`：CRUD + `load_masking_rules` 缓存 + `mask_columns` 接入 executor_node
  - `tests/test_bi_quota.py`：CRUD + `load_quota_config` 链式查找 + 缓存失效 + 接入 execute_sql
- **前端**：service API mock 测试（参考 `bi-dashboard.test.ts` 模式）

## 验收标准

1. `just check` 全绿（ruff + basedpyright + pytest + oxlint + eslint + vue-tsc + vitest）
2. `R_BI_ADMIN` 可在 UI 创建/编辑/删除脱敏规则与配额配置
3. `R_BI_ANALYST` 看不到这两个菜单
4. 配置一条 phone 脱敏规则后，智能对话查询含 phone 列时返回脱敏值
5. 配置一条 user 级配额（max_rows=10）后，该用户查询超 10 行被拦截
6. 配置变更后 60s 内生效（缓存 TTL）

## 依赖文件

### 后端
- `app/business/bi/api/masking.py`（新建）
- `app/business/bi/api/quota.py`（新建）
- `app/business/bi/api/__init__.py`（修改：挂载路由）
- `app/business/bi/services_masking.py`（新建：load_masking_rules + 缓存）
- `app/business/bi/services_quota.py`（新建：load_quota_config + 缓存）
- `app/business/bi/sandbox/masking.py`（已有，无需改）
- `app/business/bi/sandbox/quota.py`（修改：QuotaConfig dataclass 已有，无需改）
- `app/business/bi/sandbox/executor.py`（修改：接入 load_quota_config）
- `app/business/bi/agent/nodes/executor.py`（修改：接入 mask_columns）
- `app/business/bi/services_chart.py`（修改：refresh_chart 接入 mask_columns）
- `app/business/bi/init_data.py`（修改：菜单 + 按钮 + 角色权限）
- `app/business/bi/config.py`（修改：追加缓存 TTL 配置）
- `app/core/code.py`（修改：新增 4120/4121 + 登记 4102/4103/4104）
- `.env.example`（修改：追加缓存 TTL 配置）

### 前端
- `web/src/service/api/bi-masking.ts`（新建）
- `web/src/service/api/bi-quota.ts`（新建）
- `web/src/views/bi/masking/index.vue`（新建）
- `web/src/views/bi/masking/modules/masking-operate-modal.vue`（新建）
- `web/src/views/bi/quota/index.vue`（新建）
- `web/src/views/bi/quota/modules/quota-operate-modal.vue`（新建）
- `web/src/typings/api/bi.d.ts`（修改：补全类型）
- `web/src/locales/langs/_generated/bi/zh-cn.ts`（修改）
- `web/src/locales/langs/_generated/bi/en-us.ts`（修改）
- `web/src/locales/langs/_generated/bi/types.d.ts`（修改）
- `web/src/locales/langs/zh-cn.ts`（修改：route 命名）
- `web/src/locales/langs/en-us.ts`（修改：route 命名）

### 测试
- `tests/test_bi_masking.py`（新建）
- `tests/test_bi_quota.py`（新建）
- `web/src/service/api/__tests__/bi-masking.test.ts`（新建）
- `web/src/service/api/__tests__/bi-quota.test.ts`（新建）
