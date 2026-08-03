# BI 异步大查询（BiQueryTask）— Spec 文档

> **批次**：差异化第一梯队 · 批次 B
> **前置依赖**：无（与批次 A 图表保存并行，结果可被批次 A 的 BiChart 复用）
> **文档版本**：v1.0 · 2026-08-03

---

## 1. 背景与目标

### 1.1 现状问题

当前 BI 模块的 SQL 执行链路（[app/business/bi/sandbox/executor.py](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/app/business/bi/sandbox/executor.py)）完全基于同步 `asyncio.wait_for`：

- **硬超时 30s**：超过即报错 4104，用户必须把大查询拆碎或换工具
- **行数上限 1 万行**：超过即报错 4103，无法支持百万行级导出
- **请求阻塞**：长查询期间 HTTP 连接占用，前端不能取消、不能看进度
- **熔断进程内**：[sandbox/quota.py](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/app/business/bi/sandbox/quota.py) 用进程内字典，多 worker（Granian）下熔断失效
- **无任务队列框架**：项目未引入 Celery/ARQ/Temporal，缺少跨请求长生命周期任务的支持

### 1.2 目标

把"超长 + 大数据量"查询从同步阻塞变为**可观测、可取消、可恢复的异步任务**：

1. **超长查询**：支持分钟级（默认 10 分钟）SQL 执行，前端实时看进度
2. **大数据量导出**：支持百万行结果流式 CSV 下载，不爆内存
3. **智能切换**：用户照常点"运行"，后端自动判断——小查询同步秒回，大查询软超时自动转异步，用户无感
4. **可取消**：任意时刻可取消正在运行的任务，立即释放连接
5. **任务历史**：所有异步任务持久化记录，可回查 SQL/结果/耗时

### 1.3 非目标（本批次不做）

- 完全替换同步 SQL 执行（智能切换保持同步优先，避免破坏对话 SSE 流水线）
- 按角色/数据源差异化配额（接入 `BiQuotaConfig` 模型留待后续，本期用环境变量配置）
- 任务调度的高级语义（重试/死信/优先级/定时调度——本期只做 FIFO 简单队列）
- WebSocket 实时推送（本期纯轮询，复用现有 SSE 封装但不新建 WS 基础设施）

---

## 2. 用户场景

### 场景 1：智能切换（核心体验）

> 张三在 SQL 工作台跑一条 3 表 JOIN 的分析 SQL。点击"运行"，前端开始转圈。25 秒后查询还没返回，前端 UI 自动切换为"任务进行中"，显示进度条和"已扫描 X 行"。1 分 20 秒后查询完成，前端显示结果预览（1 万行）和"下载完整 CSV（共 12 万行）"按钮。

### 场景 2：手动提交大导出

> 李四要导出本季度所有订单。他在 SQL 工作台写好 SQL，点"运行"旁的下拉，选"异步运行（大查询）"。系统立即返回任务 ID，他切到"查询任务"页面看进度。完成后下载 CSV，用 Excel 打开看。

### 场景 3：取消长任务

> 王五提交了一个跑了 3 分钟还没完的任务，怀疑 SQL 写错了。他在任务详情页点"取消"，系统立即中断执行，释放数据库连接，任务标记为 `cancelled`。

### 场景 4：复用任务结果

> 赵六昨天跑了一个大查询，今天想基于结果做图表。他打开"查询任务"列表，找到昨天的任务，点"保存为图表"，复用批次 A 的 `BiChart` 组件把结果（取预览的前 1 万行）存为图表。

### 场景 5：多 worker 负载均衡

> 部署环境开了 4 个 granian worker。3 个用户同时提交异步查询，每个任务被 3 个 worker 中的某 1 个抢到执行（Redis BLPOP 原子性），剩余 1 个 worker 处理常规请求不受影响。

---

## 3. 架构设计

### 3.1 整体架构

