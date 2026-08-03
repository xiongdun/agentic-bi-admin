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
from pathlib import Path
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text

from app.business.bi.async_query import state, storage
from app.business.bi.async_query.queue import dequeue
from app.business.bi.async_query.quota import decr_running, incr_running
from app.business.bi.config import BIZ_SETTINGS
from app.business.bi.models import BiQueryTask
from app.business.bi.sandbox.dialect import get_dialect_name
from app.business.bi.sandbox.executor import get_engine, test_connection
from app.business.bi.sandbox.tenant import inject_tenant_filter
from app.business.bi.sandbox.whitelist import validate_sql
from app.core.code import Code
from app.core.exceptions import BizError
from app.core.log import log


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
            log.exception(f"bi.async_query execute_task failed task_id={task_id}")
            await state.update_status(task_id, "failed", redis, error_message="worker internal error")

    log.info("bi.async_query worker stopped")


async def execute_task(task_id: int, redis: Redis, app: Any) -> None:
    """执行单个任务。"""
    task = await BiQueryTask.get_or_none(id=task_id, deleted_at__isnull=True)
    if task is None:
        log.warning(f"bi.async_query task {task_id} not found, skip")
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
    await incr_running(user_id, redis)

    start_time = time.time()
    csv_path: Path | None = None
    result_uri: str | None = None

    try:
        # test_connection —— 不可用直接失败
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

        async with engine.connect() as conn:
            result = await conn.execute(text(safe_sql))
            if result.returns_rows:
                columns = list(result.keys())
                # 准备 CSV
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
        # preview_rows 已截断到 max_preview，write_preview 内部 isTruncated 判断失效；
        # 用 total_rows 覆盖 isTruncated 与 rowCount（rowCount 表示预览行数，isTruncated 表示是否还有更多）
        is_truncated = total_rows > max_preview
        snapshot["isTruncated"] = is_truncated

        task.status = "success"
        task.progress = 100
        task.rows_fetched = total_rows
        task.elapsed_ms = elapsed_ms
        task.result_snapshot = snapshot
        task.result_uri = result_uri
        task.result_row_count = total_rows
        task.result_is_truncated = is_truncated
        task.finished_at = datetime.now()
        await task.save(
            update_fields=[
                "status",
                "progress",
                "rows_fetched",
                "elapsed_ms",
                "result_snapshot",
                "result_uri",
                "result_row_count",
                "result_is_truncated",
                "finished_at",
                "updated_at",
            ]
        )
        await state.update_status(task_id, "success", redis)
        await state.update_progress(task_id, redis, progress=100, rows_fetched=total_rows, elapsed_ms=elapsed_ms)
        await state.clear_cancel(task_id, redis)
        log.info(f"bi.async_query task {task_id} success rows={total_rows}")

    except TaskCancelledError:
        await _finalize_terminal(task_id, redis, user_id, "cancelled", "用户取消", start_time, csv_path)
        log.info(f"bi.async_query task {task_id} cancelled")
    except TaskTimeoutError as e:
        await _finalize_terminal(task_id, redis, user_id, "failed", f"执行超时：{e}", start_time, csv_path)
        log.warning(f"bi.async_query task {task_id} timeout")
    except BizError as e:
        await _finalize_terminal(task_id, redis, user_id, "failed", str(e), start_time, csv_path)
        log.warning(f"bi.async_query task {task_id} biz_error: {e}")
    except Exception as e:
        await _finalize_terminal(task_id, redis, user_id, "failed", f"内部错误：{e}", start_time, csv_path)
        log.exception(f"bi.async_query task {task_id} internal_error")


async def _finalize_terminal(
    task_id: int,
    redis: Redis,
    user_id: int,
    status: str,
    error_message: str,
    start_time: float,
    csv_path: Path | None,
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
            csv_path.unlink(missing_ok=True)
        except Exception:
            log.warning(f"bi.async_query task {task_id} cleanup csv failed")
    await decr_running(user_id, redis)


async def recover_stale_tasks(redis: Redis) -> int:
    """启动时扫描 status=running 但 started_at 超过 timeout 的任务，标记 failed。

    Returns:
        恢复的任务数
    """
    from datetime import timedelta

    timeout = BIZ_SETTINGS.BI_ASYNC_QUERY_TIMEOUT
    threshold = datetime.now() - timedelta(seconds=timeout * 2)  # 2 倍宽限
    stale = await BiQueryTask.filter(status="running", started_at__lt=threshold)
    for task in stale:
        task.status = "failed"
        task.error_message = "worker crash recovery：任务异常中断"
        task.finished_at = datetime.now()
        await task.save(update_fields=["status", "error_message", "finished_at", "updated_at"])
        await state.update_status(task.id, "failed", redis, error_message="worker crash recovery")
        log.warning(f"bi.async_query recovered stale task {task.id}")
    return len(stale)
