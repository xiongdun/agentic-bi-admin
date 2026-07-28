# AgenticBIAdmin 项目记忆

> 适用于本仓库（`d:\code\python\agentic-bi-admin`）所有会话。优先级仅次于 `AGENTS.md`（项目规则覆盖用户偏好）。

---

## 1. 项目定位

**AgenticBIAdmin** = FastSoyAdmin（FastAPI + Vue3 全栈后台管理模板）+ **AgenticBI**（智能数据分析业务模块，**待实现**）。

- 仓库结构由 `AGENTS.md` / `CLAUDE.md` 主导（AI 协作指南，动手前必读）
- 在线文档：https://sleep1223.github.io/fast-soy-admin-docs/ + 离线 `docs/` 镜像

## 2. ⚠️ 当前实现状态（重要）

- **已实现业务模块**：仅 [app/business/hr/](file:///d:/code/python/agentic-bi-admin/app/business/hr)（HR 管理 Demo），是 manifest 模式范例
- **BI 业务模块**：[app/business/bi/](file:///d:/code/python/agentic-bi-admin/app/business/bi) 与 [web/src/views/bi/](file:///d:/code/python/agentic-bi-admin/web/src/views/bi) **目前均无任何代码**，仅有设计文档 [docs/bi/agentic-bi.md](file:///d:/code/python/agentic-bi-admin/docs/bi/agentic-bi.md)（已按 AgenticBIAdmin 规范重写过）
- 落地 BI 模块时参考 [docs/bi/agentic-bi.md](file:///d:/code/python/agentic-bi-admin/docs/bi/agentic-bi.md) + [app/business/hr/](file:///d:/code/python/agentic-bi-admin/app/business/hr) 范例

## 3. 后端架构

### 3.1 顶层包与依赖铁律

| 包 | 职责 | 依赖方向 |
|---|---|---|
| `app/core/` | 框架基础设施 | **不依赖** system / business |
| `app/system/` | 内置系统模块（auth/RBAC/user/menu/api/dictionary/radar） | **仅依赖** `app/core/` |
| `app/business/<x>/` | 业务模块（autodiscover 自动加载） | 依赖 `app/utils`；**不得反向 import `app.system.*`**（白名单：`init_helper` 暴露的 service）；**不得互相 import** 兄弟业务模块 |
| `app/utils/__init__.py` | 业务开发者的统一 import 入口 | 业务代码一律从这里导入 |

### 3.2 业务模块统一分层

`api/` → `services/` → `controllers/` → `models/ + schemas/`

### 3.3 autodiscover（[app/core/autodiscover.py](file:///d:/code/python/agentic-bi-admin/app/core/autodiscover.py)）

- `app/business/<name>/` 下含 `__init__.py` 的子目录即业务模块
- **manifest 模式（推荐）**：`module.py` 导出 `module = BusinessModule(...)`，含 routers/init/permissions/events/data_policies/tasks
- **legacy 模式**：`api.py` 或 `api/__init__.py` 暴露 `router`
- 路由前缀自动加 `/<module>`，业务 router 内不要重复带模块前缀
- `BUSINESS_MODULES_DISABLED=mod1,mod2` 环境变量运行时禁用模块

### 3.4 启动生命周期（[app/core/init_app.py](file:///d:/code/python/agentic-bi-admin/app/core/init_app.py)）

```
create_app() → register_db / register_exceptions / register_routers("/api")
lifespan(app) — Redis 锁 leader-only
  init_menus() → refresh_api_list() → init_users()
  for each business init() → refresh_all_cache()
```

**多 worker**：granian；Redis 锁 `app:init_lock` 选 leader，`app:init_done` 标记完成。

## 4. 核心抽象（不可破坏）

### 4.1 响应契约

- 一律 `Success` / `SuccessExtra` / `Fail`，HTTP 恒 200，格式 `{"code": str, "msg": str, "data": Any}`
- ❌ 不要返回裸 dict / `JSONResponse(...)` / 字面量
- ❌ 不要 `raise HTTPException`；用 `raise BizError(code, msg)` 穿透任意层
- 仅 api 层用 `return Fail(...)`

### 4.2 响应码（[app/core/code.py](file:///d:/code/python/agentic-bi-admin/app/core/code.py)）

`0000` 成功 / `1xxx` 系统 / `21xx` 认证 / `22xx` 授权 / `23xx` 冲突 / `24xx` 业务 / `25xx` 限流 / `26xx` Schema 兜底 / `4000+` 业务自定义

### 4.3 Schema

- 业务 schema 一律 `from app.utils import SchemaBase`；分页 `PageQueryBase`
- ID 字段 `SqidId`；路径参数 `SqidPath`（sqid 编码）
- Update schema 用 `make_optional(XxxCreate, "XxxUpdate")`

### 4.4 Model

- 继承 `BaseModel + AuditMixin`；软删加 `SoftDeleteMixin`；树结构加 `TreeMixin`
- 文件头加 `# pyright: reportIncompatibleVariableOverride=false`
- 字段写 `description="..."`；类 docstring 写中文资源名
- `Meta.table` 用 `biz_<module>_<entity>` 前缀
- **每个 `ForeignKeyField` / `OneToOneField` 上方显式声明 `<name>_id: int`**
- `BaseModel.to_dict()` 自动 camelCase + sqid 编码

### 4.5 CRUDRouter（[app/core/router.py](file:///d:/code/python/agentic-bi-admin/app/core/router.py)）

标准 6 路由（POST /search、GET/PATCH/DELETE /{id}、POST、DELETE 批量）
- 自定义：`@crud.override("create")`
- 关闭：`enable_routes={"get", "delete"}`
- 按钮权限：`action_dependencies={"create": [require_buttons("B_X_CREATE")], ...}`
- `route_key_prefix="bi.datasources"` → 生成 `APIRoute.name = bi.datasources.list`
- `data_policy="datasource_read"` → list 路由自动 `apply_data_policy(...)`
- `soft_delete=True` / `tree_endpoint=True` 配合对应 Mixin

### 4.6 CRUDBase + build_search

- 提供 `get / list / create / update / remove / soft_remove / get_tree / build_search`
- `build_search()` 从 Pydantic schema + `SearchFieldConfig`（contains/icontains/exact/in/range）自动构造 Q
- 事务：`async with in_transaction(get_db_conn(Model))`，不硬编码连接名

### 4.7 权限（RBAC + 行级 data_scope）

```
User ─M2M─ Role ─M2M─ Menu / Button / Api
              └─field: data_scope (all / scope / self / custom)
```

- 超管 `R_SUPER` 跳过所有权限校验
- `DependAuth` / `DependPermission` / `require_buttons(...)` / `require_roles(...)`
- 业务里用 `has_role_code(...)` / `has_button_code(...)`
- 写接口必须挂按钮权限；不要硬判 `role_code == "..."`
- 行级权限用 `scope_id` + `scope_id_field`（可映射为 `tenant_id`/`project_id`/`store_id`）

### 4.8 事件总线（[app/core/events.py](file:///d:/code/python/agentic-bi-admin/app/core/events.py)）

跨模块联动走 `emit("event.name", **kwargs)` / `@on("event.name")`，仅进程内。

### 4.9 init_helper（[app/system/services/init_helper.py](file:///d:/code/python/agentic-bi-admin/app/system/services/init_helper.py)）

业务模块允许从这里 import：`ensure_menu` / `ensure_role` / `ensure_user` / `reconcile_menu_subtree` / `refresh_api_list` / `apply_init_data`

⚠️ `reconcile_menu_subtree(...)` 启用的子树是单一数据源，Web UI 手工创建的菜单/按钮会在下次重启被清除。

### 4.10 缓存

业务自有缓存按 `<module>_<resource>:<scope>` 命名，读→miss→查→写 TTL，变更时主动失效。

## 5. 工具链与命令

- **Python 走 `uv`**（`uv sync` / `uv add <pkg>` / `uv run <cmd>`），❌ 不直调 `python`/`pip`
- **前端走 `pnpm`**；**命令入口走 `just`**
- 提交前必跑 `just check`

### 5.1 常用 just 命令

```bash
just install                  # 装后端 (uv sync) + 前端 (pnpm install)
cp .env.example .env          # 首次复制环境变量
just db-init                  # 首次初始化数据库
just run                      # 并行启动后端 :9999 + 前端 :9527
just run backend / frontend   # 仅后端 / 仅前端
just stop                     # 停止 dev server
just mm                       # makemigrations + migrate
just fmt                      # 格式化 + 安全 lint 修复
just check                    # 提交前门禁（fmt + typecheck + test）
just cli-init <name>          # 创建业务模块骨架
just cli-crud <name> 中文名   # 一键生成前后端 CRUD + i18n
just dbhistory                # 迁移历史
just init-plan                # dry-run 业务 init 声明 + route-key 漂移检查
just module-list              # 列出已发现的业务模块
just check-boundaries         # 检查业务模块 import 边界
```

## 6. 数据库

- 默认 `tortoise-orm[asyncpg]` + `aiosqlite`，PostgreSQL/SQLite 开箱即用
- 切 MySQL/MSSQL/Oracle：`uv sync --extra {mysql|mssql|oracle}`
- 业务模块可在 `config.py` 声明独立 `DB_URL`，autodiscover 注册为 `conn_<biz>`
- 迁移走 `aerich`（`just mm`），❌ 不直接 SQL 改数据库

## 7. 前端架构

### 7.1 技术栈（[web/package.json](file:///d:/code/python/agentic-bi-admin/web/package.json)）

Vue 3.5 + Vite 8 + TS 6 + **Naive UI 2.44** + pro-naive-ui + Elegant Router 0.3.8 + Pinia 3 + **UnoCSS 66** + vue-i18n 11 + Alova + axios；图表 echarts 6 / visactor vchart / antv g2/g6。

### 7.2 目录（[web/src](file:///d:/code/python/agentic-bi-admin/web/src)）

- `views/<module>/<feature>/index.vue` + `modules/*.vue`：页面（Elegant Router 扫描自动生成路由）
- `service/api/<module>.ts`：业务 API，在 `index.ts` re-export
- `service/request/{index,shared,type}.ts`：共享 axios 实例（基于 `@sa/axios`，扁平 `[data, error]` 返回）
- `store/modules/{auth,route,tab,theme,app,business}/`：Pinia setup store
- `router/elegant/{routes,imports,transform}.ts`：自动生成产物，不要手改；新增页面后 `pnpm gen-route`
- `typings/api/<module>.d.ts`：后端响应类型 `Api.<Module>.<Entity>`
- `locales/langs/{zh-cn,en-us}.ts` 基础包 + `_generated/<module>/` 模块包（`locale.ts` 用 glob 自动合并）
- `hooks/business/auth.ts`：`useAuth().hasAuth(...)` 按钮码判断
- `theme/preset/{default,dark,compact,azir}.json`：主题预设

### 7.3 请求层关键

- `request = createFlatRequest(...)`：返回 `[data, error]` 元组
- `isBackendSuccess`：`String(code) === VITE_SERVICE_SUCCESS_CODE`（项目配 `0000`）
- `onBackendFail` 按码分流：
  - `VITE_SERVICE_LOGOUT_CODES=2100,2101,2104,2105` → `resetStore()` 跳登录
  - `VITE_SERVICE_MODAL_LOGOUT_CODES=2102,2106` → 弹窗后登出
  - `VITE_SERVICE_EXPIRED_TOKEN_CODES=2103` → refresh token，成功后重放原请求

### 7.4 类型映射

```
后端 {code, msg, data} → App.Service.Response<T> → transform 拆出 data: T
业务侧 request<Api.Bi.Datasource>() 拿强类型数据
```

## 8. AgenticBI 业务模块规划约定（待实现时遵循）

参考 [docs/bi/agentic-bi.md](file:///d:/code/python/agentic-bi-admin/docs/bi/agentic-bi.md)（已重写）+ [app/business/hr/](file:///d:/code/python/agentic-bi-admin/app/business/hr) 范例：

- **manifest 模式**：`app/business/bi/module.py` 暴露 `module = BusinessModule(name="bi", title="智能 BI", ...)`
- **分层**：`api/` → `services/` → `controllers/` → `models/ + schemas/`
- **路由前缀**：autodiscover 自动加 `/business/bi`；完整路径 `/api/v1/business/bi/<resource>/...`
- **标准 CRUD**：`CRUDRouter(...)` + `route_key_prefix="bi.<resource>"`
- **角色/按钮码**：`R_BI_ADMIN` / `R_BI_ANALYST`；按钮 `B_BI_<RESOURCE>_<ACTION>`
- **IaC 子树**：`init_data.py` 用 `ensure_menu` + `reconcile_menu_subtree`
- **多 LLM Provider**：`llm/` 抽象层（DeepSeek / Ollama / 通义 / OpenAI / Mock / Custom），`.env` 的 `LLM_DEFAULT_PROVIDER` 切换
- **多数据源**：PostgreSQL / MySQL / ClickHouse / Trino / SQLite，sqlglot 做方言转换 + AST 白名单校验
- **SQL 沙箱**：`sandbox/whitelist.py`（sqlglot AST 白名单）+ `masking.py` + `tenant.py` + `quota.py` + `executor.py`
- **Agent 流水线**：5 节点 intent → sql_gen → sql_validate → executor → explain（执行失败不 explain），`runner.py` 暴露 `run_chat_turn(...)`
- **SSE 流式**：基于 `sse_starlette`（需 `uv add sse-starlette`），封装在 `app/business/bi/sse.py`
- **Guard 限流**：BI 模块在 `module.py` 声明 `ENDPOINT_RATE_LIMITS`（autodiscover 自动合并到 Guard），为 SSE/SQL 路径设更宽松配额；如需完全跳过 Guard，需改 [app/core/init_app.py](file:///d:/code/python/agentic-bi-admin/app/core/init_app.py) 的 `_make_guard_config()` `exclude_paths`（框架级变更，需确认）—— ⚠️ 项目**没有** `GUARD_EXCLUDE_PATHS` 环境变量
- **新增依赖**：`uv add sqlglot "sqlalchemy[asyncio]" cryptography sse-starlette`（当前 pyproject.toml 未含）；`app/utils/` 下**没有** sse.py / crypto.py / sqlglot_utils.py，BI 需自建在 `app/business/bi/` 下
- **模块结构**：标准分层用扁平文件（`models.py` / `schemas.py` / `controllers.py` / `services.py`，与 HR + CLI 一致）；BI 特有能力（agent/ sandbox/ llm/ metadata/ security/）用子包
- **前端落点**：API `web/src/service/api/bi*.ts`；页面 `web/src/views/bi/<feature>/index.vue` + `modules/*.vue`；类型 `web/src/typings/api/bi.d.ts`；i18n `web/src/locales/langs/_generated/bi/`

## 9. 命名规范

| 类型 | 规范 |
|---|---|
| 文件 / 目录 | `snake_case` |
| 类 | `PascalCase` |
| 函数 / 方法 | `snake_case` |
| 常量 | `UPPER_SNAKE_CASE` |
| API 路径 | `kebab-case`，资源名复数，不带尾斜杠 |
| Schema 字段（Python） | `snake_case`；HTTP 边界（前端） `camelCase` |
| 角色编码 | `R_<UPPER>`（如 `R_BI_ADMIN`） |
| 按钮编码 | `B_<MODULE>_<RESOURCE>_<ACTION>`（如 `B_BI_DS_CREATE`） |
| 路由名（route key） | `module_subpage`（如 `bi_chat`） |
| 业务表名 | `biz_<module>_<entity>` |
| 业务缓存 key | `<module>_<resource>:<scope>` |
| 文档/日志/生成结果路径 | 统一用 `/` |

## 10. 权限边界

### 始终允许

- 读仓库文件、`.env.example`、`justfile`、`pyproject.toml`、`web/package.json`
- 跑只读 / `--check` / dry-run 命令
- `just --list` / `just dbhistory` / `just fmt` / `just check`
- 读系统表/元数据

### 需要用户确认

- **框架级**：编辑 `app/core/*`、`app/utils/__init__.py` re-export、`init_app.py` 全局中间件/异常/路由挂载、`app/core/code.py` 已有响应码、`justfile` 已有 target 语义、`pyproject.toml` / `web/package.json` 主版本依赖升级
- **数据库**：`migrate`（先给 SQL）、手写迁移文件、改 `BaseModel` / `AuditMixin` / `SoftDeleteMixin` / `TreeMixin`
- **RBAC/安全**：改 `init_data.py` 菜单/按钮/角色种子、`R_SUPER` 行为、`DependPermission` 校验逻辑、`app/core/data_scope.py` 行级规则、`JWT_*` / `GUARD_*` / `CORS_ORIGINS`
- **部署/服务**：改 `deploy/`、`docker-compose.yml`、`nginx.conf`，重启服务、`just up` / `just down`

### 禁止 — 始终需要明确授权

破坏性操作必须用户明确说"确认/yes"：

- `DROP DATABASE` / `DROP TABLE` / `TRUNCATE` / `DELETE` 不带 WHERE
- 反向迁移 / 手工 downgrade
- `rm -rf migrations/` / `rm app_system.sqlite3`
- `git reset --hard` / `git push --force`（非个人 feature 分支）
- 删除业务模块目录 `app/business/<name>/`
- 直接 SQL 改用户/角色/权限表绕过 `init_data`
- 清空 Redis（`FLUSHDB` / `FLUSHALL`）

## 11. Windows 平台已知坑

### Guard Redis 兼容性（已修复）

- 现象：登录返回 `{"code":"5001","msg":"服务器内部错误: GuardRedisError"}`
- 根因：Windows + redis-py 4.6.0 + ProactorEventLoop，Guard 中间件首次请求时 `Redis.from_url(...).ping()` 抛 `OSError(22)`
- 修复：[app/core/init_app.py](file:///d:/code/python/agentic-bi-admin/app/core/init_app.py) `_make_guard_config()` 已加 `enable_redis = sys.platform != "win32"`，Windows 回退进程内限流
- 根治：`uv add "redis>=5.0"` 后改回 `enable_redis=True`

### Redis 本地安装

- 安装路径：`D:\Redis\`（含 `redis-server.exe` / `redis-cli.exe`，tporadowski/redis 5.0.14.1）
- 已用默认配置（无密码、bind 127.0.0.1、port 6379）启动
- 关机/重启电脑后需再次手动启动：`Start-Process -FilePath "D:\Redis\redis-server.exe" -WorkingDirectory "D:\Redis" -WindowStyle Hidden`
- 验证：`D:\Redis\redis-cli.exe ping` → `PONG`
- 如需开机自启：`redis-server --service-install redis.windows-service.conf`（需管理员）

## 12. 运行环境

- 后端：http://127.0.0.1:9999 （granian，1 worker）— 启动命令 `uv run python run.py`（项目根目录）
- 前端：http://localhost:9527/ （Vite v8.0.12，test 模式）— 启动命令 `cd web; pnpm dev`
- Redis：127.0.0.1:6379（PID 见启动时进程号）
- DB：SQLite（`app_system.sqlite3`，仓库根目录）

## 13. 关键文件速查

### 后端核心

- [.env](file:///d:/code/python/agentic-bi-admin/.env) — 运行配置
- [justfile](file:///d:/code/python/agentic-bi-admin/justfile) — 命令入口
- [app/core/init_app.py](file:///d:/code/python/agentic-bi-admin/app/core/init_app.py) — make_middlewares / register_db / register_exceptions / register_routers
- [app/core/autodiscover.py](file:///d:/code/python/agentic-bi-admin/app/core/autodiscover.py) — 业务模块发现
- [app/core/business.py](file:///d:/code/python/agentic-bi-admin/app/core/business.py) — BusinessModule / BusinessRouter / DataPolicy / EventSpec
- [app/core/router.py](file:///d:/code/python/agentic-bi-admin/app/core/router.py) — CRUDRouter / SearchFieldConfig
- [app/core/crud.py](file:///d:/code/python/agentic-bi-admin/app/core/crud.py) — CRUDBase / get_db_conn
- [app/core/base_model.py](file:///d:/code/python/agentic-bi-admin/app/core/base_model.py) — BaseModel / AuditMixin / TreeMixin
- [app/core/base_schema.py](file:///d:/code/python/agentic-bi-admin/app/core/base_schema.py) — SchemaBase / PageQueryBase / Success / SuccessExtra / Fail / make_optional
- [app/core/code.py](file:///d:/code/python/agentic-bi-admin/app/core/code.py) — 响应码
- [app/core/dependency.py](file:///d:/code/python/agentic-bi-admin/app/core/dependency.py) — DependAuth / DependPermission / require_buttons / require_roles
- [app/core/data_scope.py](file:///d:/code/python/agentic-bi-admin/app/core/data_scope.py) — DataScopeType / build_scope_filter
- [app/core/ctx.py](file:///d:/code/python/agentic-bi-admin/app/core/ctx.py) — CTX_USER / has_role_code / has_button_code
- [app/core/events.py](file:///d:/code/python/agentic-bi-admin/app/core/events.py) — emit / on
- [app/core/exceptions.py](file:///d:/code/python/agentic-bi-admin/app/core/exceptions.py) — BizError / SchemaValidationError
- [app/core/policy.py](file:///d:/code/python/agentic-bi-admin/app/core/policy.py) — apply_data_policy
- [app/core/sqids.py](file:///d:/code/python/agentic-bi-admin/app/core/sqids.py) — encode_id / decode_id
- [app/utils/__init__.py](file:///d:/code/python/agentic-bi-admin/app/utils/__init__.py) — 业务统一 import 入口
- [app/utils/sse.py](file:///d:/code/python/agentic-bi-admin/app/utils/sse.py) — SSE 工具
- [app/utils/crypto.py](file:///d:/code/python/agentic-bi-admin/app/utils/crypto.py) — Fernet 加解密
- [app/utils/sqlglot_utils.py](file:///d:/code/python/agentic-bi-admin/app/utils/sqlglot_utils.py) — SQL 方言转换/校验
- [app/system/services/init_helper.py](file:///d:/code/python/agentic-bi-admin/app/system/services/init_helper.py) — ensure_menu / ensure_role / ensure_user / reconcile_menu_subtree / refresh_api_list / apply_init_data
- [app/business/hr/module.py](file:///d:/code/python/agentic-bi-admin/app/business/hr/module.py) — manifest 范例
- [app/business/hr/init_data.py](file:///d:/code/python/agentic-bi-admin/app/business/hr/init_data.py) — 菜单/角色/按钮种子范例
- [app/cli/](file:///d:/code/python/agentic-bi-admin/app/cli) — 代码生成器

### 文档

- [AGENTS.md](file:///d:/code/python/agentic-bi-admin/AGENTS.md) — AI 协作指南（最优先）
- [docs/standard/backend.md](file:///d:/code/python/agentic-bi-admin/docs/standard/backend.md) — 后端 PR review checklist
- [docs/standard/vue.md](file:///d:/code/python/agentic-bi-admin/docs/standard/vue.md) — 前端规范
- [docs/standard/naming.md](file:///d:/code/python/agentic-bi-admin/docs/standard/naming.md) — 命名规范
- [docs/getting-started/architecture.md](file:///d:/code/python/agentic-bi-admin/docs/getting-started/architecture.md) — 架构总览
- [docs/develop/](file:///d:/code/python/agentic-bi-admin/docs/develop) — 开发指南
- [docs/bi/agentic-bi.md](file:///d:/code/python/agentic-bi-admin/docs/bi/agentic-bi.md) — BI 设计 PRD（已重写）

### 前端

- [web/package.json](file:///d:/code/python/agentic-bi-admin/web/package.json) — 依赖与 scripts
- [web/eslint.config.js](file:///d:/code/python/agentic-bi-admin/web/eslint.config.js) + [web/.oxlintrc.json](file:///d:/code/python/agentic-bi-admin/web/.oxlintrc.json)
- [web/src/service/request/index.ts](file:///d:/code/python/agentic-bi-admin/web/src/service/request/index.ts) — 主请求实例
- [web/src/router/index.ts](file:///d:/code/python/agentic-bi-admin/web/src/router/index.ts) + [web/src/router/guard/route.ts](file:///d:/code/python/agentic-bi-admin/web/src/router/guard/route.ts)
- [web/src/typings/app.d.ts](file:///d:/code/python/agentic-bi-admin/web/src/typings/app.d.ts) — App.Service.Response / App.I18n.Schema
- [web/src/locales/locale.ts](file:///d:/code/python/agentic-bi-admin/web/src/locales/locale.ts) — _generated 自动合并