```
┌─────────────┐     POST /sql/run         ┌──────────────┐
│  前端 UI     │ ─────────────────────────▶│ sql_workbench│
│ (轮询/进度)  │                            │    api       │
└─────┬───────┘                            └──────┬───────┘
      ▲                                           │ 同步执行
      │ GET /tasks/{id}                           ▼
      │ (轮询)                          ┌──────────────────┐
      │                                 │  services.run_sql│
      │                                 └────┬─────────────┘
      │                                      │ asyncio.wait_for
      │                                      │ 软超时 25s 触发
      │                                      ▼
      │                                 ┌──────────────────┐
      │                                 │ services_async   │ transfer
      │                                 │  _query.submit   │ ──────▶ task_id
      │                                 └────┬─────────────┘
      │                                      │ LPUSH
      │                                      ▼
      │                                 ┌──────────────────┐
      │                                 │ Redis List       │
      │                                 │ bi:async_query   │
      │                                 │   :queue         │
      │                                 └──────────────────┘
      │                                      ▲ BLPOP
      │                                      │
      │                                 ┌────┴─────────────┐
      │                                 │ async_query      │
      │                                 │   runner worker  │ (每个 granian worker 1 个协程)
      │                                 └────┬─────────────┘
      │                                      │
      │                                      ▼
      │                                 ┌──────────────────┐
      │                                 │ sandbox.executor │ (复用)
      │                                 │  + fetchmany 流式│
      │                                 └────┬─────────────┘
      │                                      │
      └──────────────────────────────────────┘
                                  写结果：JSON 预览 + CSV 落盘
                                  更状态：Redis Hash + DB BiQueryTask
```

### 3.2 核心组件

新建 `app/business/bi/async_query/` 子包：

| 模块 | 职责 |
|---|---|
| `__init__.py` | 暴露对外接口 |
| `queue.py` | Redis List 队列：`enqueue(task_id)` / `dequeue()` (BLPOP) |
| `runner.py` | worker 协程：拉任务 → 执行 → 写结果 → 更状态 |
| `state.py` | 状态机：`update_progress(task_id, pct, rows)` / `update_status` / `get_state` / `check_cancel` |
| `storage.py` | 结果存储：`write_preview` (JSON) / `write_csv` (流式) / `read_csv_stream` |
| `quota.py` | Redis 共享配额：替换 `sandbox/quota.py` 的进程内字典 |

新增/修改：

| 文件 | 责任 |
|---|---|
| `app/business/bi/models.py` | 新增 `BiQueryTask` 模型 |
| `app/business/bi/schemas.py` | 新增 `BiQueryTask*` Schema |
| `app/business/bi/controllers.py` | 新增 `bi_query_task_controller` |
| `app/business/bi/services_async_query.py` | 业务编排：submit/get/cancel/list/delete |
| `app/business/bi/api/async_query.py` | API 路由 |
| `app/business/bi/api/sql_workbench.py` | 改造 `/sql/run` 加软超时智能切换 |
| `app/business/bi/services.py` | 改造 `run_sql` 支持 transfer |
| `app/business/bi/sandbox/quota.py` | 改造为 Redis 共享熔断 |
| `app/business/bi/config.py` | 新增 `BI_ASYNC_QUERY_*` 配置 |
| `app/business/bi/module.py` | 启动 worker 协程 + 注册新路由 + 限流 |
| `app/business/bi/init_data.py` | 新增菜单 + 5 个按钮码 + 角色权限 |
| `app/core/code.py` | 新增 4110-4119 错误码段 |
| `app/__init__.py` | 启动时拉起 async_query worker 协程 |
| `tests/conftest.py` | 注册新模型 |
| `tests/test_bi_async_query.py` | 测试用例 |

前端：

| 文件 | 责任 |
|---|---|
| `web/src/views/bi/async-query-tasks/index.vue` | 任务列表页 |
| `web/src/views/bi/async-query-tasks/detail.vue` | 任务详情页（进度/结果/下载/保存为图表） |
| `web/src/views/bi/sql-workbench/index.vue` | 加软超时 UI 切换 + "异步运行"下拉按钮 |
| `web/src/service/api/bi-async-query.ts` | API 层 |
| `web/src/typings/api/bi.d.ts` | 新增 BiQueryTask 类型 |
| `web/src/locales/langs/_generated/bi/zh-cn.ts` | i18n |
| `web/src/locales/langs/_generated/bi/en-us.ts` | i18n |
| `web/src/locales/langs/_generated/bi/types.d.ts` | i18n 类型 |

### 3.3 任务状态机

```
                        ┌──────────────┐
        submit          │   pending    │
       ──────────────▶  │              │
                        └──────┬───────┘
                               │ runner BLPOP 拿到
                               ▼
                        ┌──────────────┐
                        │   running    │  ◀── progress 0-100
                        │              │      rows_fetched 累计
                        └──┬─────┬─────┘
                           │     │
              用户取消     │     │ 执行完成
                           │     │
                           ▼     ▼
                  ┌──────────┐  ┌──────────┐
                  │cancelled │  │ success  │
                  └──────────┘  └──────────┘
                               ┌──────────┐
                  执行失败/超时 │ failed   │
                               └──────────┘
```

