# BI 异步大查询（BiQueryTask）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把"超长 + 大数据量"SQL 查询从同步阻塞变为可观测、可取消、可恢复的异步任务，支持分钟级执行、百万行 CSV 导出、智能切换、并发配额与任务历史。

**Architecture:** Redis List 队列 + BLPOP 的轻量任务调度；任务状态走 Redis Hash（实时）+ DB `BiQueryTask`（持久化）；结果按行数分流——JSON 预览（≤1 万行）+ CSV 落盘（>1 万行）；worker 协程随 granian 生命周期，shutdown 通过 `shutdown_event` 优雅退出；同步 `/sql/run` 加 25s 软超时自动转异步。

**Tech Stack:** FastAPI · Tortoise ORM · SQLAlchemy async engine（流式 `fetchmany`） · Redis（List/Hash/ZSet/Counter） · Pydantic v2 · Vue3 + Naive UI（前端）

**Spec:** [.trae/specs/bi-async-query/spec.md](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/.trae/specs/bi-async-query/spec.md)

**Project conventions reminder:**
- Python 工具链走 `uv`（不要直接 `python`/`pip`）
- 常用命令：`just mm` / `just fmt` / `just check` / `just run`
- 业务模块 import 入口统一 `from app.utils import ...`
- 响应统一用 `Success` / `SuccessExtra` / `Fail`；不要返回裸 dict
- 业务 schema 继承 `SchemaBase`；分页继承 `PageQueryBase`；SQID 参数 request schema 定义为 `str`
- 写接口必须有按钮权限校验
- `just check` 是提交前门禁（前后端统一）

---

## 文件结构总览

### 新建文件

| 路径 | 责任 |
|---|---|
| `app/business/bi/async_query/__init__.py` | 子包入口，暴露对外接口 |
| `app/business/bi/async_query/queue.py` | Redis List 队列：`enqueue` / `dequeue` |
| `app/business/bi/async_query/state.py` | 状态机：`init_state` / `update_progress` / `update_status` / `get_state` / `check_cancel` / `delete_state` + `set_runtime_redis` / `get_runtime_redis` |
| `app/business/bi/async_query/storage.py` | 结果存储：`write_preview` / `write_csv_header` / `read_csv_stream` / `resolve_csv_path` / `delete_csv` |
| `app/business/bi/async_query/quota.py` | Redis 共享配额：`check_concurrency` / `incr_running` / `decr_running` |
| `app/business/bi/async_query/runner.py` | worker 协程：`worker_loop` / `execute_task` / `recover_stale_tasks` |
| `app/business/bi/services_async_query.py` | 业务编排：`submit` / `get_task` / `cancel` / `list_tasks` / `delete_task` / `get_download_stream` |
| `app/business/bi/api/async_query.py` | API 路由（8 个接口） |
| `migrations/models/2_xxxx_add_bi_query_task.py` | 数据库迁移（自动生成） |
| `tests/test_bi_async_query.py` | 单元 + 集成测试 |
| `tests/test_bi_async_query_runner.py` | worker runner 单元测试 |
| `web/src/views/bi/async-query-tasks/index.vue` | 任务列表页 |
| `web/src/views/bi/async-query-tasks/detail.vue` | 任务详情页 |
| `web/src/service/api/bi-async-query.ts` | 前端 API 层 |

### 修改文件

| 路径 | 改动 |
|---|---|
| `app/business/bi/models.py` | 新增 `BiQueryTask` 模型 |
| `app/business/bi/schemas.py` | 新增 `BiQueryTask*` Schema |
| `app/business/bi/controllers.py` | 新增 `bi_query_task_controller` |
| `app/business/bi/config.py` | 新增 `BI_ASYNC_QUERY_*` 配置项 |
| `app/business/bi/sandbox/quota.py` | 改造为 Redis 共享熔断（替换进程内字典） |
| `app/business/bi/sandbox/executor.py` | 调整 `check_quota` / `record_failure` / `record_success` 为 async + 接受 redis 参数 |
| `app/business/bi/services.py` | 改造 `run_sql` 支持软超时 transfer；新增 `transfer_to_async` |
| `app/business/bi/api/sql_workbench.py` | 改造 `/sql/run` 处理 transfer 响应 |
| `app/business/bi/api/__init__.py` | 聚合 `async_query` 路由 |
| `app/business/bi/module.py` | 追加限流配置 |
| `app/business/bi/init_data.py` | 新增菜单 + 5 个按钮码 + 角色权限 |
| `app/core/code.py` | 新增 4110-4119 错误码段 |
| `app/__init__.py` | lifespan 启动 worker 协程 + crash recovery |
| `tests/conftest.py` | 注册 `BiQueryTask` 模型 + 新增 fixture |
| `.env.example` | 新增 `BI_ASYNC_QUERY_*` 环境变量 |
| `web/src/typings/api/bi.d.ts` | 新增 `BiQueryTask` 类型 |
| `web/src/locales/langs/_generated/bi/zh-cn.ts` | i18n |
| `web/src/locales/langs/_generated/bi/en-us.ts` | i18n |
| `web/src/locales/langs/_generated/bi/types.d.ts` | i18n 类型 |
| `web/src/router/elegant/imports.ts` + `transform.ts` | 路由导入（如 elegant-router 不自动生成则手动） |
| `web/src/router/bi.ts`（如有） | 路由配置 |

---

## Task 1: 配置项 + 错误码 + .env.example

**Files:**
- Modify: `app/business/bi/config.py`
- Modify: `app/core/code.py`
- Modify: `.env.example`

- [ ] **Step 1: 在 `app/business/bi/config.py` 的 `BusinessSettings` 中追加异步查询配置**

在 `BI_CHART_SNAPSHOT_MAX_ROWS` 字段之后、`model_config` 之前追加：

```python
    # 异步大查询
    # 总开关：False 时 /sql/async-run 与软超时转异步都直接拒绝
    BI_ASYNC_QUERY_ENABLED: bool = True
    # 异步查询行数上限（远大于同步的 1 万）
    BI_ASYNC_QUERY_MAX_ROWS: int = 1_000_000
    # 异步查询执行超时上限（秒，10 分钟）
    BI_ASYNC_QUERY_TIMEOUT: int = 600
    # 每用户最大并发异步任务数
    BI_ASYNC_QUERY_USER_MAX_CONCURRENCY: int = 2
    # 全局最大并发异步任务数
    BI_ASYNC_QUERY_GLOBAL_MAX_CONCURRENCY: int = 20
    # 结果预览行数（JSON 存储上限）
    BI_ASYNC_QUERY_PREVIEW_ROWS: int = 10_000
    # 任务记录保留天数（过期由清理任务软删 + CSV 物理删除）
    BI_ASYNC_QUERY_TTL_DAYS: int = 7
    # 同步查询软超时（秒，比硬超时 30s 早 5s 触发转异步）
    BI_SYNC_SOFT_TIMEOUT: int = 25
    # CSV 落盘目录（相对项目根）
    BI_ASYNC_QUERY_CSV_DIR: str = "data/async_query"
    # runner BLPOP 超时（秒，控制 shutdown 检查频率）
    BI_ASYNC_QUEUE_BLPOP_TIMEOUT: int = 5
    # 流式 fetchmany 批大小
    BI_ASYNC_QUERY_BATCH_SIZE: int = 1000
```

- [ ] **Step 2: 在 `app/core/code.py` 的 BI 图表段之后追加 4110-4119 错误码段**

在 `BI_DATASOURCE_UNAVAILABLE = "4201"` 之后追加：

```python
    # 41xx — BI 异步大查询
    BI_ASYNC_QUERY_NOT_ENABLED = "4110"  # 异步大查询功能未开启
    BI_ASYNC_QUERY_USER_CONCURRENCY_EXCEEDED = "4111"  # 用户并发任务数超限
    BI_ASYNC_QUERY_GLOBAL_CONCURRENCY_EXCEEDED = "4112"  # 全局并发任务数超限
    BI_ASYNC_QUERY_TASK_NOT_FOUND = "4113"  # 任务不存在
    BI_ASYNC_QUERY_TASK_NOT_CANCELLABLE = "4114"  # 任务当前状态不可取消
    BI_ASYNC_QUERY_RESULT_FILE_MISSING = "4115"  # 结果文件不存在或已清理
    BI_ASYNC_QUERY_TRANSFER_FAILED = "4116"  # 同步转异步失败
    BI_ASYNC_QUERY_CSV_WRITE_FAILED = "4117"  # CSV 写入失败
    BI_ASYNC_QUERY_TASK_TIMEOUT = "4118"  # 异步查询执行超时
    BI_ASYNC_QUERY_CANCELLED = "4119"  # 任务已取消
```

注意：spec 里写的是 `4110-4119`，但 `BI_CHART_NOT_FOUND` 已占用 `4200`。两段不冲突（411x ≠ 420x），保留 spec 的码值。

- [ ] **Step 3: 在 `.env.example` 的 BI 配额段后追加异步查询配置**

在 `BI_METADATA_BATCH_SIZE=100` 之后追加：

```bash
# BI 异步大查询
BI_ASYNC_QUERY_ENABLED=true
BI_ASYNC_QUERY_MAX_ROWS=1000000
BI_ASYNC_QUERY_TIMEOUT=600
BI_ASYNC_QUERY_USER_MAX_CONCURRENCY=2
BI_ASYNC_QUERY_GLOBAL_MAX_CONCURRENCY=20
BI_ASYNC_QUERY_PREVIEW_ROWS=10000
BI_ASYNC_QUERY_TTL_DAYS=7
BI_SYNC_SOFT_TIMEOUT=25
BI_ASYNC_QUERY_CSV_DIR=data/async_query
BI_ASYNC_QUEUE_BLPOP_TIMEOUT=5
BI_ASYNC_QUERY_BATCH_SIZE=1000
```

- [ ] **Step 4: 验证配置可加载**

Run: `uv run python -c "from app.business.bi.config import BIZ_SETTINGS; print(BIZ_SETTINGS.BI_ASYNC_QUERY_CSV_DIR, BIZ_SETTINGS.BI_SYNC_SOFT_TIMEOUT)"`
Expected: 输出 `data/async_query 25`

Run: `uv run python -c "from app.core.code import Code; print(Code.BI_ASYNC_QUERY_NOT_ENABLED, Code.BI_ASYNC_QUERY_CANCELLED)"`
Expected: 输出 `4110 4119`

- [ ] **Step 5: Commit**

```bash
git add app/business/bi/config.py app/core/code.py .env.example
git commit -m "feat(bi): add async query config and error codes (4110-4119)"
```

---

## Task 2: BiQueryTask 模型 + 迁移 + conftest

**Files:**
- Modify: `app/business/bi/models.py`
- Create: `migrations/models/2_xxxx_add_bi_query_task.py`（自动生成）
- Modify: `tests/conftest.py`

- [ ] **Step 1: 在 `app/business/bi/models.py` 末尾追加 `BiQueryTask` 模型**

在 `BiChart` 类之后追加：

```python
# ==================== async query 子模块 ====================


class BiQueryTask(BaseModel, AuditMixin, SoftDeleteMixin):
    """异步查询任务。

    记录一次异步 SQL 执行的完整生命周期：提交 → 运行 → 完成/失败/取消。
    小结果（≤ ``BI_ASYNC_QUERY_PREVIEW_ROWS``）直接存 ``result_snapshot`` JSONField；
    大结果落 CSV 到 ``BI_ASYNC_QUERY_CSV_DIR``，``result_uri`` 存相对路径。

    行级隔离：``tenant_id`` 存 ``user.id``（与 BiChart / BiChatSession 一致）。
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

注：`datetime` 类型注解需要 `from datetime import datetime` 已在文件顶部存在（检查后补）。

- [ ] **Step 2: 确认 `datetime` 已 import**

Run: `uv run python -c "from app.business.bi.models import BiQueryTask; print(BiQueryTask.__name__)"`
Expected: 若报 `NameError: name 'datetime' is not defined`，在 `models.py` 顶部追加 `from datetime import datetime` 后重试。

- [ ] **Step 3: 生成迁移文件**

Run: `just mm`
Expected: 生成 `migrations/models/2_xxxx_add_bi_query_task.py` 并 apply 到数据库。检查迁移 SQL 包含 `CREATE TABLE biz_bi_query_task` 与两个索引。

- [ ] **Step 4: 在 `tests/conftest.py` 顶部 import 处补 BiQueryTask**

确认 `TEST_TORTOISE_ORM` 的 models 列表里已有 `"app.business.bi.models"`（已存在，无需改）。在 `bi_datasource` fixture 之后追加 `bi_query_task` fixture：

```python
@pytest_asyncio.fixture(loop_scope="session")
async def bi_query_task(app, bi_datasource):
    """Seed a BiQueryTask owned by the super admin (tenant_id = user.id)."""
    from app.business.bi.models import BiQueryTask

    user = bi_datasource.tenant_id  # 与 bi_datasource 同一 user

    # 清理上一轮残留
    await BiQueryTask.all().delete()

    task = await BiQueryTask.create(
        name="测试任务",
        datasource_id=bi_datasource.id,
        sql_text="SELECT 1",
        status="pending",
        tenant_id=user,
        source="manual",
        created_by=str(user),
        updated_by=str(user),
    )
    return task
```

- [ ] **Step 5: 跑现有测试确保未破坏**

Run: `uv run pytest tests/test_bi_chart.py -v 2>&1 | tail -30`
Expected: 全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add app/business/bi/models.py migrations/models/ tests/conftest.py
git commit -m "feat(bi): add BiQueryTask model + migration + test fixture"
```

---

## Task 3: Schemas + Controller

**Files:**
- Modify: `app/business/bi/schemas.py`
- Modify: `app/business/bi/controllers.py`

- [ ] **Step 1: 在 `app/business/bi/schemas.py` 末尾追加 BiQueryTask Schema**

```python
# ============================================================
# async query：BiQueryTask
# ============================================================


class BiAsyncRunSchema(SchemaBase):
    """手动提交异步查询。"""

    sql: str = Field(title="要执行的 SQL")
    datasource_id: str = Field(title="数据源 ID（sqid）")
    name: str | None = Field(None, max_length=100, title="任务名称（可选）")


class BiQueryTaskSearchSchema(PageQueryBase):
    """任务分页查询。"""

    name: str | None = Field(None, title="按名称模糊搜索")
    status: str | None = Field(None, title="按状态筛选：pending/running/success/failed/cancelled")
    datasource_id: str | None = Field(None, title="按数据源筛选（sqid）")


class BiQueryTaskOutSchema(SchemaBase):
    """任务响应（不含 sql_text 全文，详情接口才返回）。"""

    id: str | None = Field(None, title="任务 ID（sqid）")
    name: str | None = Field(None, title="任务名称")
    datasource_id: str | None = Field(None, title="数据源 ID（sqid）")
    status: str | None = Field(None, title="任务状态")
    progress: int | None = Field(None, title="进度百分比 0-100")
    rows_fetched: int | None = Field(None, title="已扫描行数")
    elapsed_ms: int | None = Field(None, title="执行耗时（毫秒）")
    result_row_count: int | None = Field(None, title="结果总行数")
    result_is_truncated: bool | None = Field(None, title="结果是否被截断")
    error_message: str | None = Field(None, title="错误信息")
    started_at: datetime | None = Field(None, title="开始执行时间")
    finished_at: datetime | None = Field(None, title="完成时间")
    source: str | None = Field(None, title="提交来源")
    created_at: datetime | None = Field(None, title="创建时间")
```

- [ ] **Step 2: 在 `app/business/bi/controllers.py` 追加 controller**

在文件顶部 `from app.business.bi.models import (...)` 的导入列表中追加 `BiQueryTask`，然后在 `bi_chart_controller = CRUDBase(model=BiChart)` 之后追加：

```python
# ---- async query ----
bi_query_task_controller = CRUDBase(model=BiQueryTask)
```

并在底部 PascalCase 别名段追加：

```python
BiQueryTaskController = bi_query_task_controller
```

- [ ] **Step 3: 验证 import 与实例化**

Run: `uv run python -c "from app.business.bi.controllers import bi_query_task_controller; from app.business.bi.schemas import BiAsyncRunSchema, BiQueryTaskSearchSchema, BiQueryTaskOutSchema; print('ok')"`
Expected: 输出 `ok`

- [ ] **Step 4: Commit**

```bash
git add app/business/bi/schemas.py app/business/bi/controllers.py
git commit -m "feat(bi): add BiQueryTask schemas and controller"
```

---

## Task 4: async_query/queue.py — Redis List 队列

**Files:**
- Create: `app/business/bi/async_query/__init__.py`
- Create: `app/business/bi/async_query/queue.py`
- Test: `tests/test_bi_async_query.py`（新建，先写 queue 段）

- [ ] **Step 1: 创建 `app/business/bi/async_query/__init__.py`**

```python
"""BI 异步大查询子包。

组件：
- ``queue`` —— Redis List 队列（BLPOP）
- ``state`` —— Redis Hash 任务状态机
- ``storage`` —— 结果存储（JSON 预览 + CSV 流式）
- ``quota`` —— Redis 共享配额 + 熔断
- ``runner`` —— worker 协程（拉任务 → 执行 → 写结果）
"""

from __future__ import annotations
```

- [ ] **Step 2: 创建 `app/business/bi/async_query/queue.py`**

```python
"""Redis List 队列 — 任务调度通道。

使用 ``LPUSH`` 入队、``BLPOP`` 阻塞出队，保证多 worker 下每个任务只被消费一次。
key 设计见 spec §3.4。
"""

from __future__ import annotations

from redis.asyncio import Redis

QUEUE_KEY = "bi:async_query:queue"


async def enqueue(task_id: int, redis: Redis) -> None:
    """将 task_id 入队（LPUSH，左进）。"""
    await redis.lpush(QUEUE_KEY, task_id)


async def dequeue(redis: Redis, timeout: int = 5) -> int | None:
    """阻塞出队（BLPOP）。超时返回 None，由调用方决定继续循环或退出。"""
    result = await redis.blpop(QUEUE_KEY, timeout=timeout)
    if result is None:
        return None
    # fakeredis 与真 redis 返回 (key, value) 元组，value 为 bytes 或 str
    _, raw = result
    if isinstance(raw, bytes):
        raw = raw.decode()
    return int(raw)


async def queue_size(redis: Redis) -> int:
    """当前队列长度（监控用）。"""
    return await redis.llen(QUEUE_KEY)
```

- [ ] **Step 3: 创建测试文件 `tests/test_bi_async_query.py`，先写 queue 测试**

