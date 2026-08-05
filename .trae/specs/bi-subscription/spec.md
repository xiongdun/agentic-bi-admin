# BI 仪表盘定时订阅推送 Spec — Batch D-2

## 目标

让用户订阅 BiDashboard，按 cron 表达式定时刷新仪表盘所有图表，刷新完成后推送站内消息（成功摘要 / 失败报告）。用户可在前端管理订阅（创建/暂停/删除/查看推送记录）。

## 背景

- Batch C 已实现 BiDashboard + refresh_dashboard（Semaphore=5 并发，25s 超时）
- Batch D-1 已实现 BiMaskingRule/BiQuotaConfig 的 CRUD + PeriodicTask 机制（`bi.async_query.cleanup` 每 24h leader_only）
- 项目无通知基础设施，需新建 `notify/` 子模块
- PeriodicTask handler 签名为无参协程，通过 `state.get_runtime_redis()` 获取 Redis

## 功能边界

### 做

1. **BiSubscription 模型**：订阅记录，存 dashboard_id + cron 表达式 + user_id + 状态
2. **BiNotifyRecord 模型**：推送记录，存 subscription_id + 内容 + 状态 + 时间
3. **CRUD API**：订阅管理 6 路由（list/get/create/update/delete/batch_delete）+ 推送记录只读 2 路由（list/get）
4. **cron 调度**：PeriodicTask `bi.subscription.dispatch`，每 60s leader_only 触发，扫描到期订阅并执行刷新
5. **同步刷新**：handler 内直接调 `refresh_dashboard`（已有 Semaphore 限并发），刷新完写 BiNotifyRecord
6. **站内消息**：前端铃铛图标轮询未读消息，点击跳转订阅详情
7. **cron 解析**：用 `croniter` 库计算下次触发时间（轻量，无额外依赖）
8. **菜单/按钮/角色权限**：订阅管理菜单（order=12）+ 8 按钮码，R_BI_ADMIN 和 R_BI_ANALYST 均可用（订阅是用户级能力）
9. **迁移 0006**：新建 BiSubscription + BiNotifyRecord 两张表

### 不做

- 不做邮件/飞书推送（MVP 仅站内消息，后续可扩展）
- 不做图表级订阅（仅仪表盘）
- 不做异步队列执行（同步刷新，handler 内 Semaphore 限并发）
- 不做订阅"立即触发"接口（用户可手动 refresh_dashboard 代替）
- 不做消息已读批量标记（前端逐条标记即可）

## 架构决策

### 1. cron 表达式解析

用 `croniter` 库（纯 Python，无 C 扩展）。订阅创建时校验 cron 表达式合法性。PeriodicTask handler 每 60s 扫描所有 `status_type=enable AND next_run_at <= now` 的订阅，执行刷新后更新 `next_run_at = croniter.get_next()`。

### 2. BiSubscription 模型设计

```python
class BiSubscription(BaseModel, AuditMixin):
    id: int (PK)
    name: str (100)              # 订阅名称
    dashboard_id: int            # 仪表盘 ID（不走 FK，软删不级联）
    user_id: int                 # 订阅者用户 ID（行级隔离字段）
    cron_expr: str (100)         # cron 表达式（5 字段：分 时 日 月 周）
    next_run_at: datetime        # 下次触发时间（UTC）
    last_run_at: datetime | null # 上次触发时间
    last_status: str (20) | null # 上次执行状态 success/failed
    status_type: StatusType      # enable/disable
    tenant_id: int               # 行级 scope_id（存 user.id，与 BiChart 一致）
```

### 3. BiNotifyRecord 模型设计

```python
class BiNotifyRecord(BaseModel, AuditMixin):
    id: int (PK)
    subscription_id: int         # 订阅 ID（不走 FK）
    user_id: int                 # 接收者用户 ID（行级隔离）
    title: str (200)             # 消息标题
    content: str (2000)          # 消息内容（JSON：成功摘要 / 失败原因）
    status: str (20)             # success / failed
    is_read: bool = False        # 是否已读
    tenant_id: int               # 行级 scope_id
```

### 4. PeriodicTask 调度