状态来源：Redis Hash（实时）→ 完成后同步到 DB `BiQueryTask`（持久化）。

### 3.4 Redis 键设计

| 键 | 类型 | TTL | 用途 |
|---|---|---|---|
| `bi:async_query:queue` | List | 持久 | 就绪队列，元素为 task_id |
| `bi:async_query:task:{id}` | Hash | 7 天 | 实时状态：status/progress/rows_fetched/elapsed_ms/error_message |
| `bi:async_query:task:{id}:cancel` | String | 1 小时 | 取消标志（值为 1） |
| `bi:async_query:user:{uid}:running` | 计数器 | 1 小时 | 用户进行中任务数（INCR/DECR） |
| `bi:async_query:global:running` | 计数器 | 1 小时 | 全局进行中任务数 |
| `bi:quota:failures:{scope}` | ZSet | 1 小时 | 熔断失败记录（score=时间戳，member=时间戳） |

---

## 4. 数据模型

### 4.1 BiQueryTask

```python
class BiQueryTask(BaseModel, AuditMixin, SoftDeleteMixin):
    """异步查询任务。

    记录一次异步 SQL 执行的完整生命周期：提交 → 运行 → 完成/失败/取消。
    小结果（≤ BI_ASYNC_QUERY_PREVIEW_ROWS）直接存 ``result_snapshot`` JSONField；
    大结果落 CSV 到 ``BI_ASYNC_QUERY_CSV_DIR``，``result_uri`` 存相对路径。
    """

    id = fields.IntField(primary_key=True, description="主键ID")
    name: str = fields.CharField(max_length=100, null=True, blank=True, description="任务名称（可选，默认自动生成）")
    datasource_id: int
    datasource: fields.ForeignKeyRelation[BiDatasource] = fields.ForeignKeyField(
        "app_system.BiDatasource",
        related_name="query_tasks",
        on_delete=fields.CASCADE,
        description="所属数据源",
    )
    sql_text: str = fields.TextField(description="来源 SQL（提交时已过白名单校验）")
    # 实时状态在 Redis Hash，这里存最终快照（runner 完成时回写）
    status: str = fields.CharField(max_length=20, default="pending", description="任务状态：pending/running/success/failed/cancelled")
    progress: int = fields.IntField(default=0, description="进度百分比 0-100")
    rows_fetched: int = fields.IntField(default=0, description="已扫描行数")
    elapsed_ms: int = fields.IntField(default=0, description="执行耗时（毫秒）")
    # 结果存储
    result_snapshot: dict | None = fields.JSONField(null=True, description="结果预览（≤1万行，结构 {columns, rows, rowCount, elapsedMs, isTruncated}）")
    result_uri: str | None = fields.CharField(max_length=255, null=True, description="CSV 文件相对路径（大结果时）")
    result_row_count: int = fields.IntField(default=0, description="结果总行数")
    result_is_truncated: bool = fields.BooleanField(default=False, description="结果是否被截断（仅预览截断，CSV 完整）")
    # 错误
    error_message: str | None = fields.TextField(null=True, description="失败/取消原因")
    # 时间
    started_at: datetime | None = fields.DatetimeField(null=True, description="开始执行时间")
    finished_at: datetime | None = fields.DatetimeField(null=True, description="完成/失败/取消时间")
    # 行级隔离
    tenant_id: int = fields.IntField(default=0, description="租户ID（行级 data_scope 作用域，存 user.id）")
    # 来源
    source: str = fields.CharField(max_length=20, default="manual", description="提交来源：manual（手动）/ auto_transfer（同步软超时转异步）")

    class Meta:
        table = "biz_bi_query_task"
        manager = SoftDeleteManager()
        indexes = [
            ("tenant_id", "status"),
            ("tenant_id", "created_at"),
        ]
```

---

## 5. 核心流程

### 5.1 智能切换（/sql/run 改造）

```
POST /sql/run
  │
  ▼
services.run_sql(sql, datasource_id, user_id)
  │
  ▼
asyncio.wait_for(execute_sql(...), timeout=BI_SYNC_SOFT_TIMEOUT=25)
  │
  ├─ 成功（25s 内返回）──▶ 正常返回结果（现有行为不变）
  │
  └─ TimeoutError ──▶ transfer_to_async:
                        │
                        ├─ 1. 提交 BiQueryTask (source=auto_transfer)
                        ├─ 2. enqueue(task_id) 到 Redis 队列
                        └─ 3. 返回 {transferred: true, taskId, message: "查询超时，已转为异步任务"}
```