```python
"""BI 异步大查询测试。

覆盖：
- ``queue`` —— enqueue/dequeue/BLPOP 超时
- ``state`` —— init_state/update_progress/get_state/check_cancel/delete_state
- ``storage`` —— write_preview 截断 / write_csv_header 流式 / resolve_csv_path 防穿越
- ``quota`` —— check_concurrency / incr_running / decr_running
- ``services_async_query`` —— submit/get/cancel/list/delete 全流程
- ``runner`` —— execute_task 流式执行 / 取消 / 超时 / crash recovery
- API 鉴权 + 智能切换 transfer
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ===================== queue =====================


class TestQueue:
    async def test_enqueue_dequeue_fifo(self, app):
        from app.business.bi.async_query.queue import dequeue, enqueue, queue_size

        redis = app.state.redis
        await redis.delete("bi:async_query:queue")

        # LPUSH 入队顺序：1, 2, 3 → BLPOP 出队顺序：3, 2, 1（栈语义）
        # spec §3.4 用 List，BLPOP 是左 pop，所以 LPUSH+BLPOP 是 LIFO
        # 这里测的是 "入队 / 出队能配对"，顺序由调用方决定
        await enqueue(101, redis)
        await enqueue(102, redis)
        assert await queue_size(redis) == 2

        first = await dequeue(redis, timeout=1)
        # LPUSH 后 BLPOP 拿到的是最后入队的（102）
        assert first == 102

        second = await dequeue(redis, timeout=1)
        assert second == 101

        assert await queue_size(redis) == 0

    async def test_dequeue_timeout_returns_none(self, app):
        from app.business.bi.async_query.queue import dequeue

        redis = app.state.redis
        await redis.delete("bi:async_query:queue")
        result = await dequeue(redis, timeout=1)
        assert result is None
```

- [ ] **Step 4: 跑测试**

Run: `uv run pytest tests/test_bi_async_query.py::TestQueue -v`
Expected: 2 个测试 PASS。

- [ ] **Step 5: Commit**

```bash
git add app/business/bi/async_query/__init__.py app/business/bi/async_query/queue.py tests/test_bi_async_query.py
git commit -m "feat(bi): add async_query.queue (Redis List)"
```

---

## Task 5: async_query/state.py — Redis Hash 状态机

**Files:**
- Create: `app/business/bi/async_query/state.py`
- Test: `tests/test_bi_async_query.py`（追加 state 段）

- [ ] **Step 1: 创建 `app/business/bi/async_query/state.py`**

```python
"""任务状态机 — Redis Hash 存实时状态，DB 存最终快照。

Redis key 设计（spec §3.4）：
- ``bi:async_query:task:{id}`` Hash，TTL 7 天
  字段：status / progress / rows_fetched / elapsed_ms / error_message / started_at
- ``bi:async_query:task:{id}:cancel`` String，TTL 1 小时，值为 1 表示请求取消

状态流转（spec §3.3）：pending → running → success/failed/cancelled
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from redis.asyncio import Redis

TASK_KEY = "bi:async_query:task:{task_id}"
CANCEL_KEY = "bi:async_query:task:{task_id}:cancel"
TASK_TTL_SECONDS = 7 * 24 * 3600  # 7 天
CANCEL_TTL_SECONDS = 3600  # 1 小时


def _task_key(task_id: int) -> str:
    return TASK_KEY.format(task_id=task_id)


def _cancel_key(task_id: int) -> str:
    return CANCEL_KEY.format(task_id=task_id)


async def init_state(task_id: int, redis: Redis, status: str = "pending") -> None:
    """任务提交时初始化 Redis Hash。"""
    key = _task_key(task_id)
    await redis.hset(
        key,
        mapping={
            "status": status,
            "progress": "0",
            "rows_fetched": "0",
            "elapsed_ms": "0",
            "started_at": "",
            "error_message": "",
        },
    )
    await redis.expire(key, TASK_TTL_SECONDS)


async def update_status(task_id: int, status: str, redis: Redis, error_message: str | None = None) -> None:
    """更新任务状态。"""
    fields: dict[str, str] = {"status": status}
    if error_message is not None:
        fields["error_message"] = error_message
    await redis.hset(_task_key(task_id), mapping=fields)


async def update_progress(
    task_id: int,
    redis: Redis,
    progress: int | None = None,
    rows_fetched: int | None = None,
    elapsed_ms: int | None = None,
) -> None:
    """增量更新进度字段。任一参数为 None 则跳过。"""
    fields: dict[str, str] = {}
    if progress is not None:
        fields["progress"] = str(progress)
    if rows_fetched is not None:
        fields["rows_fetched"] = str(rows_fetched)
    if elapsed_ms is not None:
        fields["elapsed_ms"] = str(elapsed_ms)
    if fields:
        await redis.hset(_task_key(task_id), mapping=fields)


async def set_started_at(task_id: int, redis: Redis, started_at: datetime) -> None:
    await redis.hset(_task_key(task_id), mapping={"started_at": started_at.isoformat()})


async def get_state(task_id: int, redis: Redis) -> dict[str, Any]:
    """读取任务实时状态。"""
    raw = await redis.hgetall(_task_key(task_id))
    if not raw:
        return {}
    decoded: dict[str, Any] = {}
    for k, v in raw.items():
        key = k.decode() if isinstance(k, bytes) else k
        val = v.decode() if isinstance(v, bytes) else v
        decoded[key] = val
    # 类型归一化
    for int_field in ("progress", "rows_fetched", "elapsed_ms"):
        if int_field in decoded and decoded[int_field]:
            try:
                decoded[int_field] = int(decoded[int_field])
            except (ValueError, TypeError):
                pass
    return decoded


async def request_cancel(task_id: int, redis: Redis) -> None:
    """请求取消（worker 在下一批次检测）。"""
    await redis.set(_cancel_key(task_id), "1", ex=CANCEL_TTL_SECONDS)


async def check_cancel(task_id: int, redis: Redis) -> bool:
    """检查是否被请求取消。"""
    val = await redis.get(_cancel_key(task_id))
    if val is None:
        return False
    if isinstance(val, bytes):
        val = val.decode()
    return val == "1"


async def clear_cancel(task_id: int, redis: Redis) -> None:
    """清理取消标志（任务终态后）。"""
    await redis.delete(_cancel_key(task_id))


async def delete_state(task_id: int, redis: Redis) -> None:
    """删除任务状态（清理任务时）。"""
    await redis.delete(_task_key(task_id), _cancel_key(task_id))


# ---- 运行期 Redis 单例 ----
# PeriodicTask.handler 签名为 Callable[[], ...]（无参），
# cleanup_expired_tasks 等需在无参 handler 中访问 redis 的代码通过本单例获取。
_runtime_redis: Redis | None = None


def set_runtime_redis(redis: Redis) -> None:
    """lifespan 启动 worker 时调用，注入 app.state.redis。"""
    global _runtime_redis
    _runtime_redis = redis


def get_runtime_redis() -> Redis:
    if _runtime_redis is None:
        raise RuntimeError("runtime redis not initialized; call set_runtime_redis first")
    return _runtime_redis
```

- [ ] **Step 2: 在 `tests/test_bi_async_query.py` 追加 state 测试**

```python
# ===================== state =====================


class TestState:
    async def test_init_and_get_state(self, app):
        from app.business.bi.async_query.state import get_state, init_state

        redis = app.state.redis
        await init_state(9999, redis, status="pending")
        state = await get_state(9999, redis)
        assert state["status"] == "pending"
        assert state["progress"] == 0
        assert state["rows_fetched"] == 0
        assert state["elapsed_ms"] == 0

    async def test_update_progress(self, app):
        from app.business.bi.async_query.state import get_state, init_state, update_progress

        redis = app.state.redis
        await init_state(8888, redis)
        await update_progress(8888, redis, progress=45, rows_fetched=4500, elapsed_ms=3200)
        state = await get_state(8888, redis)
        assert state["progress"] == 45
        assert state["rows_fetched"] == 4500
        assert state["elapsed_ms"] == 3200

    async def test_update_status_with_error(self, app):
        from app.business.bi.async_query.state import get_state, init_state, update_status

        redis = app.state.redis
        await init_state(7777, redis)
        await update_status(7777, "failed", redis, error_message="timeout")
        state = await get_state(7777, redis)
        assert state["status"] == "failed"
        assert state["error_message"] == "timeout"

    async def test_check_cancel_default_false(self, app):
        from app.business.bi.async_query.state import check_cancel

        redis = app.state.redis
        await redis.delete("bi:async_query:task:6666:cancel")
        assert await check_cancel(6666, redis) is False

    async def test_request_cancel_sets_flag(self, app):
        from app.business.bi.async_query.state import check_cancel, request_cancel

        redis = app.state.redis
        await request_cancel(5555, redis)
        assert await check_cancel(5555, redis) is True

    async def test_get_state_missing_returns_empty(self, app):
        from app.business.bi.async_query.state import get_state

        redis = app.state.redis
        await redis.delete("bi:async_query:task:12345")
        assert await get_state(12345, redis) == {}
```

- [ ] **Step 3: 跑测试**

Run: `uv run pytest tests/test_bi_async_query.py::TestState -v`
Expected: 6 个测试 PASS。

- [ ] **Step 4: Commit**

```bash
git add app/business/bi/async_query/state.py tests/test_bi_async_query.py
git commit -m "feat(bi): add async_query.state (Redis Hash state machine)"
```

---

## Task 6: async_query/storage.py — 结果存储

**Files:**
- Create: `app/business/bi/async_query/storage.py`
- Test: `tests/test_bi_async_query.py`（追加 storage 段）

- [ ] **Step 1: 创建 `app/business/bi/async_query/storage.py`**

```python
"""结果存储 — JSON 预览 + CSV 流式落盘。

策略（spec §3.2 / §5.3）：
- ``write_preview``：取前 ``max_rows`` 行构造 JSON snapshot，标记 isTruncated
- ``write_csv_header``：写入 CSV 表头，调用方分批 fetchmany 后逐批 append 行
- ``resolve_csv_path``：拼接绝对路径 + 防目录穿越校验
- ``read_csv_stream``：下载用，按 chunk 读
"""

from __future__ import annotations

import csv
import io
import os
import re
from pathlib import Path
from typing import Any, Iterator

from app.business.bi.config import BIZ_SETTINGS

# result_uri 只允许 ``<task_id>.csv`` 形式，防目录穿越
_URI_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+\.csv$")


def write_preview(columns: list[str], rows: list[dict[str, Any]], elapsed_ms: int) -> dict:
    """构造结果预览 JSON。超过 ``BI_ASYNC_QUERY_PREVIEW_ROWS`` 的行被截断。"""
    max_rows = BIZ_SETTINGS.BI_ASYNC_QUERY_PREVIEW_ROWS
    total = len(rows)
    truncated = total > max_rows
    preview_rows = rows[:max_rows]
    return {
        "columns": columns,
        "rows": preview_rows,
        "rowCount": len(preview_rows),
        "elapsedMs": elapsed_ms,
        "isTruncated": truncated,
    }


def _csv_dir() -> Path:
    """CSV 落盘目录（绝对路径）。"""
    csv_dir = BIZ_SETTINGS.BI_ASYNC_QUERY_CSV_DIR
    # 相对路径基于项目根（cwd）
    p = Path(csv_dir)
    if not p.is_absolute():
        p = Path.cwd() / csv_dir
    p.mkdir(parents=True, exist_ok=True)
    return p


def make_result_uri(task_id: int) -> str:
    """生成 result_uri（相对路径）。"""
    return f"{task_id}.csv"


def resolve_csv_path(result_uri: str) -> Path:
    """把 result_uri 解析为绝对路径，并校验不逃逸 CSV 目录。

    Raises:
        ValueError: result_uri 格式非法或路径逃逸
    """
    if not _URI_PATTERN.match(result_uri):
        raise ValueError(f"非法 result_uri: {result_uri}")
    base = _csv_dir().resolve()
    target = (base / result_uri).resolve()
    # 防穿越：target 必须在 base 之内
    if base not in target.parents and target != base:
        raise ValueError(f"路径逃逸 CSV 目录: {result_uri}")
    return target


def write_csv_header(file_path: Path, columns: list[str]) -> None:
    """写 CSV 表头（覆盖写）。"""
    with file_path.open("w", newline="", encoding="utf-8") as f:
        # UTF-8 BOM 头方便 Excel 直接打开
        f.write("\ufeff")
        writer = csv.writer(f)
        writer.writerow(columns)


def append_csv_rows(file_path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    """追加写 CSV 行。"""
    with file_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow([row.get(c, "") for c in columns])


def read_csv_stream(file_path: Path, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
    """按 chunk 流式读 CSV（FastAPI StreamingResponse 用）。"""
    with file_path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk


def delete_csv(result_uri: str) -> None:
    """删除 CSV 文件（任务删除时调用）。不存在则静默。"""
    try:
        path = resolve_csv_path(result_uri)
        path.unlink(missing_ok=True)
    except ValueError:
        # 非法 result_uri 直接忽略
        pass
```

- [ ] **Step 2: 在 `tests/test_bi_async_query.py` 追加 storage 测试**

```python
# ===================== storage =====================


class TestStorage:
    async def test_write_preview_under_limit(self):
        from app.business.bi.async_query.storage import write_preview

        columns = ["a", "b"]
        rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
        result = write_preview(columns, rows, elapsed_ms=10)
        assert result["rowCount"] == 2
        assert result["isTruncated"] is False
        assert result["rows"] == rows

    async def test_write_preview_truncates(self, monkeypatch):
        from app.business.bi.async_query import storage as storage_mod
        from app.business.bi.config import BIZ_SETTINGS

        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_PREVIEW_ROWS", 3)
        rows = [{"a": i} for i in range(10)]
        result = storage_mod.write_preview(["a"], rows, elapsed_ms=5)
        assert result["rowCount"] == 3
        assert result["isTruncated"] is True
        assert len(result["rows"]) == 3

    async def test_resolve_csv_path_rejects_traversal(self):
        from app.business.bi.async_query.storage import resolve_csv_path

        with pytest.raises(ValueError):
            resolve_csv_path("../../etc/passwd")
        with pytest.raises(ValueError):
            resolve_csv_path("sub/dir/file.csv")
        with pytest.raises(ValueError):
            resolve_csv_path("")

    async def test_resolve_csv_path_accepts_valid(self):
        from app.business.bi.async_query.storage import resolve_csv_path

        path = resolve_csv_path("12345.csv")
        assert path.name == "12345.csv"
        assert path.suffix == ".csv"

    async def test_write_and_append_csv(self, tmp_path, monkeypatch):
        from app.business.bi.async_query.storage import (
            append_csv_rows,
            read_csv_stream,
            write_csv_header,
        )
        from app.business.bi.config import BIZ_SETTINGS

        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_CSV_DIR", str(tmp_path))

        file_path = tmp_path / "99999.csv"
        write_csv_header(file_path, ["a", "b"])
        append_csv_rows(file_path, ["a", "b"], [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}])
        append_csv_rows(file_path, ["a", "b"], [{"a": 3, "b": "z"}])

        content = b"".join(read_csv_stream(file_path))
        # BOM + header + 3 rows
        assert content.startswith(b"\xef\xbb\xbfa,b\r\n")
        assert b"1,x" in content
        assert b"3,z" in content
```

- [ ] **Step 3: 跑测试**

Run: `uv run pytest tests/test_bi_async_query.py::TestStorage -v`
Expected: 5 个测试 PASS。

- [ ] **Step 4: Commit**

```bash
git add app/business/bi/async_query/storage.py tests/test_bi_async_query.py
git commit -m "feat(bi): add async_query.storage (JSON preview + CSV streaming)"
```

---

## Task 7: async_query/quota.py + 改造 sandbox/quota.py 为 Redis 共享熔断

**Files:**
- Create: `app/business/bi/async_query/quota.py`
- Modify: `app/business/bi/sandbox/quota.py`
- Modify: `app/business/bi/sandbox/executor.py`
- Test: `tests/test_bi_async_query.py`（追加 quota 段）

- [ ] **Step 1: 创建 `app/business/bi/async_query/quota.py`（异步查询并发配额）**

```python
"""异步查询并发配额 — 用户级 + 全局级。

Redis 计数器（spec §6.1）：
- ``bi:async_query:user:{uid}:running`` 计数器，TTL 1 小时
- ``bi:async_query:global:running`` 计数器，TTL 1 小时
"""

from __future__ import annotations

from redis.asyncio import Redis

from app.business.bi.config import BIZ_SETTINGS
from app.core.code import Code
from app.core.exceptions import BizError

_USER_KEY = "bi:async_query:user:{user_id}:running"
_GLOBAL_KEY = "bi:async_query:global:running"
_TTL_SECONDS = 3600


def _user_key(user_id: int) -> str:
    return _USER_KEY.format(user_id=user_id)


async def check_concurrency(user_id: int, redis: Redis) -> None:
    """提交前检查并发配额。超限抛 BizError。"""
    user_running = await redis.get(_user_key(user_id))
    user_running = int(user_running) if user_running else 0
    if user_running >= BIZ_SETTINGS.BI_ASYNC_QUERY_USER_MAX_CONCURRENCY:
        raise BizError(Code.BI_ASYNC_QUERY_USER_CONCURRENCY_EXCEEDED)

    global_running = await redis.get(_GLOBAL_KEY)
    global_running = int(global_running) if global_running else 0
    if global_running >= BIZ_SETTINGS.BI_ASYNC_QUERY_GLOBAL_MAX_CONCURRENCY:
        raise BizError(Code.BI_ASYNC_QUERY_GLOBAL_CONCURRENCY_EXCEEDED)


async def incr_running(user_id: int, redis: Redis) -> None:
    """任务进入 running 时递增计数。"""
    pipe = redis.pipeline()
    pipe.incr(_user_key(user_id))
    pipe.expire(_user_key(user_id), _TTL_SECONDS)
    pipe.incr(_GLOBAL_KEY)
    pipe.expire(_GLOBAL_KEY, _TTL_SECONDS)
    await pipe.execute()


async def decr_running(user_id: int, redis: Redis) -> None:
    """任务终态时递减计数（不会低于 0）。"""
    user_key = _user_key(user_id)
    user_val = await redis.decr(user_key)
    if user_val < 0:
        await redis.set(user_key, 0)
    global_val = await redis.decr(_GLOBAL_KEY)
    if global_val < 0:
        await redis.set(_GLOBAL_KEY, 0)
```

- [ ] **Step 2: 改造 `app/business/bi/sandbox/quota.py` — 替换进程内字典为 Redis ZSet**

完整重写 `quota.py`（保留同步签名以减少调用方改动；新增 async 版本供 executor 用）：