```python
# module.py
PeriodicTask(
    name="bi.subscription.dispatch",
    handler=dispatch_subscriptions,
    interval_seconds=60,
    leader_only=True,
    run_immediately=False,
)
```

`dispatch_subscriptions()` 逻辑：
1. 查 `BiSubscription.filter(status_type=enable, next_run_at__lte=now)`
2. 对每个订阅：调 `refresh_dashboard(dashboard_id, user_id, tenant_id)`
3. 写 BiNotifyRecord（成功：摘要含图表数/耗时；失败：错误信息）
4. 更新 `last_run_at` / `last_status` / `next_run_at`
5. 单订阅超时 30s（`asyncio.wait_for`），失败不阻塞其他订阅

### 5. 站内消息前端

- 顶部导航栏铃铛图标 + 未读计数 badge
- 每 30s 轮询 `/business/bi/notify/unread-count`
- 点击铃铛弹出下拉列表（最近 10 条）
- 点击消息跳转订阅详情页
- 消息标记已读：PUT `/business/bi/notify/{id}/read`

### 6. 行级隔离

BiSubscription / BiNotifyRecord 均用 `tenant_id` 字段存 `user.id`（与 BiChart 一致）。用户只能看自己的订阅和消息。管理员（R_BI_ADMIN, data_scope=all）可看所有。

### 7. 错误码

```
4130 BI_SUBSCRIPTION_NOT_FOUND    订阅不存在
4131 BI_NOTIFY_RECORD_NOT_FOUND   消息记录不存在
4132 BI_SUBSCRIPTION_CRON_INVALID cron 表达式非法
4133 BI_SUBSCRIPTION_DASHBOARD_NOT_FOUND 订阅的仪表盘不存在
```

## 数据模型影响

### 新增迁移 `0006_add_bi_subscription.py`

```python
# BiSubscription 表
CREATE TABLE biz_bi_subscription (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    dashboard_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    cron_expr VARCHAR(100) NOT NULL,
    next_run_at TIMESTAMPTZ NOT NULL,
    last_run_at TIMESTAMPTZ,
    last_status VARCHAR(20),
    status_type VARCHAR(10) DEFAULT 'enable',
    tenant_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    created_by VARCHAR(50),
    updated_by VARCHAR(50),
    is_deleted BOOLEAN DEFAULT FALSE
)

# BiNotifyRecord 表
CREATE TABLE biz_bi_notify_record (
    id INTEGER PRIMARY KEY,
    subscription_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    title VARCHAR(200) NOT NULL,
    content VARCHAR(2000),
    status VARCHAR(20) NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    tenant_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    created_by VARCHAR(50),
    updated_by VARCHAR(50),
    is_deleted BOOLEAN DEFAULT FALSE
)
```

## API 设计

### BiSubscription（6 路由，用户级）

| Method | Path | Name | Button |
|---|---|---|---|
| POST | `/subscriptions/search` | `bi.subscription.list` | `B_BI_SUBSCRIPTION_VIEW` |
| GET | `/subscriptions/{id}` | `bi.subscription.get` | `B_BI_SUBSCRIPTION_VIEW` |
| POST | `/subscriptions` | `bi.subscription.create` | `B_BI_SUBSCRIPTION_CREATE` |
| PUT | `/subscriptions/{id}` | `bi.subscription.update` | `B_BI_SUBSCRIPTION_EDIT` |
| DELETE | `/subscriptions/{id}` | `bi.subscription.delete` | `B_BI_SUBSCRIPTION_DELETE` |
| DELETE | `/subscriptions/batch_delete` | `bi.subscription.batch_delete` | `B_BI_SUBSCRIPTION_DELETE` |

行级隔离：`tenant_id = user.id`，用户只看自己的订阅。

### BiNotifyRecord（3 路由，只读 + 标记已读）

| Method | Path | Name | Button |
|---|---|---|---|
| POST | `/notify/search` | `bi.notify.list` | `B_BI_NOTIFY_VIEW` |
| GET | `/notify/{id}` | `bi.notify.get` | `B_BI_NOTIFY_VIEW` |
| GET | `/notify/unread-count` | `bi.notify.unread_count` | `B_BI_NOTIFY_VIEW` |
| PUT | `/notify/{id}/read` | `bi.notify.mark_read` | `B_BI_NOTIFY_VIEW` |