前端收到 `transferred=true`：UI 切换为"任务进行中"模式，开始轮询 `GET /tasks/{taskId}`。

### 5.2 手动提交（/sql/async-run）

```
POST /sql/async-run {sql, datasource_id, name?}
  │
  ▼
services_async_query.submit:
  ├─ 1. check_quota(user_id) —— 用户/全局并发上限
  ├─ 2. validate_sql(sql, dialect) —— 白名单（复用 sandbox/whitelist）
  ├─ 3. inject_tenant_filter(sql, tenant_id) —— 行级权限（复用 sandbox/tenant）
  ├─ 4. 创建 BiQueryTask(status=pending)
  ├─ 5. Redis INCR bi:async_query:user:{uid}:running / global:running
  ├─ 6. enqueue(task_id)
  ├─ 7. radar_log + BiAuditLog
  └─ 8. 返回 {taskId, status: "pending"}
```

### 5.3 Worker 执行循环

```python
async def worker_loop(redis, app):
    while not shutdown_event.is_set():
        # BLPOP 阻塞拉取，超时 5s 退出检查 shutdown
        result = await redis.blpop("bi:async_query:queue", timeout=5)
        if not result:
            continue
        task_id = int(result[1])
        try:
            await execute_task(task_id, app)
        except Exception as e:
            log.exception("async_query worker error task_id={}", task_id)
            await state.mark_failed(task_id, str(e))
```

`execute_task` 流程：

```
1. 加载 BiQueryTask
2. 更状态 running + started_at + Redis INCR running 计数
3. test_connection(datasource) —— 不可用直接 mark_failed
4. validate_sql + inject_tenant_filter（二次校验，防止数据被篡改）
5. get_engine(datasource) + conn.execute(text(sql), stream=True)
6. 流式 fetchmany(batch=1000):
   - 每批次:
     ├─ 检查 cancel 标志 → 命中则中断 + mark_cancelled + 清理半成品 CSV
     ├─ 累计 rows_fetched
     ├─ 写 CSV（流式追加）
     ├─ 前 1 万行追加到 preview_rows
     ├─ 更新 Redis Hash: progress/rows_fetched/elapsed_ms
     └─ 检查超时（累计耗时 > BI_ASYNC_QUERY_TIMEOUT）→ mark_failed(timeout)
7. 完成:
   ├─ 写 result_snapshot (preview_rows + columns)
   ├─ 写 result_uri (CSV 相对路径)
   ├─ 更状态 success + finished_at + result_row_count
   └─ Redis DECR running 计数
```

### 5.4 取消

```
POST /tasks/{id}/cancel
  │
  ▼
services_async_query.cancel:
  ├─ 1. 加载 BiQueryTask，校验归属当前用户
  ├─ 2. 校验 status in (pending, running)
  ├─ 3. Redis SET bi:async_query:task:{id}:cancel = 1
  └─ 4. 如果 status=pending（还没被 worker 拿到）→ 直接 mark_cancelled + DECR running
       如果 status=running → 等待 worker 在下一批次检测到（最多 1 秒）
```

### 5.5 下载

```
GET /tasks/{id}/download
  │
  ▼
services_async_query.get_download_stream:
  ├─ 1. 加载 BiQueryTask，校验归属 + status=success + result_uri 存在
  ├─ 2. 拼接绝对路径 BI_ASYNC_QUERY_CSV_DIR / result_uri
  ├─ 3. 校验文件存在（不存在 → 4115）
  └─ 4. 返回 StreamingResponse(FileIter(file), media_type="text/csv", headers={
         "Content-Disposition": f'attachment; filename="{task_id}.csv"',
         "Content-Length": str(size),
       })
```

支持 `Range` 请求头（断点续传）：解析 `Range: bytes=start-end`，seek 后返回 206。

---

## 6. 配额与熔断

### 6.1 配额检查（提交时）

```python
async def check_concurrency(user_id: int, redis) -> None:
    user_running = await redis.get(f"bi:async_query:user:{user_id}:running") or 0
    if int(user_running) >= BI_ASYNC_QUERY_USER_MAX_CONCURRENCY:  # 默认 2
        raise BizError(Code.BI_ASYNC_QUERY_USER_CONCURRENCY_EXCEEDED)
    global_running = await redis.get("bi:async_query:global:running") or 0
    if int(global_running) >= BI_ASYNC_QUERY_GLOBAL_MAX_CONCURRENCY:  # 默认 20
        raise BizError(Code.BI_ASYNC_QUERY_GLOBAL_CONCURRENCY_EXCEEDED)
```