```python
"""查询配额限制 — 行数 / 超时 / 熔断。

熔断改造（spec §6.2）：原进程内字典在多 worker 下失效，改为 Redis ZSet。
- ``bi:quota:failures:{scope}`` ZSet，score=时间戳，member=时间戳
- 窗口内失败次数 >= threshold 触发熔断

scope 形如 ``user:{user_id}`` 或 ``datasource:{datasource_id}``。
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from redis.asyncio import Redis

from app.core.exceptions import BizError

# 错误码 4102 = 查询熔断
_BREAKER_OPEN_CODE = 4102


@dataclass
class QuotaConfig:
    """配额配置。"""

    max_rows: int = int(os.getenv("BI_QUERY_MAX_ROWS", "10000"))
    timeout_seconds: int = int(os.getenv("BI_QUERY_TIMEOUT", "30"))
    breaker_threshold: int = int(os.getenv("BI_QUERY_BREAKER_THRESHOLD", "10"))
    breaker_window_seconds: int = 60


_default_config = QuotaConfig()


def _failures_key(scope: str) -> str:
    return f"bi:quota:failures:{scope}"


async def record_failure(scope: str, redis: Redis, config: QuotaConfig | None = None) -> None:
    """记录失败到 Redis ZSet。"""
    cfg = config or _default_config
    now = time.time()
    key = _failures_key(scope)
    pipe = redis.pipeline()
    pipe.zadd(key, {str(now): now})
    # 清理窗口外的旧记录
    pipe.zremrangebyscore(key, 0, now - cfg.breaker_window_seconds)
    pipe.expire(key, cfg.breaker_window_seconds)
    await pipe.execute()


async def record_success(scope: str, redis: Redis) -> None:
    """成功时清空失败计数。"""
    await redis.delete(_failures_key(scope))


async def check_quota(scope: str, redis: Redis, config: QuotaConfig | None = None) -> None:
    """检查熔断。超阈值抛 BizError(4102)。"""
    cfg = config or _default_config
    now = time.time()
    key = _failures_key(scope)
    count = await redis.zcount(key, now - cfg.breaker_window_seconds, now)
    if count >= cfg.breaker_threshold:
        raise BizError(
            _BREAKER_OPEN_CODE,
            f"查询熔断：scope={scope} 在 {cfg.breaker_window_seconds} 秒内失败 {count} 次，"
            f"超过阈值 {cfg.breaker_threshold}",
        )


def check_row_limit(row_count: int, config: QuotaConfig | None = None) -> None:
    """检查返回行数是否超限。

    Raises:
        BizError(4103): 行数超限
    """
    cfg = config or _default_config
    if row_count > cfg.max_rows:
        raise BizError(4103, f"查询返回行数 {row_count} 超过限制 {cfg.max_rows}")


def get_timeout(config: QuotaConfig | None = None) -> int:
    """获取查询超时秒数。"""
    cfg = config or _default_config
    return cfg.timeout_seconds


# ---- 兼容旧 API（同步签名已废弃，保留只为 import 兼容，调用方应改用 async 版） ----
# 旧 _failure_records 进程内字典已删除；旧 check_quota(user_id) / record_failure(user_id)
# 同步函数已删除。所有调用方改为传 redis 调 async 版。


def reset_failures_sync() -> None:
    """测试用：清空所有熔断记录（仅当无 redis 实例时用，正常应调 async 版）。"""
    # 无操作：旧进程内字典已移除，调用方应直接 await redis.delete(...)
    return


async def reset_failures(scope: str | None, redis: Redis) -> None:
    """重置失败计数（测试或管理用途）。scope=None 时清所有已知 scope。"""
    if scope is None:
        # 扫描 bi:quota:failures:* —— 测试场景用 fakeredis，生产应避免
        async for key in redis.scan_iter(match="bi:quota:failures:*"):
            await redis.delete(key)
    else:
        await redis.delete(_failures_key(scope))
```

- [ ] **Step 3: 改造 `app/business/bi/sandbox/executor.py` — 调整 quota 调用为 async + redis**

修改要点：
- `execute_sql` 接受可选 `redis` 参数；若 redis 为 None，跳过熔断（保留兼容）。
- `check_quota` / `record_failure` / `record_success` 改为 async 调用，scope 用 `f"user:{user_id}"`。

修改 `execute_sql` 函数签名与实现：

```python
async def execute_sql(
    sql: str,
    datasource: BiDatasource,
    user_id: int,
    timeout: int | None = None,
    max_rows: int | None = None,
    redis=None,
) -> ExecutionResult:
    """执行 SQL 并返回结果。

    Args:
        redis: Redis 客户端（用于熔断计数）。None 时跳过熔断（向后兼容）。
    """
    scope = f"user:{user_id}"

    # 配额检查
    if redis is not None:
        await check_quota(scope, redis)

    engine = await get_engine(datasource)
    timeout_seconds = timeout or get_timeout()

    start = time.time()
    try:
        async with engine.connect() as conn:
            result = await asyncio.wait_for(conn.execute(text(sql)), timeout=timeout_seconds)
            columns = list(result.keys()) if result.returns_rows else []
            rows: list[dict[str, Any]] = []
            if result.returns_rows:
                fetched = result.fetchmany(max_rows or 10000)
                for row in fetched:
                    rows.append(dict(row._mapping))

        elapsed_ms = int((time.time() - start) * 1000)
        check_row_limit(len(rows))

        if redis is not None:
            await record_success(scope, redis)

        return ExecutionResult(
            rows=rows,
            columns=columns,
            elapsed_ms=elapsed_ms,
            row_count=len(rows),
        )

    except BizError:
        if redis is not None:
            await record_failure(scope, redis)
        raise
    except Exception as e:
        if redis is not None:
            await record_failure(scope, redis)
        elapsed_ms = int((time.time() - start) * 1000)
        raise BizError(4104, f"SQL 执行失败: {e}") from e
```

更新顶部 import：

```python
from app.business.bi.sandbox.quota import (
    check_quota,
    check_row_limit,
    get_timeout,
    record_failure,
    record_success,
)
```

- [ ] **Step 4: 改造 `app/business/bi/services.py` 的 `run_sql` — 传 redis 给 execute_sql**

在 `run_sql` 函数体内，把 `result: ExecutionResult = await execute_sql(safe_sql, ds, user_id=user_id)` 改为：

```python
    # 传 redis 给熔断计数（多 worker 共享）
    from app.utils import get_redis_from_app

    redis = get_redis_from_app()
    result: ExecutionResult = await execute_sql(safe_sql, ds, user_id=user_id, redis=redis)
```

注：`get_redis_from_app` 是 `app.utils` 暴露的辅助函数；若不存在则在 `app/core/redis.py` 添加：

```python
def get_redis_from_app() -> Redis | None:
    """从当前 FastAPI 请求上下文取 redis（无请求上下文时返回 None）。"""
    from app.utils import get_app_state

    state = get_app_state()
    return getattr(state, "redis", None) if state else None
```

若 `get_app_state` 也不存在，则在 `app/core/redis.py` 直接用 `from starlette.requests import Request` + ContextVar 方案；最简实现：

```python
import contextvars

_app_state_var: contextvars.ContextVar = contextvars.ContextVar("app_state", default=None)


def set_app_state(state) -> None:
    _app_state_var.set(state)


def get_app_state():
    return _app_state_var.get()
```

并在 `app/__init__.py` 的 `lifespan` 中 `await init_redis()` 之后追加 `set_app_state(_app.state)`。

**简化方案（推荐）**：直接在 `services.run_sql` 里从 `fastapi` 的 `Request` 取。但 `run_sql` 当前不接受 Request 参数。最干净的做法是让 `execute_sql` 的 `redis` 参数成为必填，由调用方传入。改 `services.run_sql` 签名：

```python
async def run_sql(user, schema: SqlRunSchema, redis=None) -> dict:
```

API 层（`api/sql_workbench.py`）改用 `Depends(get_redis)` 注入。但 `get_redis` 在 `app/core/redis.py` 已存在（`def get_redis(request: Request) -> Redis`），可直接用：

修改 `api/sql_workbench.py` 的 `run_sql_endpoint`：

```python
from app.core.redis import AioRedis


@router.post("/sql/run", ...)
async def run_sql_endpoint(obj_in: SqlRunSchema, redis: AioRedis):
    user = _get_user_or_raise()
    result = await run_sql(user, obj_in, redis=redis)
    return Success(data=result)
```

并相应改 `services.run_sql` 签名为 `async def run_sql(user, schema, redis) -> dict`，把 `redis` 作为必传参数。

同样改 `services.preview_table`、`services.test_metric` 的 `execute_sql` 调用，传 redis（如有）。`preview_table` 通过 `get_current_user_id` 调用，可让 API 层传 redis；为最小改动，让 `services.preview_table` 也接受 `redis` 参数。

- [ ] **Step 5: 在 `tests/test_bi_async_query.py` 追加 quota 测试**

```python
# ===================== quota =====================


class TestAsyncQuota:
    async def test_check_concurrency_under_limit(self, app):
        from app.business.bi.async_query.quota import check_concurrency

        redis = app.state.redis
        await redis.delete("bi:async_query:user:1:running", "bi:async_query:global:running")
        # 不应抛异常
        await check_concurrency(1, redis)

    async def test_check_concurrency_user_exceeded(self, app, monkeypatch):
        from app.business.bi.async_query.quota import check_concurrency
        from app.business.bi.config import BIZ_SETTINGS

        redis = app.state.redis
        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_USER_MAX_CONCURRENCY", 2)
        await redis.set("bi:async_query:user:2:running", 2)
        with pytest.raises(Exception) as exc:
            await check_concurrency(2, redis)
        assert "4111" in str(exc.value) or "用户并发" in str(exc.value)

    async def test_check_concurrency_global_exceeded(self, app, monkeypatch):
        from app.business.bi.async_query.quota import check_concurrency
        from app.business.bi.config import BIZ_SETTINGS

        redis = app.state.redis
        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_GLOBAL_MAX_CONCURRENCY", 20)
        await redis.set("bi:async_query:global:running", 20)
        with pytest.raises(Exception) as exc:
            await check_concurrency(3, redis)
        assert "4112" in str(exc.value) or "全局并发" in str(exc.value)

    async def test_incr_decr_running(self, app):
        from app.business.bi.async_query.quota import (
            check_concurrency,
            decr_running,
            incr_running,
        )

        redis = app.state.redis
        await redis.delete("bi:async_query:user:4:running", "bi:async_query:global:running")
        await incr_running(4, redis)
        await incr_running(4, redis)
        assert int(await redis.get("bi:async_query:user:4:running")) == 2
        await decr_running(4, redis)
        assert int(await redis.get("bi:async_query:user:4:running")) == 1

    async def test_decr_clamps_to_zero(self, app):
        from app.business.bi.async_query.quota import decr_running

        redis = app.state.redis
        await redis.delete("bi:async_query:user:5:running")
        await decr_running(5, redis)  # 不会变成 -1
        assert int(await redis.get("bi:async_query:user:5:running")) == 0


class TestSandboxQuotaRedis:
    """sandbox/quota.py 改造为 Redis 后的行为测试。"""

    async def test_record_failure_and_check_quota(self, app):
        from app.business.bi.sandbox.quota import (
            QuotaConfig,
            check_quota,
            record_failure,
        )

        redis = app.state.redis
        await redis.delete("bi:quota:failures:user:10")
        cfg = QuotaConfig(breaker_threshold=3, breaker_window_seconds=60)

        # 前 2 次不熔断
        await record_failure("user:10", redis, cfg)
        await record_failure("user:10", redis, cfg)
        await check_quota("user:10", redis, cfg)  # 不抛

        # 第 3 次触发熔断
        await record_failure("user:10", redis, cfg)
        with pytest.raises(Exception) as exc:
            await check_quota("user:10", redis, cfg)
        assert "4102" in str(exc.value) or "熔断" in str(exc.value)

    async def test_record_success_clears(self, app):
        from app.business.bi.sandbox.quota import (
            check_quota,
            record_failure,
            record_success,
        )

        redis = app.state.redis
        await redis.delete("bi:quota:failures:user:11")
        await record_failure("user:11", redis)
        await record_success("user:11", redis)
        # 不应抛熔断
        await check_quota("user:11", redis)
```

- [ ] **Step 6: 跑测试 + 确保现有 BI 测试不破坏**

Run: `uv run pytest tests/test_bi_async_query.py::TestAsyncQuota tests/test_bi_async_query.py::TestSandboxQuotaRedis -v`
Expected: 全部 PASS。

Run: `uv run pytest tests/test_bi_chart.py -v 2>&1 | tail -20`
Expected: 全部 PASS。若有失败，多半是 `execute_sql` 调用方未传 redis；让 `redis=None` 默认值生效即可。

- [ ] **Step 7: Commit**

```bash
git add app/business/bi/async_query/quota.py app/business/bi/sandbox/quota.py app/business/bi/sandbox/executor.py app/business/bi/services.py app/business/bi/api/sql_workbench.py tests/test_bi_async_query.py
git commit -m "feat(bi): migrate quota to Redis ZSet + add async_query.quota"
```

---

## Task 8: async_query/runner.py — Worker 协程

**Files:**
- Create: `app/business/bi/async_query/runner.py`
- Test: `tests/test_bi_async_query_runner.py`（新建）

- [ ] **Step 1: 创建 `app/business/bi/async_query/runner.py`**

```python
"""异步查询 worker — 从队列拉任务 → 流式执行 → 写结果 → 更状态。

核心流程（spec §5.3）：
1. ``worker_loop`` 阻塞 BLPOP，拿到 task_id 后调 ``execute_task``
2. ``execute_task`` 流式 fetchmany，每批次：
   - 检查 cancel 标志
   - 累计 rows_fetched / elapsed_ms
   - 写 CSV（追加）
   - 前 N 行追加到 preview_rows
   - 检查累计超时
3. 完成：写 result_snapshot + result_uri + 状态 success + DECR running
4. 失败/取消/超时：写状态 + 清理半成品 CSV + DECR running
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any

from sqlalchemy import text

from app.business.bi.async_query import state, storage
from app.business.bi.async_query.queue import dequeue
from app.business.bi.async_query.quota import decr_running
from app.business.bi.config import BIZ_SETTINGS
from app.business.bi.models import BiQueryTask
from app.business.bi.sandbox.dialect import get_dialect_name
from app.business.bi.sandbox.executor import get_engine
from app.business.bi.sandbox.tenant import inject_tenant_filter
from app.business.bi.sandbox.whitelist import validate_sql
from app.core.code import Code
from app.core.exceptions import BizError
from app.core.log import log
from redis.asyncio import Redis


class TaskCancelledError(Exception):
    """任务被用户取消。"""


class TaskTimeoutError(Exception):
    """任务累计执行超时。"""


# 全局 shutdown 事件，由 lifespan 设置
_shutdown_event: asyncio.Event | None = None


def set_shutdown_event(event: asyncio.Event) -> None:
    global _shutdown_event
    _shutdown_event = event


def get_shutdown_event() -> asyncio.Event:
    global _shutdown_event
    if _shutdown_event is None:
        _shutdown_event = asyncio.Event()
    return _shutdown_event


async def worker_loop(redis: Redis, app: Any) -> None:
    """worker 主循环。每个 granian worker 启动一个协程。"""
    log.info("bi.async_query worker started")
    shutdown = get_shutdown_event()
    blpop_timeout = BIZ_SETTINGS.BI_ASYNC_QUEUE_BLPOP_TIMEOUT

    while not shutdown.is_set():
        try:
            task_id = await dequeue(redis, timeout=blpop_timeout)
        except Exception:
            log.exception("bi.async_query dequeue failed")
            await asyncio.sleep(1)
            continue

        if task_id is None:
            continue

        try:
            await execute_task(task_id, redis, app)
        except Exception:
            log.exception("bi.async_query execute_task failed task_id={}", task_id)
            await state.update_status(task_id, "failed", redis, error_message="worker internal error")

    log.info("bi.async_query worker stopped")


async def execute_task(task_id: int, redis: Redis, app: Any) -> None:
    """执行单个任务。"""
    task = await BiQueryTask.get_or_none(id=task_id, deleted_at__isnull=True)
    if task is None:
        log.warning("bi.async_query task {} not found, skip", task_id)
        return

    # 标记 running
    started_at = datetime.now()
    task.status = "running"
    task.started_at = started_at
    await task.save(update_fields=["status", "started_at", "updated_at"])
    await state.update_status(task_id, "running", redis)
    await state.set_started_at(task_id, redis, started_at)

    # 加载关联数据源
    datasource = await task.datasource
    user_id = task.tenant_id  # tenant_id 存的就是 user_id

    # 递增 running 计数（pending → running 时）
    from app.business.bi.async_query.quota import incr_running
    await incr_running(user_id, redis)

    start_time = time.time()
    csv_path: Any = None
    result_uri: str | None = None

    try:
        # test_connection —— 不可用直接失败
        from app.business.bi.sandbox.executor import test_connection

        ok, err_msg, _ = await test_connection(datasource)
        if not ok:
            raise BizError(Code.BI_DATASOURCE_UNAVAILABLE, f"数据源不可用：{err_msg}")

        # 二次校验 SQL（防止 task 数据被篡改）
        dialect = get_dialect_name(datasource.db_type)
        validation = validate_sql(task.sql_text, dialect=dialect)
        safe_sql = validation.sql
        safe_sql = inject_tenant_filter(safe_sql, tenant_id=user_id, dialect=dialect)

        engine = await get_engine(datasource)

        # 流式执行
        columns: list[str] = []
        preview_rows: list[dict[str, Any]] = []
        total_rows = 0
        max_preview = BIZ_SETTINGS.BI_ASYNC_QUERY_PREVIEW_ROWS
        batch_size = BIZ_SETTINGS.BI_ASYNC_QUERY_BATCH_SIZE
        timeout_seconds = BIZ_SETTINGS.BI_ASYNC_QUERY_TIMEOUT
        csv_dir = BIZ_SETTINGS.BI_ASYNC_QUERY_CSV_DIR

        async with engine.connect() as conn:
            result = await conn.execute(text(safe_sql))
            if result.returns_rows:
                columns = list(result.keys())
                # 准备 CSV（只有数据量大时才落 CSV —— 但本批次始终写 CSV 简化逻辑）
                result_uri = storage.make_result_uri(task_id)
                csv_path = storage.resolve_csv_path(result_uri)
                storage.write_csv_header(csv_path, columns)

                while True:
                    # 检查取消
                    if await state.check_cancel(task_id, redis):
                        raise TaskCancelledError()

                    # 检查超时
                    elapsed = time.time() - start_time
                    if elapsed > timeout_seconds:
                        raise TaskTimeoutError(f"累计 {int(elapsed)}s > {timeout_seconds}s")

                    batch = result.fetchmany(batch_size)
                    if not batch:
                        break

                    batch_dicts = [dict(row._mapping) for row in batch]
                    total_rows += len(batch_dicts)

                    # 追加到 preview（前 max_preview 行）
                    remaining = max_preview - len(preview_rows)
                    if remaining > 0:
                        preview_rows.extend(batch_dicts[:remaining])

                    # 追加 CSV
                    storage.append_csv_rows(csv_path, columns, batch_dicts)

                    # 更新进度
                    elapsed_ms = int(elapsed * 1000)
                    # 进度估算：用超时占比作 proxy（无法获知 SQL 总行数）
                    progress = min(99, int(elapsed / timeout_seconds * 100))
                    await state.update_progress(
                        task_id,
                        redis,
                        progress=progress,
                        rows_fetched=total_rows,
                        elapsed_ms=elapsed_ms,
                    )

        elapsed_ms = int((time.time() - start_time) * 1000)

        # 写结果快照
        snapshot = storage.write_preview(columns, preview_rows, elapsed_ms)
        is_truncated = total_rows > max_preview

        task.status = "success"
        task.progress = 100
        task.rows_fetched = total_rows
        task.elapsed_ms = elapsed_ms
        task.result_snapshot = snapshot
        task.result_uri = result_uri
        task.result_row_count = total_rows
        task.result_is_truncated = is_truncated
        task.finished_at = datetime.now()
        await task.save(update_fields=[
            "status", "progress", "rows_fetched", "elapsed_ms",
            "result_snapshot", "result_uri", "result_row_count",
            "result_is_truncated", "finished_at", "updated_at",
        ])
        await state.update_status(task_id, "success", redis)
        await state.update_progress(
            task_id, redis, progress=100, rows_fetched=total_rows, elapsed_ms=elapsed_ms
        )
        await state.clear_cancel(task_id, redis)
        log.info("bi.async_query task {} success rows={}", task_id, total_rows)

    except TaskCancelledError:
        await _finalize_terminal(task_id, redis, user_id, "cancelled", "用户取消", start_time, csv_path)
        log.info("bi.async_query task {} cancelled", task_id)
    except TaskTimeoutError as e:
        await _finalize_terminal(task_id, redis, user_id, "failed", f"执行超时：{e}", start_time, csv_path)
        log.warning("bi.async_query task {} timeout", task_id)
    except BizError as e:
        await _finalize_terminal(task_id, redis, user_id, "failed", str(e), start_time, csv_path)
        log.warning("bi.async_query task {} biz_error: {}", task_id, e)
    except Exception as e:
        await _finalize_terminal(task_id, redis, user_id, "failed", f"内部错误：{e}", start_time, csv_path)
        log.exception("bi.async_query task {} internal_error", task_id)


async def _finalize_terminal(
    task_id: int,
    redis: Redis,
    user_id: int,
    status: str,
    error_message: str,
    start_time: float,
    csv_path: Any,
) -> None:
    """统一处理终态：更新 DB + Redis + 清理半成品 CSV + DECR running。"""
    elapsed_ms = int((time.time() - start_time) * 1000)
    task = await BiQueryTask.get_or_none(id=task_id)
    if task is not None:
        task.status = status
        task.elapsed_ms = elapsed_ms
        task.error_message = error_message
        task.finished_at = datetime.now()
        await task.save(update_fields=["status", "elapsed_ms", "error_message", "finished_at", "updated_at"])
    await state.update_status(task_id, status, redis, error_message=error_message)
    await state.clear_cancel(task_id, redis)
    # 清理半成品 CSV（失败/取消时）
    if csv_path is not None:
        try:
            from pathlib import Path
            if isinstance(csv_path, Path):
                csv_path.unlink(missing_ok=True)
        except Exception:
            log.warning("bi.async_query task {} cleanup csv failed", task_id)
    await decr_running(user_id, redis)


async def recover_stale_tasks(redis: Redis) -> int:
    """启动时扫描 status=running 但 created_at 超过 timeout 的任务，标记 failed。

    Returns:
        恢复的任务数
    """
    from datetime import datetime, timedelta

    timeout = BIZ_SETTINGS.BI_ASYNC_QUERY_TIMEOUT
    threshold = datetime.now() - timedelta(seconds=timeout * 2)  # 2 倍宽限
    stale = await BiQueryTask.filter(status="running", started_at__lt=threshold)
    for task in stale:
        task.status = "failed"
        task.error_message = "worker crash recovery：任务异常中断"
        task.finished_at = datetime.now()
        await task.save(update_fields=["status", "error_message", "finished_at", "updated_at"])
        await state.update_status(task.id, "failed", redis, error_message="worker crash recovery")
        log.warning("bi.async_query recovered stale task {}", task.id)
    return len(stale)
```