行级隔离：`user_id = user.id`，用户只看自己的消息。

### 服务函数

- `dispatch_subscriptions() -> None`：PeriodicTask handler，扫描到期订阅并执行
- `execute_subscription(sub: BiSubscription) -> None`：执行单个订阅刷新 + 写消息
- `validate_cron_expr(expr: str) -> datetime`：校验 cron 表达式，返回下次触发时间

## 前端设计

### 页面

- `web/src/views/bi/subscriptions/index.vue` — 订阅列表（表格 + 搜索 + 增改模态框）
- `web/src/views/bi/subscriptions/modules/subscription-operate-modal.vue` — 增改模态框（含 cron 表达式输入 + 仪表盘选择 + 预设档位快捷按钮）
- `web/src/views/bi/notify-records/index.vue` — 消息记录列表（只读 + 标记已读）

### 铃铛组件

- `web/src/layouts/base/widgets/notify-bell.vue` — 顶部导航栏铃铛（轮询未读数 + 下拉列表）
- 在 `web/src/layouts/base/index.vue` 导航栏右侧挂载

### 路由

由 elegant-router 自动生成：
- `bi_subscriptions` → `/bi/subscriptions`
- `bi_notify-records` → `/bi/notify-records`

### i18n

追加 `page.bi.subscription.*` 和 `page.bi.notify.*` 命名空间，中英双语。

## 安全考量

1. **行级隔离**：订阅和消息均按 `user_id` 隔离，用户只能看自己的
2. **cron 注入**：`croniter` 解析失败抛异常，不让非法 cron 入库
3. **handler 超时**：单订阅刷新 30s 超时，失败不阻塞其他订阅
4. **leader_only**：PeriodicTask 只在 leader worker 执行，避免多 worker 重复触发
5. **消息清理**：BiNotifyRecord 保留 30 天，超期自动软删（复用 cleanup 机制或新增 PeriodicTask）

## 测试策略

- **后端**：模型/服务/API 三层测试
  - `tests/test_bi_subscription.py`：CRUD + cron 校验 + dispatch_subscriptions + execute_subscription
  - `tests/test_bi_notify.py`：消息记录查询 + 标记已读
- **前端**：service API mock 测试

## 验收标准

1. `just check` 全绿
2. 用户可在 UI 创建仪表盘订阅（选仪表盘 + cron 表达式）
3. 到期自动刷新仪表盘并写站内消息
4. 顶部铃铛显示未读数，点击查看消息
5. 消息可标记已读
6. 订阅可暂停（disable）/删除

## 依赖文件

### 后端新建
- `app/business/bi/models.py`（修改：追加 BiSubscription / BiNotifyRecord）
- `app/business/bi/schemas.py`（修改：追加 schemas）
- `app/business/bi/controllers.py`（修改：追加 controllers）
- `app/business/bi/services_subscription.py`（新建：dispatch + execute + cron 校验）
- `app/business/bi/api/subscription.py`（新建：6 路由）
- `app/business/bi/api/notify.py`（新建：4 路由）
- `app/business/bi/api/__init__.py`（修改：挂载路由）
- `app/business/bi/module.py`（修改：注册 PeriodicTask）
- `app/business/bi/init_data.py`（修改：菜单 + 按钮 + 角色权限）
- `app/business/bi/config.py`（修改：订阅超时配置）
- `app/core/code.py`（修改：新增 4130-4133 错误码）
- `migrations/app_system/0006_add_bi_subscription.py`（新建）
- `pyproject.toml`（修改：追加 croniter 依赖）

### 前端新建
- `web/src/service/api/bi-subscription.ts`
- `web/src/service/api/bi-notify.ts`
- `web/src/views/bi/subscriptions/index.vue`
- `web/src/views/bi/subscriptions/modules/subscription-operate-modal.vue`
- `web/src/views/bi/notify-records/index.vue`
- `web/src/layouts/base/widgets/notify-bell.vue`
- `web/src/layouts/base/index.vue`（修改：挂载铃铛）
- `web/src/typings/api/bi.d.ts`（修改：追加类型）
- i18n 文件（修改）