### 6.2 熔断改造（sandbox/quota.py）

将 `_failure_records: dict[int, deque[float]]` 进程内字典替换为 Redis ZSet：

```python
async def record_failure(scope: str, redis):
    now = time.time()
    key = f"bi:quota:failures:{scope}"
    await redis.zadd(key, {str(now): now})
    await redis.expire(key, BI_QUERY_BREAKER_WINDOW_SECONDS)  # 60s
    # 清理过期
    await redis.zremrangebyscore(key, 0, now - BI_QUERY_BREAKER_WINDOW_SECONDS)

async def check_quota(scope: str, redis) -> None:
    key = f"bi:quota:failures:{scope}"
    now = time.time()
    count = await redis.zcount(key, now - BI_QUERY_BREAKER_WINDOW_SECONDS, now)
    if count >= BI_QUERY_BREAKER_THRESHOLD:  # 10
        raise BizError(Code.BI_QUERY_BREAKER_OPEN)
```

`scope` 为 `user:{user_id}` 或 `datasource:{datasource_id}`（两套独立计数，命中任一即熔断）。

同步 `/sql/run` 和异步查询共用同一套熔断，多 worker 一致。

---

## 7. API 接口

### 7.1 接口列表

| 方法 | 路径 | name | 按钮码 | 说明 |
|---|---|---|---|---|
| POST | `/sql/async-run` | `bi.sql.async_run` | `B_BI_SQL_ASYNC_RUN` | 手动提交异步查询 |
| GET | `/sql/tasks/{task_id}` | `bi.sql.tasks.get` | `B_BI_SQL_TASK_VIEW` | 查状态 + 进度（轮询用，2s 间隔） |
| POST | `/sql/tasks/search` | `bi.sql.tasks.list` | `B_BI_SQL_TASK_VIEW` | 分页查任务列表 |
| POST | `/sql/tasks/{task_id}/cancel` | `bi.sql.tasks.cancel` | `B_BI_SQL_TASK_CANCEL` | 取消任务 |
| DELETE | `/sql/tasks/{task_id}` | `bi.sql.tasks.delete` | `B_BI_SQL_TASK_DELETE` | 删除任务（含 CSV 文件） |
| GET | `/sql/tasks/{task_id}/result` | `bi.sql.tasks.result` | `B_BI_SQL_TASK_VIEW` | 获取结果预览（JSON） |
| GET | `/sql/tasks/{task_id}/download` | `bi.sql.tasks.download` | `B_BI_SQL_TASK_DOWNLOAD` | 流式下载 CSV |
| (改造) | `/sql/run` | `bi.sql.run` | (现有) | 加软超时智能切换，返回体可能多 `transferred`/`taskId` 字段 |

### 7.2 响应结构

任务状态响应（轮询用）：

```json
{
  "code": "0000",
  "data": {
    "taskId": "abc123",
    "name": "本月销售分析",
    "status": "running",
    "progress": 45,
    "rowsFetched": 45000,
    "elapsedMs": 32000,
    "startedAt": "2026-08-03T10:00:00Z",
    "source": "auto_transfer",
    "isTruncated": false
  }
}
```

任务完成响应：

```json
{
  "code": "0000",
  "data": {
    "taskId": "abc123",
    "status": "success",
    "progress": 100,
    "rowsFetched": 120000,
    "elapsedMs": 80000,
    "resultRowCount": 120000,
    "resultIsTruncated": false,
    "resultPreview": {
      "columns": ["order_id", "amount", ...],
      "rows": [...],
      "rowCount": 10000,
      "elapsedMs": 80000,
      "isTruncated": true
    },
    "resultDownloadUrl": "/api/v1/business/bi/sql/tasks/abc123/download",
    "finishedAt": "2026-08-03T10:01:20Z"
  }
}
```

智能切换响应（`/sql/run` 软超时触发）：

```json
{
  "code": "0000",
  "data": {
    "transferred": true,
    "taskId": "abc123",
    "message": "查询超时，已转为异步任务",
    "datasourceId": "...",
    "sqlText": "..."
  }
}
```

---

## 8. 配置项

新增到 `app/business/bi/config.py` 的 `BusinessSettings`，同步到 `.env.example`：