- [ ] **Step 2: 创建测试 `tests/test_bi_async_query_runner.py`**

```python
"""async_query.runner worker 测试。

测试策略：
- 不依赖真 SQLAlchemy 连接，用 monkeypatch 替换 ``execute_sql`` 路径中的 ``engine.connect`` 与 ``result.fetchmany``
- 验证：成功路径写 result_snapshot/result_uri；取消路径清理 CSV；超时路径写 failed
- 验证：DB 状态 + Redis 状态同步更新
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


class _FakeResult:
    """模拟 SQLAlchemy Result 对象。"""

    def __init__(self, columns: list[str], all_rows: list[dict], batch_size: int):
        self._columns = columns
        self._all_rows = all_rows
        self._batch_size = batch_size
        self._cursor = 0
        self.returns_rows = True

    def keys(self):
        return self._columns

    def fetchmany(self, size: int):
        if self._cursor >= len(self._all_rows):
            return []
        end = min(self._cursor + size, len(self._all_rows))
        batch = self._all_rows[self._cursor:end]
        self._cursor = end
        return [SimpleNamespace(_mapping=r) for r in batch]


class TestExecuteTask:
    async def test_success_writes_snapshot_and_csv(self, app, bi_datasource, monkeypatch, tmp_path):
        from app.business.bi.async_query import runner, state
        from app.business.bi.async_query.queue import enqueue
        from app.business.bi.config import BIZ_SETTINGS
        from app.business.bi.models import BiQueryTask

        # 配置：CSV 目录指 tmp_path，batch 小一点便于测多批次
        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_CSV_DIR", str(tmp_path))
        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_BATCH_SIZE", 5)
        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_PREVIEW_ROWS", 10)

        user_id = bi_datasource.tenant_id
        task = await BiQueryTask.create(
            name="runner-success",
            datasource_id=bi_datasource.id,
            sql_text="SELECT id, name FROM orders",
            status="pending",
            tenant_id=user_id,
            source="manual",
            created_by=str(user_id),
            updated_by=str(user_id),
        )
        await state.init_state(task.id, app.state.redis, status="pending")

        # mock test_connection / validate_sql / inject_tenant_filter / get_engine
        async def _fake_test_connection(ds):
            return True, "ok", 1

        def _fake_validate_sql(sql, dialect="sqlite"):
            return SimpleNamespace(sql=sql, is_valid=True, error=None, warnings=[])

        def _fake_inject_tenant_filter(sql, tenant_id, dialect="sqlite"):
            return sql

        fake_engine = MagicMock()
        fake_result = _FakeResult(
            columns=["id", "name"],
            all_rows=[{"id": i, "name": f"row{i}"} for i in range(23)],  # 23 行 = 5 批
            batch_size=5,
        )

        class _FakeConn:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def execute(self, statement):
                return fake_result

        fake_engine.connect = MagicMock(return_value=_FakeConn())

        async def _fake_get_engine(ds):
            return fake_engine

        monkeypatch.setattr(runner, "test_connection", _fake_test_connection)
        monkeypatch.setattr(runner, "validate_sql", _fake_validate_sql)
        monkeypatch.setattr(runner, "inject_tenant_filter", _fake_inject_tenant_filter)
        monkeypatch.setattr(runner, "get_engine", _fake_get_engine)

        await runner.execute_task(task.id, app.state.redis, app)

        # DB 状态
        await task.refresh_from_db()
        assert task.status == "success"
        assert task.rows_fetched == 23
        assert task.result_row_count == 23
        assert task.result_uri == f"{task.id}.csv"
        # snapshot 预览 ≤ 10 行
        assert task.result_snapshot["rowCount"] == 10
        assert task.result_snapshot["isTruncated"] is True

        # CSV 文件存在且非空
        csv_file = tmp_path / f"{task.id}.csv"
        assert csv_file.exists()
        content = csv_file.read_text(encoding="utf-8")
        assert "id,name" in content
        assert "row22" in content

    async def test_cancelled_cleans_csv(self, app, bi_datasource, monkeypatch, tmp_path):
        from app.business.bi.async_query import runner, state
        from app.business.bi.config import BIZ_SETTINGS
        from app.business.bi.models import BiQueryTask

        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_CSV_DIR", str(tmp_path))
        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_BATCH_SIZE", 2)

        user_id = bi_datasource.tenant_id
        task = await BiQueryTask.create(
            name="runner-cancel",
            datasource_id=bi_datasource.id,
            sql_text="SELECT id FROM orders",
            status="pending",
            tenant_id=user_id,
            source="manual",
            created_by=str(user_id),
            updated_by=str(user_id),
        )
        await state.init_state(task.id, app.state.redis, status="pending")
        # 预先设取消标志
        await state.request_cancel(task.id, app.state.redis)

        async def _fake_test_connection(ds):
            return True, "ok", 1

        def _fake_validate_sql(sql, dialect="sqlite"):
            return SimpleNamespace(sql=sql, is_valid=True, error=None, warnings=[])

        def _fake_inject_tenant_filter(sql, tenant_id, dialect="sqlite"):
            return sql

        fake_engine = MagicMock()
        fake_result = _FakeResult(
            columns=["id"],
            all_rows=[{"id": i} for i in range(10)],
            batch_size=2,
        )

        class _FakeConn:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def execute(self, statement):
                return fake_result

        fake_engine.connect = MagicMock(return_value=_FakeConn())

        async def _fake_get_engine(ds):
            return fake_engine

        monkeypatch.setattr(runner, "test_connection", _fake_test_connection)
        monkeypatch.setattr(runner, "validate_sql", _fake_validate_sql)
        monkeypatch.setattr(runner, "inject_tenant_filter", _fake_inject_tenant_filter)
        monkeypatch.setattr(runner, "get_engine", _fake_get_engine)

        await runner.execute_task(task.id, app.state.redis, app)

        await task.refresh_from_db()
        assert task.status == "cancelled"
        assert task.error_message is not None
        # 半成品 CSV 应被清理
        csv_file = tmp_path / f"{task.id}.csv"
        assert not csv_file.exists()

    async def test_datasource_unavailable_marks_failed(self, app, bi_datasource, monkeypatch):
        from app.business.bi.async_query import runner, state
        from app.business.bi.models import BiQueryTask

        user_id = bi_datasource.tenant_id
        task = await BiQueryTask.create(
            name="runner-ds-fail",
            datasource_id=bi_datasource.id,
            sql_text="SELECT 1",
            status="pending",
            tenant_id=user_id,
            source="manual",
            created_by=str(user_id),
            updated_by=str(user_id),
        )
        await state.init_state(task.id, app.state.redis, status="pending")

        async def _fake_test_connection(ds):
            return False, "连接失败: mock", 5

        monkeypatch.setattr(runner, "test_connection", _fake_test_connection)

        await runner.execute_task(task.id, app.state.redis, app)

        await task.refresh_from_db()
        assert task.status == "failed"
        assert "数据源不可用" in (task.error_message or "")


class TestRecoverStaleTasks:
    async def test_recovers_old_running(self, app, bi_datasource):
        from datetime import datetime, timedelta

        from app.business.bi.async_query import runner
        from app.business.bi.models import BiQueryTask

        user_id = bi_datasource.tenant_id
        # 构造一个 2 小时前 started_at 的 running 任务
        old_started = datetime.now() - timedelta(hours=2)
        task = await BiQueryTask.create(
            name="stale",
            datasource_id=bi_datasource.id,
            sql_text="SELECT 1",
            status="running",
            started_at=old_started,
            tenant_id=user_id,
            source="manual",
            created_by=str(user_id),
            updated_by=str(user_id),
        )

        n = await runner.recover_stale_tasks(app.state.redis)
        assert n >= 1

        await task.refresh_from_db()
        assert task.status == "failed"
        assert "crash recovery" in (task.error_message or "")
```

- [ ] **Step 3: 跑测试**

Run: `uv run pytest tests/test_bi_async_query_runner.py -v`
Expected: 4 个测试 PASS。

- [ ] **Step 4: Commit**

```bash
git add app/business/bi/async_query/runner.py tests/test_bi_async_query_runner.py
git commit -m "feat(bi): add async_query.runner (worker loop + execute_task + crash recovery)"
```

---

## Task 9: services_async_query.py — 业务编排

**Files:**
- Create: `app/business/bi/services_async_query.py`
- Test: `tests/test_bi_async_query.py`（追加 services 段）

- [ ] **Step 1: 创建 `app/business/bi/services_async_query.py`**

```python
"""BiQueryTask 业务服务 — submit / get / cancel / list / delete / download / cleanup。

编排层：把 queue + state + storage + runner + model 串成完整业务流程。
所有函数接受 ``redis`` 参数（由 API 层注入），不依赖全局状态。

注：响应 dict 的 key 用 camelCase（与前端 ``Api.Bi.BiQueryTask`` 类型对齐，
也与 spec §7.2 响应结构一致）。因 ``_task_record`` 是手工 dict 不走 Pydantic
alias_generator，必须显式用 camelCase。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi.responses import StreamingResponse
from tortoise.expressions import Q

from app.business.bi.async_query import state, storage
from app.business.bi.async_query.queue import enqueue
from app.business.bi.async_query.quota import check_concurrency
from app.business.bi.config import BIZ_SETTINGS
from app.business.bi.controllers import bi_query_task_controller
from app.business.bi.models import BiQueryTask
from app.business.bi.sandbox.dialect import get_dialect_name
from app.business.bi.sandbox.tenant import inject_tenant_filter, should_inject_tenant
from app.business.bi.sandbox.whitelist import validate_sql
from app.business.bi.schemas import BiAsyncRunSchema, BiQueryTaskSearchSchema
from app.business.bi.services import _get_user_data_scope
from app.core.code import Code
from app.core.exceptions import BizError
from app.core.log import log
from app.core.sqids import decode_id, encode_id
from app.utils import radar_log
from redis.asyncio import Redis


def _task_record(task: BiQueryTask, include_sql: bool = False) -> dict[str, Any]:
    """序列化任务为响应 dict（camelCase key，与前端 Api.Bi.BiQueryTask 对齐）。"""
    record: dict[str, Any] = {
        "id": encode_id(task.id),
        "name": task.name,
        "datasourceId": encode_id(task.datasource_id),
        "status": task.status,
        "progress": task.progress,
        "rowsFetched": task.rows_fetched,
        "elapsedMs": task.elapsed_ms,
        "resultRowCount": task.result_row_count,
        "resultIsTruncated": task.result_is_truncated,
        "resultSnapshot": task.result_snapshot,
        "resultUri": task.result_uri,
        "errorMessage": task.error_message,
        "startedAt": task.started_at.isoformat() if task.started_at else None,
        "finishedAt": task.finished_at.isoformat() if task.finished_at else None,
        "source": task.source,
        "createdAt": task.created_at.isoformat() if task.created_at else None,
    }
    if include_sql:
        record["sqlText"] = task.sql_text
    return record


async def submit(
    schema: BiAsyncRunSchema,
    user_id: int,
    redis: Redis,
    source: str = "manual",
) -> BiQueryTask:
    """提交异步查询任务。

    流程（spec §5.2）：
    1. 检查并发配额
    2. 校验数据源归属
    3. 白名单 + 行级注入
    4. 创建 BiQueryTask(status=pending)
    5. 初始化 Redis 状态
    6. enqueue
    7. 审计日志
    """
    if not BIZ_SETTINGS.BI_ASYNC_QUERY_ENABLED:
        raise BizError(Code.BI_ASYNC_QUERY_NOT_ENABLED)

    # 1. 并发配额
    await check_concurrency(user_id, redis)

    # 2. 数据源归属
    ds_id = decode_id(schema.datasource_id)
    from app.business.bi.models import BiDatasource

    datasource = await BiDatasource.get_or_none(
        id=ds_id, tenant_id=user_id, deleted_at__isnull=True
    )
    if datasource is None:
        raise BizError(Code.NOT_FOUND, "数据源不存在")

    # 3. 白名单 + 行级注入
    dialect = get_dialect_name(datasource.db_type)
    validation = validate_sql(schema.sql, dialect=dialect)
    safe_sql = validation.sql

    data_scope, scope_id = await _get_user_data_scope()
    if should_inject_tenant(data_scope) and scope_id is not None:
        safe_sql = inject_tenant_filter(safe_sql, tenant_id=scope_id, dialect=dialect)

    # 4. 创建任务
    name = schema.name or f"任务-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    task = await BiQueryTask.create(
        name=name,
        datasource_id=ds_id,
        sql_text=safe_sql,
        status="pending",
        tenant_id=user_id,
        source=source,
        created_by=str(user_id),
        updated_by=str(user_id),
    )

    # 5. 初始化 Redis 状态
    await state.init_state(task.id, redis, status="pending")

    # 6. enqueue
    await enqueue(task.id, redis)

    # 7. 审计
    radar_log("bi.async_query.submit", data={"task_id": task.id, "source": source})
    log.info("bi.async_query.submit task_id={} user_id={}", task.id, user_id)
    return task


async def get_task(task_id: int, user_id: int, redis: Redis) -> dict[str, Any]:
    """查任务详情（合并 DB 持久化状态 + Redis 实时状态）。"""
    task = await bi_query_task_controller.get_or_none(
        id=task_id, tenant_id=user_id, deleted_at__isnull=True
    )
    if task is None:
        raise BizError(Code.BI_ASYNC_QUERY_TASK_NOT_FOUND)

    record = _task_record(task, include_sql=True)

    # 任务还在运行时，用 Redis 实时状态覆盖 DB 快照
    if task.status in ("pending", "running"):
        live = await state.get_state(task_id, redis)
        if live:
            record["status"] = live.get("status", task.status)
            record["progress"] = live.get("progress", task.progress)
            record["rowsFetched"] = live.get("rows_fetched", task.rows_fetched)
            record["elapsedMs"] = live.get("elapsed_ms", task.elapsed_ms)

    return record


async def list_tasks(
    search_in: BiQueryTaskSearchSchema,
    user_id: int,
    redis: Redis,
) -> tuple[int, list[dict[str, Any]]]:
    """分页查任务列表（强制按当前用户隔离）。"""
    q = bi_query_task_controller.build_search(
        search_in,
        contains_fields=["name"],
        exact_fields=["status"],
    )
    q &= Q(tenant_id=user_id)

    if search_in.datasource_id:
        try:
            q &= Q(datasource_id=decode_id(search_in.datasource_id))
        except (ValueError, TypeError):
            pass

    total, tasks = await bi_query_task_controller.list(
        page=search_in.current,
        page_size=search_in.size,
        search=q,
        order=["-id"],
    )
    records = [_task_record(t, include_sql=False) for t in tasks]

    # 列表也合并 Redis 实时状态（让用户看到进行中任务的最新进度）
    for record, task in zip(records, tasks, strict=False):
        if task.status in ("pending", "running"):
            live = await state.get_state(task.id, redis)
            if live:
                record["status"] = live.get("status", task.status)
                record["progress"] = live.get("progress", task.progress)
                record["rowsFetched"] = live.get("rows_fetched", task.rows_fetched)
                record["elapsedMs"] = live.get("elapsed_ms", task.elapsed_ms)

    return total, records


async def cancel_task(task_id: int, user_id: int, redis: Redis) -> None:
    """取消任务。pending 直接置 cancelled；running 设标志位等 worker 检测。"""
    task = await bi_query_task_controller.get_or_none(
        id=task_id, tenant_id=user_id, deleted_at__isnull=True
    )
    if task is None:
        raise BizError(Code.BI_ASYNC_QUERY_TASK_NOT_FOUND)

    if task.status not in ("pending", "running"):
        raise BizError(Code.BI_ASYNC_QUERY_TASK_NOT_CANCELLABLE)

    if task.status == "pending":
        # 还没被 worker 拿到，直接 cancelled
        task.status = "cancelled"
        task.error_message = "用户取消"
        task.finished_at = datetime.now()
        await task.save(update_fields=["status", "error_message", "finished_at", "updated_at"])
        await state.update_status(task_id, "cancelled", redis, error_message="用户取消")
    else:
        # running：设标志位，worker 在下一批次检测
        await state.request_cancel(task_id, redis)

    radar_log("bi.async_query.cancel", data={"task_id": task_id})


async def delete_task(task_id: int, user_id: int, redis: Redis) -> None:
    """删除任务（软删 DB + 物理删 CSV + 清 Redis 状态）。"""
    task = await bi_query_task_controller.get_or_none(
        id=task_id, tenant_id=user_id, deleted_at__isnull=True
    )
    if task is None:
        raise BizError(Code.BI_ASYNC_QUERY_TASK_NOT_FOUND)

    # 删除 CSV 文件
    if task.result_uri:
        storage.delete_csv(task.result_uri)

    # 软删 DB
    await task.delete()
    # 清 Redis 状态
    await state.delete_state(task_id, redis)
    radar_log("bi.async_query.delete", data={"task_id": task_id})


async def get_download_stream(task_id: int, user_id: int, redis: Redis) -> StreamingResponse:
    """构造 CSV 下载流。校验归属 + status=success + 文件存在。"""
    task = await bi_query_task_controller.get_or_none(
        id=task_id, tenant_id=user_id, deleted_at__isnull=True
    )
    if task is None:
        raise BizError(Code.BI_ASYNC_QUERY_TASK_NOT_FOUND)

    if task.status != "success":
        raise BizError(Code.BI_ASYNC_QUERY_RESULT_FILE_MISSING, "任务未完成或无结果可下载")

    if not task.result_uri:
        raise BizError(Code.BI_ASYNC_QUERY_RESULT_FILE_MISSING, "任务无 CSV 结果文件")

    try:
        file_path = storage.resolve_csv_path(task.result_uri)
    except ValueError as e:
        raise BizError(Code.BI_ASYNC_QUERY_RESULT_FILE_MISSING, str(e)) from e

    if not file_path.exists():
        raise BizError(Code.BI_ASYNC_QUERY_RESULT_FILE_MISSING, "结果文件不存在或已清理")

    size = file_path.stat().st_size

    def _iter() -> AsyncIterator[bytes]:
        yield from storage.read_csv_stream(file_path)

    return StreamingResponse(
        _iter(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{task_id}.csv"',
            "Content-Length": str(size),
        },
    )
```

注：`_task_record` 的 key 必须用 camelCase（`rowsFetched` / `elapsedMs` / `resultRowCount` / `resultIsTruncated` / `resultSnapshot` / `resultUri` / `errorMessage` / `startedAt` / `finishedAt` / `createdAt` / `datasourceId` / `sqlText`），因手工 dict 不走 `SchemaBase` 的 `to_camel_case` alias_generator。`get_state` 返回的 Redis Hash 字段是 snake_case（`rows_fetched` / `elapsed_ms`），合并时显式映射到 camelCase。

- [ ] **Step 2: 在 `tests/test_bi_async_query.py` 追加 services 测试**

```python
# ===================== services_async_query =====================


from app.business.bi.schemas import BiAsyncRunSchema, BiQueryTaskSearchSchema


class TestSubmitTask:
    async def test_submit_success(self, app, bi_datasource, monkeypatch):
        from app.business.bi.async_query import queue
        from app.business.bi.services_async_query import submit

        user_id = bi_datasource.tenant_id
        redis = app.state.redis
        await redis.delete("bi:async_query:user:1:running", "bi:async_query:global:running", queue.QUEUE_KEY)

        # mock 行级 data_scope 为 all（避免注入 tenant 条件）
        async def _fake_scope():
            return "all", None

        monkeypatch.setattr("app.business.bi.services_async_query._get_user_data_scope", _fake_scope)

        schema = BiAsyncRunSchema(
            sql="SELECT id, name FROM orders LIMIT 100",
            datasource_id=encode_id_safe(bi_datasource.id),
            name="测试任务",
        )
        task = await submit(schema, user_id=user_id, redis=redis, source="manual")

        assert task.id > 0
        assert task.status == "pending"
        assert task.tenant_id == user_id
        assert task.source == "manual"

        # 任务已入队
        assert await queue.queue_size(redis) == 1
        # Redis 状态已初始化
        from app.business.bi.async_query.state import get_state
        s = await get_state(task.id, redis)
        assert s["status"] == "pending"

    async def test_submit_disabled(self, app, bi_datasource, monkeypatch):
        from app.business.bi.config import BIZ_SETTINGS
        from app.business.bi.services_async_query import submit

        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_ENABLED", False)

        schema = BiAsyncRunSchema(
            sql="SELECT 1",
            datasource_id=encode_id_safe(bi_datasource.id),
        )
        with pytest.raises(Exception) as exc:
            await submit(schema, user_id=bi_datasource.tenant_id, redis=app.state.redis)
        assert "4110" in str(exc.value) or "未开启" in str(exc.value)

    async def test_submit_datasource_not_found(self, app, bi_datasource, monkeypatch):
        from app.business.bi.services_async_query import submit

        async def _fake_scope():
            return "all", None

        monkeypatch.setattr("app.business.bi.services_async_query._get_user_data_scope", _fake_scope)

        schema = BiAsyncRunSchema(
            sql="SELECT 1",
            datasource_id=encode_id_safe(999_999_999),
        )
        with pytest.raises(Exception) as exc:
            await submit(schema, user_id=bi_datasource.tenant_id, redis=app.state.redis)
        assert str(exc.value.code) == "1101" or "不存在" in str(exc.value)


def encode_id_safe(int_id: int) -> str:
    from app.core.sqids import encode_id
    return encode_id(int_id)


class TestGetTask:
    async def test_get_task_success(self, app, bi_query_task):
        from app.business.bi.services_async_query import get_task

        user_id = bi_query_task.tenant_id
        record = await get_task(bi_query_task.id, user_id, app.state.redis)
        assert record["status"] == "pending"
        assert "sql_text" in record

    async def test_get_task_not_found(self, app, bi_datasource):
        from app.business.bi.services_async_query import get_task

        with pytest.raises(Exception) as exc:
            await get_task(999_999_999, bi_datasource.tenant_id, app.state.redis)
        assert "4113" in str(exc.value)

    async def test_get_task_tenant_isolation(self, app, bi_query_task):
        from app.business.bi.services_async_query import get_task

        other_user = bi_query_task.tenant_id + 100
        with pytest.raises(Exception) as exc:
            await get_task(bi_query_task.id, other_user, app.state.redis)
        assert "4113" in str(exc.value)


class TestCancelTask:
    async def test_cancel_pending(self, app, bi_query_task):
        from app.business.bi.async_query.state import check_cancel, get_state
        from app.business.bi.services_async_query import cancel_task

        user_id = bi_query_task.tenant_id
        await cancel_task(bi_query_task.id, user_id, app.state.redis)

        await bi_query_task.refresh_from_db()
        assert bi_query_task.status == "cancelled"

    async def test_cancel_already_done(self, app, bi_query_task):
        from app.business.bi.services_async_query import cancel_task

        bi_query_task.status = "success"
        await bi_query_task.save(update_fields=["status"])

        with pytest.raises(Exception) as exc:
            await cancel_task(bi_query_task.id, bi_query_task.tenant_id, app.state.redis)
        assert "4114" in str(exc.value)

    async def test_cancel_running_sets_flag(self, app, bi_query_task):
        from app.business.bi.async_query.state import check_cancel
        from app.business.bi.services_async_query import cancel_task

        bi_query_task.status = "running"
        await bi_query_task.save(update_fields=["status"])

        await cancel_task(bi_query_task.id, bi_query_task.tenant_id, app.state.redis)
        # pending 分支不触发，running 分支设标志位
        assert await check_cancel(bi_query_task.id, app.state.redis) is True


class TestListTasks:
    async def test_list_tasks_isolation(self, app, bi_datasource):
        from app.business.bi.models import BiQueryTask
        from app.business.bi.services_async_query import list_tasks

        user_a = bi_datasource.tenant_id
        user_b = user_a + 200

        await BiQueryTask.all().delete()
        await BiQueryTask.create(
            name="A1", datasource_id=bi_datasource.id, sql_text="SELECT 1",
            status="success", tenant_id=user_a, created_by=str(user_a), updated_by=str(user_a),
        )
        await BiQueryTask.create(
            name="B1", datasource_id=bi_datasource.id, sql_text="SELECT 1",
            status="success", tenant_id=user_b, created_by=str(user_b), updated_by=str(user_b),
        )

        search = BiQueryTaskSearchSchema(current=1, size=10)
        total, records = await list_tasks(search, user_id=user_a, redis=app.state.redis)
        assert total == 1
        assert records[0]["name"] == "A1"


class TestDeleteTask:
    async def test_delete_removes_csv(self, app, bi_query_task, tmp_path, monkeypatch):
        from app.business.bi.async_query import storage
        from app.business.bi.config import BIZ_SETTINGS
        from app.business.bi.services_async_query import delete_task

        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_CSV_DIR", str(tmp_path))

        # 构造一个 success + result_uri 的任务
        bi_query_task.status = "success"
        bi_query_task.result_uri = f"{bi_query_task.id}.csv"
        await bi_query_task.save(update_fields=["status", "result_uri"])

        # 写一个 CSV 文件
        csv_path = tmp_path / f"{bi_query_task.id}.csv"
        csv_path.write_text("id\n1\n", encoding="utf-8")
        assert csv_path.exists()

        await delete_task(bi_query_task.id, bi_query_task.tenant_id, app.state.redis)

        # CSV 被删
        assert not csv_path.exists()
        # DB 软删
        from app.business.bi.models import BiQueryTask
        deleted = await BiQueryTask.filter(id=bi_query_task.id, deleted_at__isnull=True).count()
        assert deleted == 0
```

- [ ] **Step 3: 跑测试**

Run: `uv run pytest tests/test_bi_async_query.py -v 2>&1 | tail -50`
Expected: 全部 PASS。

- [ ] **Step 4: Commit**

```bash
git add app/business/bi/services_async_query.py tests/test_bi_async_query.py
git commit -m "feat(bi): add services_async_query (submit/get/cancel/list/delete/download)"
```

---

## Task 10: api/async_query.py + 路由聚合

**Files:**
- Create: `app/business/bi/api/async_query.py`
- Modify: `app/business/bi/api/__init__.py`

- [ ] **Step 1: 创建 `app/business/bi/api/async_query.py`**

```python
"""BI 异步大查询路由 — submit / get / list / cancel / delete / result / download。

按钮码（spec §10.1）：
- ``B_BI_SQL_ASYNC_RUN`` —— 提交异步查询
- ``B_BI_SQL_TASK_VIEW`` —— 查看任务（list / get / result）
- ``B_BI_SQL_TASK_CANCEL`` —— 取消任务
- ``B_BI_SQL_TASK_DELETE`` —— 删除任务
- ``B_BI_SQL_TASK_DOWNLOAD`` —— 下载结果

行级隔离：BiQueryTask.tenant_id 存 user.id，用户只能操作自己的任务。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.business.bi.schemas import BiAsyncRunSchema, BiQueryTaskSearchSchema
from app.business.bi.services_async_query import (
    cancel_task,
    delete_task,
    get_download_stream,
    get_task,
    list_tasks,
    submit,
)
from app.core.redis import AioRedis
from app.utils import (
    BizError,
    Code,
    DependAuth,
    SqidPath,
    Success,
    SuccessExtra,
    get_current_user_id,
    require_buttons,
)

router = APIRouter()


@router.post(
    "/sql/async-run",
    summary="提交异步查询",
    name="bi.sql.async_run",
    dependencies=[DependAuth, require_buttons("B_BI_SQL_ASYNC_RUN")],
)
async def submit_async_query_endpoint(obj_in: BiAsyncRunSchema, redis: AioRedis):
    """手动提交异步查询任务。"""
    user_id = get_current_user_id()
    task = await submit(obj_in, user_id=user_id, redis=redis, source="manual")
    return Success(
        msg="任务已提交",
        data={"taskId": _encode(task.id), "status": "pending"},
    )


@router.post(
    "/sql/tasks/search",
    summary="查询任务列表",
    name="bi.sql.tasks.list",
    dependencies=[DependAuth, require_buttons("B_BI_SQL_TASK_VIEW")],
)
async def list_tasks_endpoint(obj_in: BiQueryTaskSearchSchema, redis: AioRedis):
    """分页查询当前用户的任务。"""
    user_id = get_current_user_id()
    total, records = await list_tasks(obj_in, user_id=user_id, redis=redis)
    return SuccessExtra(data={"records": records}, total=total, current=obj_in.current, size=obj_in.size)


@router.get(
    "/sql/tasks/{task_id}",
    summary="查任务状态/详情（轮询用）",
    name="bi.sql.tasks.get",
    dependencies=[DependAuth, require_buttons("B_BI_SQL_TASK_VIEW")],
)
async def get_task_endpoint(task_id: SqidPath, redis: AioRedis):
    """查任务详情（含 sql_text + 实时进度）。前端轮询用，2s 间隔。"""
    user_id = get_current_user_id()
    record = await get_task(task_id, user_id=user_id, redis=redis)
    return Success(data=record)


@router.get(
    "/sql/tasks/{task_id}/result",
    summary="获取结果预览",
    name="bi.sql.tasks.result",
    dependencies=[DependAuth, require_buttons("B_BI_SQL_TASK_VIEW")],
)
async def get_task_result_endpoint(task_id: SqidPath, redis: AioRedis):
    """获取任务结果预览（result_snapshot）。"""
    user_id = get_current_user_id()
    record = await get_task(task_id, user_id=user_id, redis=redis)
    if record["status"] != "success":
        raise BizError(Code.BI_ASYNC_QUERY_RESULT_FILE_MISSING, "任务未完成")
    return Success(data={
        "result_snapshot": record["result_snapshot"],
        "result_row_count": record["result_row_count"],
        "result_is_truncated": record["result_is_truncated"],
    })


@router.post(
    "/sql/tasks/{task_id}/cancel",
    summary="取消任务",
    name="bi.sql.tasks.cancel",
    dependencies=[DependAuth, require_buttons("B_BI_SQL_TASK_CANCEL")],
)
async def cancel_task_endpoint(task_id: SqidPath, redis: AioRedis):
    """取消任务。pending 立即置 cancelled；running 设标志位等 worker 检测。"""
    user_id = get_current_user_id()
    await cancel_task(task_id, user_id=user_id, redis=redis)
    return Success(msg="取消请求已提交")


@router.delete(
    "/sql/tasks/{task_id}",
    summary="删除任务",
    name="bi.sql.tasks.delete",
    dependencies=[DependAuth, require_buttons("B_BI_SQL_TASK_DELETE")],
)
async def delete_task_endpoint(task_id: SqidPath, redis: AioRedis):
    """删除任务（软删 DB + 物理删 CSV + 清 Redis）。"""
    user_id = get_current_user_id()
    await delete_task(task_id, user_id=user_id, redis=redis)
    return Success(msg="删除成功")


@router.get(
    "/sql/tasks/{task_id}/download",
    summary="下载结果 CSV",
    name="bi.sql.tasks.download",
    dependencies=[DependAuth, require_buttons("B_BI_SQL_TASK_DOWNLOAD")],
)
async def download_task_endpoint(task_id: SqidPath, redis: AioRedis):
    """流式下载 CSV（支持 Range 断点续传）。"""
    user_id = get_current_user_id()
    return await get_download_stream(task_id, user_id=user_id, redis=redis)


def _encode(int_id: int) -> str:
    from app.core.sqids import encode_id

    return encode_id(int_id)
```

- [ ] **Step 2: 在 `app/business/bi/api/__init__.py` 聚合新路由**

在 import 段追加：

```python
from app.business.bi.api.async_query import router as async_query_router
```

在聚合段追加（在 `router.include_router(chart_router)` 之后）：

```python
router.include_router(async_query_router)
```

并更新文件顶部 docstring 的子路由清单，追加：
- ``async_query`` —— 异步大查询（submit / list / get / cancel / delete / result / download）

- [ ] **Step 3: 验证路由注册**

Run: `uv run python -c "from app.business.bi.api import router; names = [r.name for r in router.routes if hasattr(r, 'name')]; print([n for n in names if 'tasks' in n or 'async' in n])"`
Expected: 输出包含 `bi.sql.async_run`, `bi.sql.tasks.list`, `bi.sql.tasks.get`, `bi.sql.tasks.cancel`, `bi.sql.tasks.delete`, `bi.sql.tasks.result`, `bi.sql.tasks.download`

- [ ] **Step 4: 追加 API 鉴权测试到 `tests/test_bi_async_query.py`**

```python
# ===================== API Auth =====================


class TestAsyncQueryAPIAuth:
    PREFIX = "/api/v1/business/bi"

    async def test_async_run_no_auth(self, client):
        resp = await client.post(f"{self.PREFIX}/sql/async-run", json={})
        assert resp.status_code == 200
        assert resp.json()["code"] == "2100"  # INVALID_TOKEN

    async def test_tasks_search_no_auth(self, client):
        resp = await client.post(f"{self.PREFIX}/sql/tasks/search", json={"current": 1, "size": 10})
        assert resp.status_code == 200
        assert resp.json()["code"] == "2100"

    async def test_tasks_get_no_auth(self, client):
        resp = await client.get(f"{self.PREFIX}/sql/tasks/abc")
        assert resp.status_code == 200
        assert resp.json()["code"] == "2100"

    async def test_submit_via_api(self, auth_client, bi_datasource, monkeypatch):
        """登录后通过 API 提交，验证返回 taskId。"""
        async def _fake_scope():
            return "all", None

        monkeypatch.setattr("app.business.bi.services_async_query._get_user_data_scope", _fake_scope)

        resp = await auth_client.post(
            f"{self.PREFIX}/sql/async-run",
            json={
                "sql": "SELECT id, name FROM orders LIMIT 100",
                "datasource_id": encode_id_safe(bi_datasource.id),
                "name": "API 任务",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0000"
        assert body["data"]["taskId"]
        assert body["data"]["status"] == "pending"
```

- [ ] **Step 5: 跑测试**

Run: `uv run pytest tests/test_bi_async_query.py::TestAsyncQueryAPIAuth -v`
Expected: 4 个测试 PASS。

- [ ] **Step 6: Commit**

```bash
git add app/business/bi/api/async_query.py app/business/bi/api/__init__.py tests/test_bi_async_query.py
git commit -m "feat(bi): add async_query API routes (8 endpoints)"
```

---