```python
# 异步大查询总开关
BI_ASYNC_QUERY_ENABLED: bool = True

# 异步查询行数上限（远大于同步的 1 万）
BI_ASYNC_QUERY_MAX_ROWS: int = 1_000_000

# 异步查询超时上限（秒，10 分钟）
BI_ASYNC_QUERY_TIMEOUT: int = 600

# 每用户最大并发异步任务数
BI_ASYNC_QUERY_USER_MAX_CONCURRENCY: int = 2

# 全局最大并发异步任务数
BI_ASYNC_QUERY_GLOBAL_MAX_CONCURRENCY: int = 20

# 结果预览行数（JSON 存储上限）
BI_ASYNC_QUERY_PREVIEW_ROWS: int = 10_000

# 任务记录保留天数（过期由清理任务软删）
BI_ASYNC_QUERY_TTL_DAYS: int = 7

# 同步查询软超时（秒，比硬超时 30s 早 5s 触发转异步）
BI_SYNC_SOFT_TIMEOUT: int = 25

# CSV 落盘目录（相对项目根）
BI_ASYNC_QUERY_CSV_DIR: str = "data/async_query"

# runner BLPOP 超时（秒，控制 shutdown 检查频率）
BI_ASYNC_QUEUE_BLPOP_TIMEOUT: int = 5
```

---

## 9. 错误码

在 `app/core/code.py` 的 BI 段（4xxx）追加 4110-4119：

```python
bi_async_query_not_enabled = 4110, "异步大查询功能未开启"
bi_async_query_user_concurrency_exceeded = 4111, "用户并发任务数超限"
bi_async_query_global_concurrency_exceeded = 4112, "全局并发任务数超限"
bi_async_query_task_not_found = 4113, "任务不存在"
bi_async_query_task_not_cancellable = 4114, "任务当前状态不可取消"
bi_async_query_result_file_missing = 4115, "结果文件不存在或已清理"
bi_async_query_transfer_failed = 4116, "同步转异步失败"
bi_async_query_csv_write_failed = 4117, "CSV 写入失败"
bi_async_query_task_timeout = 4118, "异步查询执行超时"
bi_async_query_cancelled = 4119, "任务已取消"
```

---

## 10. 菜单与按钮码

### 10.1 菜单（init_data.py）

在 `BI_MENU_CHILDREN` 中"图表库"之后追加：

```python
{
    "menu_name": "查询任务",
    "route_name": "bi_async-query-tasks",
    "route_path": "/bi/async-query-tasks",
    "component": "view.bi_async-query-tasks",
    "icon": "mdi:cloud-download-outline",
    "order": 6,
    "buttons": [
        {"button_code": "B_BI_SQL_ASYNC_RUN", "button_desc": "提交异步查询"},
        {"button_code": "B_BI_SQL_TASK_VIEW", "button_desc": "查看任务"},
        {"button_code": "B_BI_SQL_TASK_CANCEL", "button_desc": "取消任务"},
        {"button_code": "B_BI_SQL_TASK_DELETE", "button_desc": "删除任务"},
        {"button_code": "B_BI_SQL_TASK_DOWNLOAD", "button_desc": "下载结果"},
    ],
},
{
    "menu_name": "任务详情",
    "route_name": "bi_async-query-detail",
    "route_path": "/bi/async-query-tasks/:id",
    "component": "view.bi_async-query-detail",
    "icon": "mdi:chart-line",
    "order": 99,
    "hide_in_menu": True,
    "active_menu": "bi_async-query-tasks",
},
```

### 10.2 角色权限（R_BI_ANALYST）

追加按钮码：

```python
"B_BI_SQL_ASYNC_RUN",
"B_BI_SQL_TASK_VIEW",
"B_BI_SQL_TASK_CANCEL",
"B_BI_SQL_TASK_DELETE",
"B_BI_SQL_TASK_DOWNLOAD",
```

追加 API name：

```python
"bi.sql.async_run",
"bi.sql.tasks.get",
"bi.sql.tasks.list",
"bi.sql.tasks.cancel",
"bi.sql.tasks.delete",
"bi.sql.tasks.result",
"bi.sql.tasks.download",
```

---

## 11. 限流配置

`app/business/bi/module.py` 的 `ENDPOINT_RATE_LIMITS` 追加：

```python
"/api/v1/business/bi/sql/async-run": (10, 60),       # 60s 最多 10 次提交
"/api/v1/business/bi/sql/tasks/search": (60, 60),    # 60s 最多 60 次列表
"/api/v1/business/bi/sql/tasks/{task_id}": (120, 60),  # 轮询放宽
```