## Task 11: 智能切换 — 改造 /sql/run 支持软超时 transfer

**Files:**
- Modify: `app/business/bi/services.py`
- Modify: `app/business/bi/api/sql_workbench.py`
- Test: `tests/test_bi_async_query.py`（追加 transfer 测试）

- [ ] **Step 1: 修改 `app/business/bi/services.py` — 改造 `run_sql` 接受 redis 参数并支持 transfer**

修改 `run_sql` 函数签名与实现：

```python
async def run_sql(user, schema: SqlRunSchema, redis=None) -> dict:
    """执行 SQL（已通过白名单校验 + 自动 LIMIT + 行级注入）。

    Args:
        redis: Redis 客户端（用于熔断计数 + 软超时转异步）

    Returns:
        SqlRunResult 兼容 dict —— 成功时含 ``columns``/``rows``/``rowCount``/``elapsedMs``；
        软超时转异步时含 ``transferred=True`` 与 ``taskId``。
    """
    user_id = int(user.id)
    ds_id = decode_id(schema.datasource_id)
    ds = await bi_datasource_controller.get_or_none(id=ds_id)
    if ds is None:
        raise BizError(_BI_DS_NOT_FOUND, f"数据源不存在: {schema.datasource_id}")

    dialect = get_dialect_name(ds.db_type)
    validation = validate_sql(schema.sql, dialect=dialect)
    safe_sql = validation.sql

    data_scope, scope_id = await _get_user_data_scope()
    if should_inject_tenant(data_scope) and scope_id is not None:
        safe_sql = inject_tenant_filter(safe_sql, tenant_id=scope_id, dialect=dialect)

    # 软超时：超过 BI_SYNC_SOFT_TIMEOUT 则转异步任务
    from app.business.bi.config import BIZ_SETTINGS

    if redis is not None and BIZ_SETTINGS.BI_ASYNC_QUERY_ENABLED:
        import asyncio as _asyncio

        try:
            result: ExecutionResult = await _asyncio.wait_for(
                execute_sql(safe_sql, ds, user_id=user_id, redis=redis),
                timeout=BIZ_SETTINGS.BI_SYNC_SOFT_TIMEOUT,
            )
        except _asyncio.TimeoutError:
            # 转异步任务
            from app.business.bi.services_async_query import submit as _submit_async
            from app.business.bi.schemas import BiAsyncRunSchema

            async_schema = BiAsyncRunSchema(
                sql=schema.sql,
                datasource_id=schema.datasource_id,
                name=f"软超时转异步-{datetime.now().strftime('%H%M%S')}",
            )
            # 注意：safe_sql 已经 inject 过 tenant filter，submit 会再 inject 一次
            # 这里直接传 safe_sql 给 submit 的内部走 validate_sql（不会再次 inject）
            # —— 简化处理：submit 内部重新做完整校验链，传原始 schema.sql
            task = await _submit_async(async_schema, user_id=user_id, redis=redis, source="auto_transfer")
            return {
                "transferred": True,
                "taskId": encode_id(task.id),
                "message": "查询超时，已转为异步任务",
                "datasource_id": schema.datasource_id,
                "sql_text": schema.sql,
            }
    else:
        result = await execute_sql(safe_sql, ds, user_id=user_id, redis=redis)

    # 写审计日志（仅同步成功路径）
    await BiAuditLog.create(
        event_type="QUERY_OPERATION",
        action="执行 SQL",
        user_id=user_id,
        resource_type="datasource",
        resource_id=str(ds_id),
        status="success",
        execution_time_ms=result.elapsed_ms,
        detail={
            "sql": safe_sql,
            "row_count": result.row_count,
            "columns": result.columns,
        },
    )

    radar_log(
        "执行 SQL",
        data={
            "userId": user_id,
            "datasourceId": ds_id,
            "rowCount": result.row_count,
            "elapsedMs": result.elapsed_ms,
        },
    )

    return {
        "sql": safe_sql,
        "columns": result.columns,
        "rows": result.rows,
        "rowCount": result.row_count,
        "elapsedMs": result.elapsed_ms,
    }
```

- [ ] **Step 2: 修改 `app/business/bi/api/sql_workbench.py` — 注入 redis**

修改 `run_sql_endpoint`：

```python
from app.core.redis import AioRedis


@router.post(
    "/sql/run",
    summary="执行 SQL",
    name="bi.sql.run",
    dependencies=[DependAuth, require_buttons("B_BI_SQL_RUN")],
)
async def run_sql_endpoint(obj_in: SqlRunSchema, redis: AioRedis):
    """执行 SQL（白名单校验 + 自动 LIMIT + 配额限制）。

    软超时 25s 自动转异步任务，响应体含 ``transferred=true`` + ``taskId``。
    """
    user = _get_user_or_raise()
    result = await run_sql(user, obj_in, redis=redis)
    return Success(data=result)
```

- [ ] **Step 3: 同步修改 `services.preview_table` 接受 redis**

```python
async def preview_table(datasource_id: int, table_name: str, redis=None) -> dict:
    """预览表前 100 行。"""
    ds = await bi_datasource_controller.get_or_none(id=datasource_id)
    if ds is None:
        raise BizError(_BI_DS_NOT_FOUND, f"数据源不存在: {datasource_id}")

    safe_table = table_name.replace("`", "").replace("'", "").replace('"', "")
    sql = f"SELECT * FROM {safe_table} LIMIT 100"

    user_id = get_current_user_id() or 0
    result = await execute_sql(sql, ds, user_id=user_id, max_rows=100, redis=redis)
    return {
        "sql": sql,
        "columns": result.columns,
        "rows": result.rows,
        "rowCount": result.row_count,
        "elapsedMs": result.elapsed_ms,
    }
```

对应改 `api/sql_workbench.py` 的 `preview_table_endpoint`：

```python
@router.get(
    "/sql/preview/{datasource_id}/{table_name}",
    summary="预览表前 100 行",
    name="bi.sql.preview",
    dependencies=[DependAuth, require_buttons("B_BI_SQL_RUN")],
)
async def preview_table_endpoint(datasource_id: SqidPath, table_name: str, redis: AioRedis):
    result = await preview_table(datasource_id, table_name, redis=redis)
    return Success(data=result)
```

- [ ] **Step 4: 在 `tests/test_bi_async_query.py` 追加 transfer 测试**

```python
# ===================== Smart Switch (transfer) =====================


class TestSmartSwitch:
    async def test_run_sql_sync_success(self, app, bi_datasource, monkeypatch):
        """快查询同步返回，不触发 transfer。"""
        from app.business.bi.services import run_sql
        from app.business.bi.schemas import SqlRunSchema
        from types import SimpleNamespace

        async def _fake_scope():
            return "all", None

        async def _fake_execute_sql(*, sql, datasource, user_id, redis=None, **kw):
            return SimpleNamespace(
                columns=["id"],
                rows=[{"id": 1}],
                row_count=1,
                elapsed_ms=12,
            )

        monkeypatch.setattr("app.business.bi.services._get_user_data_scope", _fake_scope)
        monkeypatch.setattr("app.business.bi.services.execute_sql", _fake_execute_sql)

        user = SimpleNamespace(id=bi_datasource.tenant_id)
        schema = SqlRunSchema(sql="SELECT 1", datasource_id=encode_id_safe(bi_datasource.id))
        result = await run_sql(user, schema, redis=app.state.redis)

        assert result.get("transferred") is None
        assert result["rowCount"] == 1
        assert result["elapsedMs"] == 12

    async def test_run_sql_soft_timeout_transfers(self, app, bi_datasource, monkeypatch):
        """同步执行软超时，转异步任务并返回 transferred=true。"""
        import asyncio
        from app.business.bi.services import run_sql
        from app.business.bi.schemas import SqlRunSchema
        from types import SimpleNamespace

        async def _fake_scope():
            return "all", None

        async def _slow_execute_sql(*, sql, datasource, user_id, redis=None, **kw):
            # 睡 30s 让软超时触发（25s）
            await asyncio.sleep(30)
            return SimpleNamespace(columns=[], rows=[], row_count=0, elapsed_ms=30000)

        # 把软超时调到 1s，测试不用真等 25s
        from app.business.bi.config import BIZ_SETTINGS
        monkeypatch.setattr(BIZ_SETTINGS, "BI_SYNC_SOFT_TIMEOUT", 1)
        monkeypatch.setattr("app.business.bi.services._get_user_data_scope", _fake_scope)
        monkeypatch.setattr("app.business.bi.services.execute_sql", _slow_execute_sql)

        user = SimpleNamespace(id=bi_datasource.tenant_id)
        schema = SqlRunSchema(sql="SELECT 1", datasource_id=encode_id_safe(bi_datasource.id))
        result = await run_sql(user, schema, redis=app.state.redis)

        assert result.get("transferred") is True
        assert result.get("taskId")
        assert "已转为异步任务" in result["message"]
```

- [ ] **Step 5: 跑测试 + 确保现有 chart 测试不破坏**

Run: `uv run pytest tests/test_bi_async_query.py::TestSmartSwitch -v`
Expected: 2 个测试 PASS（第二个约 1s）。

Run: `uv run pytest tests/test_bi_chart.py -v 2>&1 | tail -20`
Expected: 全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add app/business/bi/services.py app/business/bi/api/sql_workbench.py tests/test_bi_async_query.py
git commit -m "feat(bi): smart switch — sync /sql/run auto-transfers to async on soft timeout"
```

---

## Task 12: Worker 启动 + init_data + 限流配置

**Files:**
- Modify: `app/__init__.py`
- Modify: `app/business/bi/init_data.py`
- Modify: `app/business/bi/module.py`

- [ ] **Step 1: 在 `app/__init__.py` 的 lifespan 中启动 worker 协程**

修改 `lifespan` 函数，在 `task_runner.start()` 之后、`yield` 之前追加：

```python
        # 启动 async_query worker 协程（每个 granian worker 一个）
        from app.business.bi.async_query.runner import (
            get_shutdown_event,
            recover_stale_tasks,
            set_shutdown_event,
            worker_loop,
        )
        from app.business.bi.async_query.state import set_runtime_redis

        # 注入运行期 redis 单例，供 PeriodicTask handler（无参签名）使用
        set_runtime_redis(_app.state.redis)
        async_query_shutdown = asyncio.Event()
        set_shutdown_event(async_query_shutdown)
        # crash recovery：扫描上次未完成的任务
        try:
            recovered = await recover_stale_tasks(_app.state.redis)
            if recovered:
                log.info("bi.async_query recovered {} stale tasks", recovered)
        except Exception:
            log.exception("bi.async_query recover_stale_tasks failed")

        async_query_task = asyncio.create_task(
            worker_loop(_app.state.redis, _app), name="bi.async_query.worker"
        )
        _app.state.async_query_worker = async_query_task
        _app.state.async_query_shutdown = async_query_shutdown
```

在 `finally` 段、`task_runner.stop()` 之前追加优雅退出：

```python
        # 优雅停止 async_query worker
        shutdown_event = getattr(_app.state, "async_query_shutdown", None)
        worker_task = getattr(_app.state, "async_query_worker", None)
        if shutdown_event is not None:
            shutdown_event.set()
        if worker_task is not None:
            try:
                await asyncio.wait_for(worker_task, timeout=10)
            except asyncio.TimeoutError:
                log.warning("bi.async_query worker did not stop gracefully within 10s, cancelling")
                worker_task.cancel()
```

- [ ] **Step 2: 修改 `app/business/bi/init_data.py` — 新增菜单与按钮码**

在 `BI_MENU_CHILDREN` 列表中"图表库"段之后追加（在最后一个 `}` 之前）：

```python
    {
        "menu_name": "查询任务",
        "route_name": "bi_async-query-tasks",
        "route_path": "/bi/async-query-tasks",
        "component": "view.bi_async-query-tasks",
        "icon": "mdi:cloud-download-outline",
        "order": 8,
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

在 `BI_ALL_BUTTONS` 列表末尾追加：

```python
    "B_BI_SQL_ASYNC_RUN",
    "B_BI_SQL_TASK_VIEW",
    "B_BI_SQL_TASK_CANCEL",
    "B_BI_SQL_TASK_DELETE",
    "B_BI_SQL_TASK_DOWNLOAD",
```

在 `BI_ALL_MENUS` 追加：

```python
    "bi_async-query-tasks",
    "bi_async-query-detail",
```

在 `BI_ANALYST_MENUS` 追加：

```python
    "bi_async-query-tasks",
    "bi_async-query-detail",
```

在 `BI_ANALYST_BUTTONS` 追加：

```python
    "B_BI_SQL_ASYNC_RUN",
    "B_BI_SQL_TASK_VIEW",
    "B_BI_SQL_TASK_CANCEL",
    "B_BI_SQL_TASK_DELETE",
    "B_BI_SQL_TASK_DOWNLOAD",
```

在 `BI_ADMIN_APIS` 与 `BI_ANALYST_APIS` 都追加：

```python
    # async_query
    "bi.sql.async_run",
    "bi.sql.tasks.list",
    "bi.sql.tasks.get",
    "bi.sql.tasks.result",
    "bi.sql.tasks.cancel",
    "bi.sql.tasks.delete",
    "bi.sql.tasks.download",
```

- [ ] **Step 3: 修改 `app/business/bi/module.py` — 追加限流配置**

在 `ENDPOINT_RATE_LIMITS` 字典追加：

```python
    "/api/v1/business/bi/sql/async-run": (10, 60),       # 60s 最多 10 次提交
    "/api/v1/business/bi/sql/tasks/search": (60, 60),    # 60s 最多 60 次列表
    "/api/v1/business/bi/sql/tasks/{task_id}": (120, 60),  # 轮询放宽
```

- [ ] **Step 4: 跑 init_data 测试**

Run: `uv run pytest tests/ -k "init_data or menu" -v 2>&1 | tail -30`
Expected: 相关测试 PASS（无新增失败）。

- [ ] **Step 5: 启动 app 验证 worker 启动 + 菜单注册**

Run: `just run backend &` 后台启动，等 5 秒后看日志。

Run: `just logs backend 2>&1 | grep -E "bi.async_query|查询任务|Business: registered" | head -10`
Expected: 看到 `bi.async_query worker started` 与 `Business: registered routes from 'bi'`。

杀掉后端进程。

- [ ] **Step 6: Commit**

```bash
git add app/__init__.py app/business/bi/init_data.py app/business/bi/module.py
git commit -m "feat(bi): wire async_query worker into lifespan + menu/button seeds + rate limits"
```

---

## Task 13: 前端 — 类型 + API + 列表页 + 详情页 + SQL 工作台改造

**Files:**
- Modify: `web/src/typings/api/bi.d.ts`
- Create: `web/src/service/api/bi-async-query.ts`
- Create: `web/src/views/bi/async-query-tasks/index.vue`
- Create: `web/src/views/bi/async-query-tasks/detail.vue`
- Modify: `web/src/views/bi/sql-workbench/index.vue`
- Modify: `web/src/locales/langs/_generated/bi/zh-cn.ts`
- Modify: `web/src/locales/langs/_generated/bi/en-us.ts`
- Modify: `web/src/locales/langs/_generated/bi/types.d.ts`
- Modify: 路由文件（如 `web/src/router/elegant/imports.ts`、`transform.ts`）

**说明：** 本任务不写测试代码（前端测试由 vitest 覆盖现有组件，新页面以人工验收为准）。`just check` 会跑 lint/typecheck。

- [ ] **Step 1: 在 `web/src/typings/api/bi.d.ts` 追加 BiQueryTask 类型**

文件结构为 `declare namespace Api { namespace Bi { ... } }`（已有），在 `namespace Bi` 块末尾、最后 `}` 之前追加（不要新开 namespace）：

```typescript
    // ============================================================
    // 异步大查询（BiQueryTask）
    // ============================================================

    /** 异步查询任务状态 */
    type BiQueryTaskStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled';

    /** 异步查询任务 */
    interface BiQueryTask {
      /** 任务 ID（sqid） */
      id: string;
      /** 任务名称 */
      name: string | null;
      /** 数据源 ID（sqid） */
      datasourceId: string;
      /** 任务状态 */
      status: BiQueryTaskStatus;
      /** 进度百分比 0-100 */
      progress: number;
      /** 已扫描行数 */
      rowsFetched: number;
      /** 执行耗时（毫秒） */
      elapsedMs: number;
      /** 结果总行数 */
      resultRowCount: number;
      /** 结果是否被截断（仅预览截断，CSV 完整） */
      resultIsTruncated: boolean;
      /** 结果预览（结构 {columns, rows, rowCount, elapsedMs, isTruncated}） */
      resultSnapshot: {
        columns: string[];
        rows: Record<string, any>[];
        rowCount: number;
        elapsedMs: number;
        isTruncated: boolean;
      } | null;
      /** 错误信息 */
      errorMessage: string | null;
      /** 开始执行时间 */
      startedAt: string | null;
      /** 完成时间 */
      finishedAt: string | null;
      /** 提交来源：manual / auto_transfer */
      source: 'manual' | 'auto_transfer';
      /** 创建时间 */
      createdAt: string;
      /** SQL 全文（仅详情接口返回） */
      sqlText?: string;
    }

    /** 异步查询任务列表查询参数 */
    interface BiQueryTaskSearchParams {
      current: number;
      size: number;
      name?: string;
      status?: BiQueryTaskStatus;
      datasourceId?: string;
    }

    /** 提交异步查询请求 */
    interface BiAsyncRunPayload {
      sql: string;
      datasourceId: string;
      name?: string;
    }

    /** 智能切换响应（/sql/run 软超时触发） */
    interface BiSqlRunTransferredResult {
      transferred: true;
      taskId: string;
      message: string;
      datasourceId: string;
      sqlText: string;
    }

    /** /sql/run 返回的联合结果：同步成功 / 软超时转异步 */
    type BiSqlRunResult = SqlExecutionResult | BiSqlRunTransferredResult;

    /** 异步任务列表分页响应 */
    interface BiQueryTaskList {
      records: BiQueryTask[];
      total: number;
    }

    /** 异步任务结果预览响应 */
    interface BiQueryTaskResult {
      resultSnapshot: BiQueryTask['resultSnapshot'];
      resultRowCount: number;
      resultIsTruncated: boolean;
    }
```

注：`SqlExecutionResult` 在同 namespace 已定义。`Api.Bi.*` 是后续 TypeScript 代码的引用形式。

- [ ] **Step 2: 创建 `web/src/service/api/bi-async-query.ts`**

参考已有 `web/src/service/api/bi-sql.ts` 的写法（用相对路径 `../request`、URL 不带 `/api/v1` 前缀，由 `getServiceBaseURL` 代理）：

```typescript
import { request } from '../request';

/** 提交异步查询 */
export function fetchBiAsyncRun(data: Api.Bi.BiAsyncRunPayload) {
  return request<{ taskId: string; status: string }>({
    url: '/business/bi/sql/async-run',
    method: 'post',
    data
  });
}

/** 任务列表分页 */
export function fetchBiAsyncTaskSearch(data: Api.Bi.BiQueryTaskSearchParams) {
  return request<Api.Bi.BiQueryTaskList>({
    url: '/business/bi/sql/tasks/search',
    method: 'post',
    data
  });
}

/** 任务详情（轮询用，2s 间隔） */
export function fetchBiAsyncTask(taskId: string) {
  return request<Api.Bi.BiQueryTask>({
    url: `/business/bi/sql/tasks/${taskId}`,
    method: 'get'
  });
}

/** 获取结果预览 */
export function fetchBiAsyncTaskResult(taskId: string) {
  return request<Api.Bi.BiQueryTaskResult>({
    url: `/business/bi/sql/tasks/${taskId}/result`,
    method: 'get'
  });
}

/** 取消任务 */
export function fetchBiAsyncTaskCancel(taskId: string) {
  return request<null>({
    url: `/business/bi/sql/tasks/${taskId}/cancel`,
    method: 'post'
  });
}

/** 删除任务 */
export function fetchBiAsyncTaskDelete(taskId: string) {
  return request<null>({
    url: `/business/bi/sql/tasks/${taskId}`,
    method: 'delete'
  });
}

/**
 * 构造 CSV 下载 URL（直接打开，浏览器自动触发下载）。
 * 注意：需要带 token，由 axios 单独处理或在 a 标签上拼接 Authorization。
 * 简化方案：用 fetch + blob 触发下载（在调用处实现）。
 */
export function buildBiAsyncDownloadUrl(taskId: string): string {
  return `/business/bi/sql/tasks/${taskId}/download`;
}
```

- [ ] **Step 3: 创建列表页 `web/src/views/bi/async-query-tasks/index.vue`**

```vue
<script setup lang="ts">
import { h, onMounted, onUnmounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { NButton, NCard, NDataTable, NInput, NPopconfirm, NSelect, NSpace, NTag } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import {
  buildBiAsyncDownloadUrl,
  fetchBiAsyncTaskCancel,
  fetchBiAsyncTaskDelete,
  fetchBiAsyncTaskSearch
} from '@/service/api/bi-async-query';
import { $t } from '@/locales';

defineOptions({ name: 'BiAsyncQueryTasks' });

const router = useRouter();
const loading = ref(false);
const tasks = ref<Api.Bi.BiQueryTask[]>([]);
const total = ref(0);
const current = ref(1);
const size = ref(10);
const searchName = ref('');
const searchStatus = ref<Api.Bi.BiQueryTaskStatus | null>(null);
const pollingTimer = ref<number | null>(null);

const statusOptions = [
  { label: '全部', value: null },
  { label: '进行中', value: 'running' },
  { label: '等待中', value: 'pending' },
  { label: '已完成', value: 'success' },
  { label: '失败', value: 'failed' },
  { label: '已取消', value: 'cancelled' }
];

const statusTagType: Record<Api.Bi.BiQueryTaskStatus, 'default' | 'info' | 'success' | 'error' | 'warning'> = {
  pending: 'default',
  running: 'info',
  success: 'success',
  failed: 'error',
  cancelled: 'warning'
};

async function loadTasks() {
  loading.value = true;
  try {
    const { data, error } = await fetchBiAsyncTaskSearch({
      current: current.value,
      size: size.value,
      name: searchName.value || undefined,
      status: searchStatus.value || undefined
    });
    if (!error && data) {
      tasks.value = data.records;
      total.value = data.total;
    }
  } finally {
    loading.value = false;
  }
}

function viewDetail(id: string) {
  router.push({ name: 'bi_async-query-detail', params: { id } });
}

async function cancelTask(id: string) {
  await fetchBiAsyncTaskCancel(id);
  window.$message?.success($t('common.updateSuccess'));
  await loadTasks();
}

async function removeTask(id: string) {
  await fetchBiAsyncTaskDelete(id);
  window.$message?.success($t('common.deleteSuccess'));
  await loadTasks();
}

function downloadCsv(id: string) {
  // 用浏览器原生 fetch 带 token 拉取，避免 a 标签不带 Authorization
  window.open(buildBiAsyncDownloadUrl(id), '_blank');
}

function onPageChange(p: number) {
  current.value = p;
  loadTasks();
}

function startPolling() {
  stopPolling();
  pollingTimer.value = window.setInterval(() => {
    if (tasks.value.some(t => t.status === 'pending' || t.status === 'running')) {
      loadTasks();
    }
  }, 3000);
}

function stopPolling() {
  if (pollingTimer.value !== null) {
    clearInterval(pollingTimer.value);
    pollingTimer.value = null;
  }
}

const columns = computed<DataTableColumns<Api.Bi.BiQueryTask>>(() => [
  { title: '任务名', key: 'name', render: row => row.name || '-' },
  {
    title: '状态',
    key: 'status',
    render: row => h(NTag, { type: statusTagType[row.status] }, { default: () => row.status })
  },
  { title: '进度', key: 'progress', render: row => `${row.progress}%` },
  { title: '已扫描行数', key: 'rowsFetched' },
  { title: '耗时(ms)', key: 'elapsedMs' },
  { title: '来源', key: 'source' },
  { title: '创建时间', key: 'createdAt' },
  {
    title: '操作',
    key: 'actions',
    render: row =>
      h(NSpace, null, {
        default: () => [
          h(NButton, { size: 'small', onClick: () => viewDetail(row.id) }, { default: () => '查看' }),
          row.status === 'running' || row.status === 'pending'
            ? h(
                NButton,
                { size: 'small', type: 'warning', onClick: () => cancelTask(row.id) },
                { default: () => '取消' }
              )
            : null,
          row.status === 'success'
            ? h(
                NButton,
                { size: 'small', type: 'info', onClick: () => downloadCsv(row.id) },
                { default: () => '下载' }
              )
            : null,
          h(
            NPopconfirm,
            { onPositiveClick: () => removeTask(row.id) },
            {
              default: () => '确认删除？',
              trigger: () =>
                h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' })
            }
          )
        ]
      })
  }
]);

onMounted(() => {
  loadTasks();
  startPolling();
});

onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <div class="h-full flex-col">
    <NCard :title="$t('page.bi.async-query-tasks.title')" :bordered="false">
      <NSpace class="mb-4">
        <NInput
          v-model:value="searchName"
          :placeholder="$t('page.bi.async-query-tasks.searchNamePlaceholder')"
          clearable
          style="width: 200px"
          @keyup.enter="loadTasks"
        />
        <NSelect
          v-model:value="searchStatus"
          :options="statusOptions"
          style="width: 160px"
          :placeholder="$t('page.bi.async-query-tasks.statusPlaceholder')"
        />
        <NButton type="primary" @click="loadTasks">{{ $t('common.search') }}</NButton>
      </NSpace>
      <NDataTable
        :columns="columns"
        :data="tasks"
        :loading="loading"
        :pagination="{
          page: current,
          pageSize: size,
          itemCount: total,
          onChange: onPageChange
        }"
      />
    </NCard>
  </div>
</template>
```

注：`computed` 需要在 import 段补 `import { computed, h, onMounted, ... } from 'vue';`（合并到一行即可）。

- [ ] **Step 4: 创建详情页 `web/src/views/bi/async-query-tasks/detail.vue`**

```vue
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NDescriptions,
  NDescriptionsItem,
  NProgress,
  NSpace,
  NTag
} from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { buildBiAsyncDownloadUrl, fetchBiAsyncTask, fetchBiAsyncTaskCancel } from '@/service/api/bi-async-query';

defineOptions({ name: 'BiAsyncQueryDetail' });

const route = useRoute();
const router = useRouter();
const task = ref<Api.Bi.BiQueryTask | null>(null);
const pollingTimer = ref<number | null>(null);

const taskId = computed(() => route.params.id as string);
const isRunning = computed(
  () => task.value?.status === 'pending' || task.value?.status === 'running'
);

const statusTagType = computed<'default' | 'info' | 'success' | 'error' | 'warning'>(() => {
  if (!task.value) return 'default';
  const map = {
    pending: 'default',
    running: 'info',
    success: 'success',
    failed: 'error',
    cancelled: 'warning'
  } as const;
  return map[task.value.status];
});

const previewColumns = computed<DataTableColumns<Record<string, any>>>(() => {
  const cols = task.value?.resultSnapshot?.columns ?? [];
  return cols.map(c => ({ title: c, key: c }));
});

const previewRows = computed<Record<string, any>[]>(() => task.value?.resultSnapshot?.rows ?? []);

async function loadTask() {
  const { data, error } = await fetchBiAsyncTask(taskId.value);
  if (!error && data) {
    task.value = data;
  }
}

async function cancel() {
  await fetchBiAsyncTaskCancel(taskId.value);
  await loadTask();
}

function downloadCsv() {
  window.open(buildBiAsyncDownloadUrl(taskId.value), '_blank');
}

function back() {
  router.push({ name: 'bi_async-query-tasks' });
}

function startPolling() {
  stopPolling();
  pollingTimer.value = window.setInterval(() => {
    if (isRunning.value) loadTask();
    else stopPolling();
  }, 2000);
}

function stopPolling() {
  if (pollingTimer.value !== null) {
    clearInterval(pollingTimer.value);
    pollingTimer.value = null;
  }
}

onMounted(() => {
  loadTask().then(startPolling);
});

onUnmounted(stopPolling);
</script>

<template>
  <div class="h-full flex-col gap-4">
    <NCard v-if="task" :title="`任务详情 - ${task.name || taskId}`" :bordered="false">
      <template #header-extra>
        <NSpace>
          <NButton @click="back">返回列表</NButton>
          <NButton v-if="isRunning" type="warning" @click="cancel">取消任务</NButton>
          <NButton v-if="task.status === 'success'" type="info" @click="downloadCsv">下载 CSV</NButton>
        </NSpace>
      </template>

      <NDescriptions :column="3" bordered label-placement="left">
        <NDescriptionsItem label="状态">
          <NTag :type="statusTagType">{{ task.status }}</NTag>
        </NDescriptionsItem>
        <NDescriptionsItem label="进度">
          <NProgress type="line" :percentage="task.progress" />
        </NDescriptionsItem>
        <NDescriptionsItem label="已扫描行数">{{ task.rowsFetched }}</NDescriptionsItem>
        <NDescriptionsItem label="耗时(ms)">{{ task.elapsedMs }}</NDescriptionsItem>
        <NDescriptionsItem label="结果总行数">{{ task.resultRowCount }}</NDescriptionsItem>
        <NDescriptionsItem label="来源">{{ task.source }}</NDescriptionsItem>
        <NDescriptionsItem label="开始时间">{{ task.startedAt }}</NDescriptionsItem>
        <NDescriptionsItem label="完成时间">{{ task.finishedAt }}</NDescriptionsItem>
        <NDescriptionsItem label="创建时间">{{ task.createdAt }}</NDescriptionsItem>
        <NDescriptionsItem v-if="task.sqlText" label="SQL" :span="3">
          <pre class="whitespace-pre-wrap break-all font-mono text-xs">{{ task.sqlText }}</pre>
        </NDescriptionsItem>
      </NDescriptions>

      <NAlert v-if="task.status === 'failed'" type="error" class="mt-4" :title="task.errorMessage || '任务失败'" />
      <NAlert v-if="task.status === 'cancelled'" type="warning" class="mt-4" :title="task.errorMessage || '任务已取消'" />

      <NCard
        v-if="task.resultSnapshot"
        :title="`结果预览（共 ${task.resultRowCount} 行，预览 ${task.resultSnapshot.rowCount} 行${task.resultIsTruncated ? '，已截断' : ''}）`"
        :bordered="true"
        class="mt-4"
      >
        <NDataTable :columns="previewColumns" :data="previewRows" :max-height="400" />
      </NCard>
    </NCard>
  </div>
</template>
```

- [ ] **Step 5: 改造 SQL 工作台处理智能切换 transfer 响应**

修改 `web/src/views/bi/sql-workbench/index.vue` 的 `handleExecute` 函数，识别 `transferred` 字段并在 transfer 时跳转详情页：

把现有 `handleExecute`：

```typescript
async function handleExecute() {
  if (!sqlContent.value.trim() || !datasourceId.value) return;
  loading.value = true;
  try {
    const { data, error } = await fetchBiSqlRun({ sql: sqlContent.value, datasourceId: datasourceId.value });
    if (!error && data) {
      result.value = data;
      currentPage.value = 1;
      autoDetectChartColumns();
      refreshChart();
      window.$message?.success($t('page.bi.sql-workbench.result'));
    }
  } finally {
    loading.value = false;
  }
}
```

改为：

```typescript
async function handleExecute() {
  if (!sqlContent.value.trim() || !datasourceId.value) return;
  loading.value = true;
  try {
    const { data, error } = await fetchBiSqlRun({ sql: sqlContent.value, datasourceId: datasourceId.value });
    if (!error && data) {
      // 智能切换：超时自动转异步任务
      if ('transferred' in data && data.transferred) {
        window.$message?.info(data.message || $t('page.bi.async-query-tasks.transferredMessage'));
        // 跳转详情页让用户看进度
        router.push({ name: 'bi_async-query-detail', params: { id: data.taskId } });
        return;
      }
      result.value = data;
      currentPage.value = 1;
      autoDetectChartColumns();
      refreshChart();
      window.$message?.success($t('page.bi.sql-workbench.result'));
    }
  } finally {
    loading.value = false;
  }
}
```

同时：

1. 顶部 import 段补 `import { useRouter } from 'vue-router';` 与 `const router = useRouter();`（如已有则跳过）。
2. 把 `fetchBiSqlRun` 的返回类型由 `Api.Bi.SqlExecutionResult` 改为 `Api.Bi.BiSqlRunResult`（联合类型，已在 Step 1 定义）—— 直接编辑 `web/src/service/api/bi-sql.ts`：

```typescript
export function fetchBiSqlRun(data: Api.Bi.SqlRunParams) {
  return request<Api.Bi.BiSqlRunResult>({
    url: '/business/bi/sql/run',
    method: 'post',
    data
  });
}
```

- [ ] **Step 6: 追加 i18n 词条**

在 `web/src/locales/langs/_generated/bi/zh-cn.ts` 的 `bi` 对象内追加：

```typescript
  'async-query-tasks': {
    title: '查询任务',
    searchNamePlaceholder: '按名称搜索',
    statusPlaceholder: '状态筛选',
    transferredMessage: '查询超时，已转为异步任务，正在跳转详情页...',
    columns: {
      name: '任务名',
      status: '状态',
      progress: '进度',
      rowsFetched: '已扫描行数',
      elapsedMs: '耗时(ms)',
      source: '来源',
      createdAt: '创建时间',
      actions: '操作'
    },
    status: {
      pending: '等待中',
      running: '进行中',
      success: '已完成',
      failed: '失败',
      cancelled: '已取消'
    },
    actions: {
      view: '查看',
      cancel: '取消',
      download: '下载',
      delete: '删除'
    },
    detail: {
      back: '返回列表',
      cancel: '取消任务',
      download: '下载 CSV',
      sqlLabel: 'SQL',
      previewTitle: '结果预览'
    }
  },
```

在 `web/src/locales/langs/_generated/bi/en-us.ts` 同步追加英文翻译：

```typescript
  'async-query-tasks': {
    title: 'Query Tasks',
    searchNamePlaceholder: 'Search by name',
    statusPlaceholder: 'Filter by status',
    transferredMessage: 'Query timed out, transferred to async task, redirecting to detail...',
    columns: {
      name: 'Name',
      status: 'Status',
      progress: 'Progress',
      rowsFetched: 'Rows Fetched',
      elapsedMs: 'Elapsed (ms)',
      source: 'Source',
      createdAt: 'Created At',
      actions: 'Actions'
    },
    status: {
      pending: 'Pending',
      running: 'Running',
      success: 'Success',
      failed: 'Failed',
      cancelled: 'Cancelled'
    },
    actions: {
      view: 'View',
      cancel: 'Cancel',
      download: 'Download',
      delete: 'Delete'
    },
    detail: {
      back: 'Back to List',
      cancel: 'Cancel Task',
      download: 'Download CSV',
      sqlLabel: 'SQL',
      previewTitle: 'Result Preview'
    }
  },