注：fastapi-guard 的路径匹配是前缀匹配，`/tasks/{task_id}` 这条会覆盖 get/cancel/delete/result/download。

---

## 12. 前端设计

### 12.1 SQL Workbench 改造

- "运行"按钮不变，点击后前端等待响应：
  - 收到正常结果 → 现有行为不变
  - 收到 `transferred=true` → UI 切换"任务进行中"模式：
    - 隐藏结果区
    - 显示进度卡片：任务名 + 进度条 + "已扫描 X 行 / 已耗时 Y 秒" + "取消"按钮
    - 启动 2s 间隔轮询 `GET /tasks/{taskId}`
    - 任务完成 → 进度卡片变结果展示（预览 + 下载按钮）
    - 任务失败/取消 → 显示错误 + "重新运行"按钮
- "运行"按钮旁加下拉："异步运行（大查询）"——直接走 `/sql/async-run`，不等待同步阶段

### 12.2 查询任务列表页

- 表格：任务名 / 数据源 / 状态（带颜色标签）/ 进度 / 行数 / 耗时 / 创建时间 / 操作
- 状态筛选：全部 / 进行中 / 已完成 / 失败 / 已取消
- 操作：查看详情 / 取消（进行中）/ 下载（成功）/ 删除
- 分页 + 按名称搜索

### 12.3 任务详情页

- 顶部：任务名 + 状态 + 进度条（进行中实时刷新）
- 中部：结果预览表格（前 1 万行，带"已截断，完整数据请下载"提示）
- 底部：SQL 折叠展示 + 元信息（数据源/耗时/行数/来源）
- 操作：下载 CSV / 保存为图表（复用批次 A 的 save-chart-modal）/ 取消 / 删除 / 重新运行

### 12.4 轮询策略

```typescript
// 自适应轮询：进行中 2s，已完成/失败/取消停止
async function pollTask(taskId: string) {
  while (true) {
    const data = await fetchTaskStatus(taskId);
    updateUI(data);
    if (['success', 'failed', 'cancelled'].includes(data.status)) return;
    await sleep(2000);
  }
}
```

页面离开（onUnmounted）时停止轮询。

---

## 13. 边界与约束

### 13.1 安全

- 所有接口走 `DependPermission` + `require_buttons`
- 任务列表/详情严格按 `tenant_id`（user.id）隔离，用户只能看自己的任务
- SQL 提交时强制走 `validate_sql` 白名单 + `inject_tenant_filter` 行级注入
- 下载接口校验任务归属 + 文件路径不能逃逸 `BI_ASYNC_QUERY_CSV_DIR`（防目录穿越）

### 13.2 资源

- CSV 文件按 task_id 命名，删除任务时同步删除文件
- 过期任务（超过 `BI_ASYNC_QUERY_TTL_DAYS`）由清理任务软删 + CSV 文件物理删除（清理任务可作为 `PeriodicTask` 注册到 `module.py`，daily 跑一次）
- worker 协程随 granian worker 生命周期，shutdown 时通过 `shutdown_event` 优雅退出（等待当前批次完成）
- 流式 fetchmany batch=1000，避免一次性加载百万行到内存

### 13.3 多 worker

- BLPOP 天然负载均衡，每个 task 只被一个 worker 拿到
- 任务状态写 Redis Hash，任一 worker 都能查
- running 计数用 Redis INCR/DECR，多 worker 一致
- 熔断改 Redis ZSet 后多 worker 共享

### 13.4 一致性

- runner 完成时先写 CSV 文件 → 再写 DB `result_uri` → 再更状态 success（顺序防止 DB 有记录但文件不存在）
- 取消时先设 cancel 标志 → worker 检测到后清理半成品 CSV → 更状态 cancelled
- 异常退出（worker crash）：任务可能卡在 running，由超时机制兜底（`BI_ASYNC_QUERY_TIMEOUT` 累计超时 mark_failed）；启动时扫描 status=running 但 created_at 超过 timeout 的任务，标记为 failed（crash recovery）

### 13.5 与现有功能的关系

- **不破坏同步 `/sql/run`**：软超时只是新增一个 transfer 分支，成功路径完全不变
- **不破坏对话 SSE**：对话内的 SQL 执行仍走同步（`bi_sse_response` 流水线），不接入异步任务
- **复用 BiChart**：异步任务结果可"保存为图表"，取 result_snapshot（前 1 万行）作为图表快照
- **复用 sandbox**：whitelist/tenant/executor/crypto 全部复用，不重写

---

## 14. 测试

### 14.1 单元测试

- `queue.py`：enqueue/dequeue、BLPOP 超时、并发 enqueue 顺序
- `state.py`：update_progress/get_state/check_cancel/mark_failed/mark_cancelled
- `storage.py`：write_preview 行数截断、write_csv 流式追加、read_csv_stream 分块
- `quota.py`（新）：Redis 熔断计数、多 worker 共享、窗口清理

### 14.2 集成测试

- 提交 → 轮询 → 完成 → 下载 全流程
- 提交 → 取消 → 状态 cancelled + 半成品 CSV 清理
- 提交 → 超时 → 状态 failed
- 智能切换：同步软超时触发 transfer，前端收到 taskId
- 任务列表分页 + 行级隔离（用户 A 看不到用户 B 的任务）
- 大结果（>1 万行）：JSON 预览截断 + CSV 完整 + result_is_truncated=true
- 下载 Range 请求（断点续传）

### 14.3 边界测试

- 用户并发达上限（2 个）→ 第 3 个提交报 4111
- 全局并发达上限（20 个）→ 第 21 个提交报 4112
- 取消 pending 任务（还没被 worker 拿到）→ 直接 cancelled
- 取消已完成的任务 → 报 4114
- 下载不存在的 task_id → 4113
- 下载 result_uri 丢失（手工删文件）→ 4115
- 路径穿越攻击（task_id 含 ../）→ 校验拒绝

### 14.4 多 worker 测试

- 启动 2 个 worker 协程，提交 4 个任务，验证每个任务只被执行一次
- worker A 拿到任务后 crash，worker B 不接管（任务靠超时兜底）

---

## 15. 手动验收清单

- [ ] SQL 工作台跑 25s+ 的查询，UI 自动切换为"任务进行中"，进度条实时更新
- [ ] SQL 工作台跑 5s 的查询，正常返回结果，不触发异步
- [ ] "异步运行"下拉直接提交任务，立即返回 taskId
- [ ] 任务详情页轮询进度，完成后显示结果预览（前 1 万行）
- [ ] 百万行结果下载 CSV，文件完整、可 Excel 打开
- [ ] 下载支持断点续传（用 curl `Range: bytes=0-99` 验证）
- [ ] 进行中任务点"取消"，1 秒内状态变 cancelled，半成品 CSV 被清理
- [ ] 用户 A 看不到用户 B 的任务（行级隔离）
- [ ] 用户已运行 2 个任务时，第 3 个提交报"用户并发超限"
- [ ] 数据源不可用时任务立即 failed，错误信息清晰
- [ ] 任务结果可"保存为图表"，复用批次 A 的 BiChart 组件
- [ ] 查询任务列表页分页/筛选/搜索正常
- [ ] 过期任务（>7 天）被清理任务软删 + CSV 物理删除
- [ ] 多 worker 部署下，任务在 worker 间负载均衡（不重复执行）

---

## 16. 风险与缓解

| 风险 | 缓解措施 |
|---|---|
| worker 协程随 granian worker 生命周期，worker 重启时进行中任务丢失 | 启动时 crash recovery：扫描 status=running 且 created_at 超时的任务标记 failed |
| BLPOP 在 shutdown 时阻塞 | BLPOP timeout=5s，循环检查 shutdown_event，最多 5s 优雅退出 |
| CSV 文件无限增长 | 清理任务 daily 软删过期任务 + 物理删除 CSV；CSV 目录按 task_id 命名便于核对 |
| 熔断改造影响现有同步查询 | 改造前后行为等价（同样阈值/窗口），只是计数从进程内换 Redis，现有测试应仍通过 |
| 软超时 25s 可能在快查边缘抖动 | 可配置 `BI_SYNC_SOFT_TIMEOUT`，默认 25s 留 5s 余量给硬超时 30s |
| 任务结果超大导致 DB JSONField 膨胀 | result_snapshot 严格限 1 万行；大结果只存 result_uri |
| 路径穿越攻击 | result_uri 校验只含 `[a-zA-Z0-9_-]+\.csv`，拼接前后做 realpath 校验不逃逸 CSV_DIR |

---

## 17. 后续迭代（不在本批次）

- 接入 `BiQuotaConfig` 模型，支持按角色/数据源差异化配额
- 任务重试/死信队列
- 任务优先级
- 定时调度（与批次 D 定时报表合并）
- WebSocket 实时推送（替代轮询，体验更好）
- 结果直接落对象存储（S3/MinIO）替代本地文件