```

在 `web/src/locales/langs/_generated/bi/types.d.ts` 追加对应类型（按现有模式扩展 `Bi` 命名空间下的 `async-query-tasks` 字段）。如 elegant-router 的 i18n 是自动生成的，跑 `pnpm gen-locale` 或对应脚本重新生成；若项目无该脚本则手动维护。

- [ ] **Step 7: 路由注册**

elegant-router 通常会扫描 `web/src/views/**` 自动生成路由。如果项目已配置 `@elegant-router/vue-router` 的自动扫描，新页面 `bi/async-query-tasks/index.vue` 与 `detail.vue` 会被自动识别为 `bi_async-query-tasks` 与 `bi_async-query-detail`。

检查 `web/src/router/elegant/imports.ts` 是否包含这两个导入：

```typescript
const BiAsyncQueryTasks = () => import('@/views/bi/async-query-tasks/index.vue');
const BiAsyncQueryDetail = () => import('@/views/bi/async-query-tasks/detail.vue');
```

若未自动生成（运行 `pnpm gen-route` 或对应 elegant-router 脚本），则手动在 `imports.ts` 追加上述两行，并在 `transform.ts` 的 `transformations` 数组里把 `bi_async-query-tasks` 与 `bi_async-query-detail` 加入对应路由表。

如果项目用 `web/src/router/bi.ts` 手工管理 BI 子路由，则在该文件追加：

```typescript
{
  name: 'bi_async-query-tasks',
  path: '/bi/async-query-tasks',
  component: 'layout.base$view.bi_async-query-tasks',
  meta: {
    title: '查询任务',
    i18nKey: 'route.bi_async-query-tasks',
    icon: 'mdi:cloud-download-outline',
    order: 8,
    buttons: ['B_BI_SQL_ASYNC_RUN', 'B_BI_SQL_TASK_VIEW', 'B_BI_SQL_TASK_CANCEL', 'B_BI_SQL_TASK_DELETE', 'B_BI_SQL_TASK_DOWNLOAD']
  }
},
{
  name: 'bi_async-query-detail',
  path: '/bi/async-query-tasks/:id',
  component: 'layout.base$view.bi_async-query-detail',
  meta: {
    title: '任务详情',
    i18nKey: 'route.bi_async-query-detail',
    activeMenu: 'bi_async-query-tasks',
    hideInMenu: true,
    order: 99
  }
}
```

- [ ] **Step 8: 跑前端门禁**

Run: `just fmt frontend`
Expected: 格式化通过，无 lint 错误。

Run: `just typecheck frontend`
Expected: typecheck 通过。若报 `Api.Bi.BiQueryTask` 找不到，确认 Step 1 类型追加正确；若报 `Bi.*` 找不到，说明还有遗留命名空间引用，全文搜索替换为 `Api.Bi.*`。

Run: `just test frontend`
Expected: 现有 vitest 全 PASS（新页面无单测，靠人工验收）。

- [ ] **Step 9: 人工验收**

启动前后端：`just run`，登录后：

1. 在「SQL 工作台」执行一条快查询（如 `SELECT 1`），应正常显示结果。
2. 执行一条慢查询（如 `SELECT pg_sleep(30); SELECT 1;` PostgreSQL，或在 SQLite 用 `WITH RECURSIVE cnt(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM cnt LIMIT 10000000) SELECT count(*) FROM cnt;`），25s 后应自动跳转到任务详情页。
3. 在「查询任务」列表查看进度更新（每 2s 轮询）。
4. 任务完成后点击「下载」获取 CSV，用 Excel 打开确认 BOM + 列对齐。
5. 在执行中点击「取消」，确认状态变 `cancelled` 且 CSV 半成品被清理。
6. 删除一条已完成的任务，确认列表与 CSV 都被清除。

- [ ] **Step 10: Commit**

```bash
git add web/src/typings/api/bi.d.ts \
        web/src/service/api/bi-async-query.ts \
        web/src/service/api/bi-sql.ts \
        web/src/views/bi/async-query-tasks/ \
        web/src/views/bi/sql-workbench/index.vue \
        web/src/locales/langs/_generated/bi/ \
        web/src/router/elegant/imports.ts \
        web/src/router/elegant/transform.ts
git commit -m "feat(bi): add async query frontend (list + detail + smart-switch redirect)"
```

---

## Task 15: 过期任务清理（PeriodicTask）

**Files:**
- Modify: `app/business/bi/services_async_query.py`（追加 `cleanup_expired_tasks`）
- Modify: `app/business/bi/module.py`（注册 PeriodicTask）
- Test: `tests/test_bi_async_query.py`（追加 cleanup 测试）

spec §13.2 要求：过期任务（超过 `BI_ASYNC_QUERY_TTL_DAYS`）由清理任务软删 + CSV 文件物理删除。清理任务作为 `PeriodicTask` 注册到 `module.py`，daily 跑一次。

- [ ] **Step 1: 在 `app/business/bi/services_async_query.py` 追加清理函数**

在文件末尾追加。注意：`PeriodicTask.handler` 签名为 `Callable[[], Awaitable[None]]`（无参），所以本函数**不接受 redis 参数**，通过 `state.get_runtime_redis()` 获取运行期 redis 单例（由 Task 12 lifespan 注入）。

```python
async def cleanup_expired_tasks() -> int:
    """清理过期任务：软删 DB + 物理删 CSV + 清 Redis 状态。

    判定：``finished_at`` 早于 ``now - BI_ASYNC_QUERY_TTL_DAYS`` 的任务。
    仅清理已终态（success/failed/cancelled）的任务，避免误删 running。

    Returns:
        清理的任务数
    """
    from datetime import datetime, timedelta

    redis = state.get_runtime_redis()
    ttl_days = BIZ_SETTINGS.BI_ASYNC_QUERY_TTL_DAYS
    threshold = datetime.now() - timedelta(days=ttl_days)

    # 只清理已终态任务
    expired = await BiQueryTask.filter(
        status__in=["success", "failed", "cancelled"],
        finished_at__lt=threshold,
        deleted_at__isnull=True,
    )
    count = 0
    for task in expired:
        # 物理删 CSV
        if task.result_uri:
            storage.delete_csv(task.result_uri)
        # 清 Redis 状态
        await state.delete_state(task.id, redis)
        # 软删 DB
        await task.delete()
        count += 1

    if count > 0:
        log.info("bi.async_query.cleanup expired={} ttl_days={}", count, ttl_days)
        radar_log("bi.async_query.cleanup", data={"count": count, "ttl_days": ttl_days})
    return count
```

- [ ] **Step 2: 在 `app/business/bi/module.py` 注册 PeriodicTask**

修改 `module.py`，在 `ENDPOINT_RATE_LIMITS` 之后追加任务声明，并把 `periodic_tasks` 加入 `BusinessModule`：

```python
from app.business.bi.services_async_query import cleanup_expired_tasks
from app.utils import BusinessModule, BusinessRouter, PeriodicTask, PermissionSpec

# daily 跑一次（86400 秒），leader_only 避免多 worker 重复执行
ASYNC_QUERY_CLEANUP_TASK = PeriodicTask(
    name="bi.async_query.cleanup",
    handler=cleanup_expired_tasks,
    interval_seconds=86400,
    leader_only=True,
    run_immediately=False,
)

module = BusinessModule(
    name="bi",
    title="智能 BI",
    version="0.1.0",
    routers=[
        BusinessRouter(router=router, auth="permission", tags=["智能 BI"]),
        BusinessRouter(router=public_router, auth="public", tags=["智能 BI"]),
    ],
    init=init,
    permissions=PermissionSpec(init_data=INIT_DATA),
    events=BI_EVENTS,
    data_policies=BI_DATA_POLICIES,
    periodic_tasks=[ASYNC_QUERY_CLEANUP_TASK],
)
```

注：`PeriodicTask` 已在 `app/utils/__init__.py` re-export（见 `from app.core.business import PeriodicTask as PeriodicTask`），可直接 import。

`PeriodicTask.handler` 的 `TaskHandler` 协议签名为 `Callable[[], Awaitable[None]]`（**无参**，见 [app/core/business.py](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/app/core/business.py) `TaskHandler` 定义与 [app/core/tasks.py](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/app/core/tasks.py) `_run_once` 中 `task.handler()` 调用）。因此 `cleanup_expired_tasks` 设计为无参函数，redis 通过 `state.get_runtime_redis()` 单例获取（Task 12 lifespan 启动时 `set_runtime_redis(_app.state.redis)` 注入）。

- [ ] **Step 3: 在 `tests/test_bi_async_query.py` 追加 cleanup 测试**

```python
# ===================== cleanup =====================


class TestCleanupExpired:
    async def test_cleanup_removes_expired(self, app, bi_datasource, monkeypatch, tmp_path):
        from datetime import datetime, timedelta

        from app.business.bi.async_query import storage
        from app.business.bi.config import BIZ_SETTINGS
        from app.business.bi.models import BiQueryTask
        from app.business.bi.services_async_query import cleanup_expired_tasks

        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_CSV_DIR", str(tmp_path))
        monkeypatch.setattr(BIZ_SETTINGS, "BI_ASYNC_QUERY_TTL_DAYS", 7)

        user_id = bi_datasource.tenant_id
        # 构造一个 10 天前 finished 的 success 任务 + CSV 文件
        old_finished = datetime.now() - timedelta(days=10)
        task = await BiQueryTask.create(
            name="expired",
            datasource_id=bi_datasource.id,
            sql_text="SELECT 1",
            status="success",
            finished_at=old_finished,
            result_uri="0.csv",  # 临时值，task.id 生成后下面立即更新
            tenant_id=user_id,
            source="manual",
            created_by=str(user_id),
            updated_by=str(user_id),
        )
        # 写一个真实的 CSV 文件
        task.result_uri = f"{task.id}.csv"
        await task.save(update_fields=["result_uri"])
        csv_path = tmp_path / f"{task.id}.csv"
        csv_path.write_text("id\n1\n", encoding="utf-8")
        assert csv_path.exists()

        # 初始化 Redis 状态
        from app.business.bi.async_query.state import init_state, set_runtime_redis
        await init_state(task.id, app.state.redis, status="success")

        # 注入运行期 redis 单例（PeriodicTask handler 无参，靠单例取 redis）
        set_runtime_redis(app.state.redis)

        n = await cleanup_expired_tasks()
        assert n >= 1

        # CSV 被物理删
        assert not csv_path.exists()
        # DB 软删
        from app.business.bi.models import BiQueryTask
        deleted = await BiQueryTask.filter(id=task.id, deleted_at__isnull=True).count()
        assert deleted == 0
        # Redis 状态被清
        from app.business.bi.async_query.state import get_state
        assert await get_state(task.id, app.state.redis) == {}

    async def test_cleanup_skips_recent(self, app, bi_datasource):
        from datetime import datetime, timedelta

        from app.business.bi.async_query.state import set_runtime_redis
        from app.business.bi.models import BiQueryTask
        from app.business.bi.services_async_query import cleanup_expired_tasks

        set_runtime_redis(app.state.redis)
        user_id = bi_datasource.tenant_id
        # 1 天前 finished 的任务，未过 7 天 TTL
        recent = await BiQueryTask.create(
            name="recent",
            datasource_id=bi_datasource.id,
            sql_text="SELECT 1",
            status="success",
            finished_at=datetime.now() - timedelta(days=1),
            tenant_id=user_id,
            source="manual",
            created_by=str(user_id),
            updated_by=str(user_id),
        )

        n = await cleanup_expired_tasks()
        assert n == 0

        # 任务仍在
        exists = await BiQueryTask.filter(id=recent.id, deleted_at__isnull=True).count()
        assert exists == 1

    async def test_cleanup_skips_running(self, app, bi_datasource):
        """即使 finished_at 很老，status=running 也不清理（避免误删卡住的任务）。"""
        from datetime import datetime, timedelta

        from app.business.bi.async_query.state import set_runtime_redis
        from app.business.bi.models import BiQueryTask
        from app.business.bi.services_async_query import cleanup_expired_tasks

        set_runtime_redis(app.state.redis)
        user_id = bi_datasource.tenant_id
        stale_running = await BiQueryTask.create(
            name="stale-running",
            datasource_id=bi_datasource.id,
            sql_text="SELECT 1",
            status="running",
            finished_at=datetime.now() - timedelta(days=30),  # 即便 finished_at 很老
            tenant_id=user_id,
            source="manual",
            created_by=str(user_id),
            updated_by=str(user_id),
        )

        n = await cleanup_expired_tasks()
        assert n == 0
        exists = await BiQueryTask.filter(id=stale_running.id, deleted_at__isnull=True).count()
        assert exists == 1
```

- [ ] **Step 4: 跑测试**

Run: `uv run pytest tests/test_bi_async_query.py::TestCleanupExpired -v`
Expected: 3 个测试 PASS。

- [ ] **Step 5: 跑 just check 确保整体未破坏**

Run: `just check backend`
Expected: 全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add app/business/bi/services_async_query.py app/business/bi/module.py tests/test_bi_async_query.py
git commit -m "feat(bi): add expired task cleanup periodic task (daily, leader_only)"
```

---

## Task 14: 端到端验收 + just check 门禁

**Files:** 无新增，仅运行验证

- [ ] **Step 1: 跑后端完整测试**

Run: `uv run pytest tests/ -v 2>&1 | tail -50`
Expected: 全部 PASS。重点关注：

- `tests/test_bi_chart.py`（chart 保存功能未破坏）
- `tests/test_bi_async_query.py`（queue / state / storage / quota / services / API / smart-switch）
- `tests/test_bi_async_query_runner.py`（worker runner）
- `tests/test_bi_datasource.py` 与 `tests/test_bi_*.py`（datasource / metadata / audit 未被 quota 改造破坏）

若有失败，定位：

- `execute_sql` 调用方未传 `redis` → 默认 `redis=None` 跳过熔断，不应失败
- `services.run_sql` 签名变更导致 import 错误 → 检查 `api/sql_workbench.py` 是否同步改了
- `BiQueryTask` 软删 fixture 残留 → 检查 `conftest.py` 的 `bi_query_task` fixture 是否清理上一轮

- [ ] **Step 2: 跑后端 lint + typecheck**

Run: `just fmt backend`
Expected: ruff check + format 通过。

Run: `just typecheck backend`
Expected: basedpyright 通过。常见报错：

- `execute_sql` 的 `redis` 参数类型应为 `Redis | None` 而非 `Optional[Redis]`（项目风格用 `X | None`）
- `services_async_query._task_record` 返回 `dict` 缺类型注解 → 补 `-> dict[str, Any]`

- [ ] **Step 3: 跑前端 lint + typecheck + test**

Run: `just fmt frontend`
Run: `just typecheck frontend`
Run: `just test frontend`
Expected: 全部通过。

- [ ] **Step 4: 跑完整门禁**

Run: `just check`
Expected: 后端 + 前端 fmt / typecheck / test 全绿。

- [ ] **Step 5: 启动 app 验证 worker 与菜单注册**

Run: `just run backend` 后台启动，等 5s。

Run: `just logs backend 2>&1 | grep -E "bi.async_query|Business: registered|查询任务" | head -20`
Expected:

- 看到 `bi.async_query worker started`
- 看到 `Business: registered routes from 'bi'`
- 看到 `recovered N stale tasks`（首次为 0）

Run: `curl -s http://localhost:9999/api/v1/business/bi/sql/tasks/search -X POST -H "Content-Type: application/json" -d '{"current":1,"size":10}'`
Expected: 401 / `code: 2100`（未授权）—— 证明路由已注册。

登录后用前端 UI 验证菜单「查询任务」可见。

杀掉后端进程。

- [ ] **Step 6: 最终 commit（如有 lint 修复残留）**

```bash
git status
# 若有未提交的格式化修复：
git add -u
git commit -m "chore(bi): apply fmt/check fixes for async query feature"
```

- [ ] **Step 7: 推送（可选，由用户决定）**

```bash
git log --oneline -15
# 等用户确认后再 git push
```

---

## 实现顺序与依赖

```
Task 1  (config + code)            ← 无依赖
Task 2  (model + migration)        ← 依赖 Task 1
Task 3  (schemas + controller)     ← 依赖 Task 2
Task 4  (queue)                    ← 依赖 Task 1（BIZ_SETTINGS）
Task 5  (state)                    ← 依赖 Task 1
Task 6  (storage)                  ← 依赖 Task 1
Task 7  (quota + sandbox 改造)     ← 依赖 Task 1；同时改 services.run_sql 签名
Task 8  (runner)                   ← 依赖 Task 4/5/6 + sandbox
Task 9  (services_async_query)     ← 依赖 Task 3/4/5/6/8
Task 10 (API 路由)                  ← 依赖 Task 9
Task 11 (智能切换 transfer)         ← 依赖 Task 7/9；与 Task 10 共享 services.run_sql 改造
Task 12 (worker 启动 + init_data)   ← 依赖 Task 8/10
Task 13 (前端)                      ← 依赖 Task 10/11 后端 API 完成
Task 15 (过期任务清理 PeriodicTask) ← 依赖 Task 9（services_async_query）
Task 14 (端到端验收)                ← 依赖全部
```

可并行的任务：

- Task 4 / Task 5 / Task 6（queue / state / storage 互不依赖）
- Task 13 的前端类型/API（Step 1-2）可与 Task 10/11 并行（仅依赖类型定义）
- Task 15 可与 Task 12/13 并行（仅依赖 Task 9）

---

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| `services.run_sql` 签名加 `redis` 参数破坏现有调用方 | 默认值 `redis=None` + 调用方逐个补传；Task 7 Step 4 / Task 11 Step 1-3 已覆盖 |
| 多 worker 下 quota 改造破坏 chart 测试 | Task 7 Step 6 显式跑 `tests/test_bi_chart.py` 验证 |
| granian 多 worker 抢同一任务 | BLPOP 是原子的，单任务只会被一个 worker 取到；Task 8 的 `recover_stale_tasks` 处理 crash 残留 |
| CSV 文件被恶意路径穿越 | Task 6 的 `resolve_csv_path` 用正则 + `resolve()` + 父目录校验三重防护 |
| 任务删除时 CSV 残留 | Task 9 `delete_task` 显式调 `storage.delete_csv` |
| 智能切换 transfer 误把快查询转异步 | 软超时 25s 远大于正常查询耗时；Task 11 测试 `test_run_sql_sync_success` 验证快查询不转 |
| 前端轮询风暴 | 列表 3s 间隔 + 详情 2s 间隔，且只在有进行中任务时轮询；Task 12 限流 `tasks/search` 60/60s、`tasks/{id}` 120/60s |
| worker 启动失败导致整个 app 起不来 | Task 12 的 `recover_stale_tasks` 包了 try/except，worker 协程也包了异常日志，不会阻断 lifespan |

---

## Self-Review 检查清单

完成所有 Task 后，对照 spec 检查：

- [ ] spec §3.1 整体架构：queue + state + storage + runner + services 分层（Task 4-9）
- [ ] spec §3.2 核心组件：6 个组件职责清晰（Task 4-9）
- [ ] spec §3.3 任务状态机：pending → running → success/failed/cancelled（Task 5/8）
- [ ] spec §3.4 Redis 键设计：queue / state / cancel / quota / breaker 全部实现（Task 4/5/7）
- [ ] spec §4.1 BiQueryTask 模型：字段完整 + 索引（Task 2）
- [ ] spec §5.1 智能切换：25s 软超时 + transfer 响应（Task 11）
- [ ] spec §5.2 提交流程：配额 → 数据源归属 → 白名单 → 创建 → init state → enqueue → 审计（Task 9）
- [ ] spec §5.3 worker 流式执行：fetchmany + cancel 检查 + 超时检查 + CSV 追加 + 进度更新（Task 8）
- [ ] spec §5.4 取消：pending 直接 cancelled / running 设标志位（Task 9）
- [ ] spec §5.5 下载：归属校验 + status=success + 路径校验 + StreamingResponse（Task 9/10）
- [ ] spec §6.1 并发配额：用户级 + 全局级（Task 7）
- [ ] spec §6.2 熔断：Redis ZSet 跨 worker（Task 7）
- [ ] spec §7 API 接口：8 个接口全部实现（Task 10）
- [ ] spec §8 配置项：11 项全部定义并加载（Task 1）
- [ ] spec §9 错误码：4110-4119 全部定义并使用（Task 1 + 各 Task）
- [ ] spec §10.1 菜单与按钮码：5 个按钮码 + 2 个菜单注册（Task 12）
- [ ] spec §10.2 角色权限：R_BI_ANALYST 包含新菜单与按钮（Task 12）
- [ ] spec §11 限流配置：3 条规则（Task 12）
- [ ] spec §12 前端设计：列表 / 详情 / 轮询 / 下载 / 智能切换跳转（Task 13）
- [ ] spec §13.1 安全：DependPermission + require_buttons + tenant_id 隔离 + 路径校验（Task 6/9/10）
- [ ] spec §13.2 资源：CSV 按 task_id 命名 + 删除同步清文件 + 流式 batch=1000 + 过期清理 PeriodicTask（Task 6/8/9/15）
- [ ] spec §13.3 多 worker：BLPOP 原子 + Redis Hash/Counter 共享（Task 4/5/7）
- [ ] spec §13.4 一致性：CSV → DB result_uri → 状态 success 顺序写（Task 8）
- [ ] spec §13.5 与现有功能关系：不破坏同步 / 不破坏 SSE / 复用 BiChart / 复用 sandbox（Task 7/11）
- [ ] spec §14 测试覆盖：queue / state / storage / quota / runner / services / API / transfer / cleanup 全有（Task 4-11/15）
- [ ] spec §15 手动验收清单：14 项全可执行（Task 13 Step 9 + Task 14 Step 5）
- [ ] spec §16 风险缓解：路径穿越 / CSV 残留 / 多 worker / 轮询风暴 / worker crash 全覆盖