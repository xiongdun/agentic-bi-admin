"""BiQueryTask 业务服务 — submit / get / cancel / list / delete / download / cleanup。

编排层：把 queue + state + storage + runner + model 串成完整业务流程。
所有函数接受 ``redis`` 参数（由 API 层注入），不依赖全局状态。

注：响应 dict 的 key 用 camelCase（与前端 ``Api.Bi.BiQueryTask`` 类型对齐，
也与 spec §7.2 响应结构一致）。因 ``_task_record`` 是手工 dict 不走 Pydantic
alias_generator，必须显式用 camelCase。``get_state`` 返回的 Redis Hash 字段
是 snake_case（``rows_fetched`` / ``elapsed_ms``），合并时显式映射到 camelCase。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterator

from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from tortoise.expressions import Q

from app.business.bi.async_query import state, storage
from app.business.bi.async_query.queue import enqueue
from app.business.bi.async_query.quota import check_concurrency
from app.business.bi.config import BIZ_SETTINGS
from app.business.bi.controllers import bi_query_task_controller
from app.business.bi.models import BiDatasource, BiQueryTask
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


def _merge_live_state(record: dict[str, Any], task: BiQueryTask, redis: Redis) -> Any:
    """任务还在运行时，用 Redis 实时状态覆盖 DB 快照。

    返回协程，由调用方 await（方便列表场景批量调度）。
    """
    live = state.get_state(task.id, redis)

    async def _apply() -> None:
        data = await live
        if not data:
            return
        record["status"] = data.get("status", record["status"])
        record["progress"] = data.get("progress", record["progress"])
        record["rowsFetched"] = data.get("rows_fetched", record["rowsFetched"])
        record["elapsedMs"] = data.get("elapsed_ms", record["elapsedMs"])

    return _apply()


async def submit(
    schema: BiAsyncRunSchema,
    user_id: int,
    redis: Redis,
    source: str = "manual",
) -> BiQueryTask:
    """提交异步查询任务。

    流程（spec §5.2）：
    1. 检查功能开关 + 并发配额
    2. 校验数据源归属
    3. 白名单 + 行级注入
    4. 创建 BiQueryTask(status=pending)
    5. 初始化 Redis 状态
    6. enqueue
    7. 审计日志
    """
    if not BIZ_SETTINGS.BI_ASYNC_QUERY_ENABLED:
        raise BizError(Code.BI_ASYNC_QUERY_NOT_ENABLED, "异步大查询功能未开启")

    # 1. 并发配额
    await check_concurrency(user_id, redis)

    # 2. 数据源归属（tenant_id 行级隔离）
    ds_id = decode_id(schema.datasource_id)
    datasource = await BiDatasource.get_or_none(id=ds_id, tenant_id=user_id, deleted_at__isnull=True)
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
    task = await bi_query_task_controller.get_or_none(id=task_id, tenant_id=user_id, deleted_at__isnull=True)
    if task is None:
        raise BizError(Code.BI_ASYNC_QUERY_TASK_NOT_FOUND, "任务不存在")

    record = _task_record(task, include_sql=True)

    # 任务还在运行时，用 Redis 实时状态覆盖 DB 快照
    if task.status in ("pending", "running"):
        await _merge_live_state(record, task, redis)

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
            await _merge_live_state(record, task, redis)

    return total, records


async def cancel_task(task_id: int, user_id: int, redis: Redis) -> None:
    """取消任务。pending 直接置 cancelled；running 设标志位等 worker 检测。"""
    task = await bi_query_task_controller.get_or_none(id=task_id, tenant_id=user_id, deleted_at__isnull=True)
    if task is None:
        raise BizError(Code.BI_ASYNC_QUERY_TASK_NOT_FOUND, "任务不存在")

    if task.status not in ("pending", "running"):
        raise BizError(Code.BI_ASYNC_QUERY_TASK_NOT_CANCELLABLE, "任务当前状态不可取消")

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
    task = await bi_query_task_controller.get_or_none(id=task_id, tenant_id=user_id, deleted_at__isnull=True)
    if task is None:
        raise BizError(Code.BI_ASYNC_QUERY_TASK_NOT_FOUND, "任务不存在")

    # 删除 CSV 文件
    if task.result_uri:
        storage.delete_csv(task.result_uri)

    # 软删 DB（SoftDeleteManager 会设置 deleted_at）
    await task.delete()
    # 清 Redis 状态
    await state.delete_state(task_id, redis)
    radar_log("bi.async_query.delete", data={"task_id": task_id})


async def get_download_stream(task_id: int, user_id: int, redis: Redis) -> StreamingResponse:
    """构造 CSV 下载流。校验归属 + status=success + 文件存在。"""
    task = await bi_query_task_controller.get_or_none(id=task_id, tenant_id=user_id, deleted_at__isnull=True)
    if task is None:
        raise BizError(Code.BI_ASYNC_QUERY_TASK_NOT_FOUND, "任务不存在")

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

    def _iter() -> Iterator[bytes]:
        yield from storage.read_csv_stream(file_path)

    return StreamingResponse(
        _iter(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{task_id}.csv"',
            "Content-Length": str(size),
        },
    )


async def cleanup_expired_tasks() -> int:
    """清理过期任务（> ``BI_ASYNC_QUERY_TTL_DAYS`` 天）。

    由 PeriodicTask 每日触发，handler 无参签名，通过 ``state.get_runtime_redis()``
    获取运行期 Redis 单例。

    清理动作：
    1. 软删 DB 记录（SoftDeleteManager 设置 deleted_at）
    2. 物理删除 CSV 文件
    3. 清除 Redis Hash / cancel 标志
    """
    from datetime import timedelta

    threshold = datetime.now() - timedelta(days=BIZ_SETTINGS.BI_ASYNC_QUERY_TTL_DAYS)
    redis = state.get_runtime_redis()

    expired = await BiQueryTask.filter(created_at__lt=threshold, deleted_at__isnull=True)
    if not expired:
        return 0

    cleaned = 0
    for task in expired:
        try:
            if task.result_uri:
                storage.delete_csv(task.result_uri)
            await task.delete()
            await state.delete_state(task.id, redis)
            cleaned += 1
        except Exception:
            log.exception("bi.async_query cleanup task {} failed", task.id)

    if cleaned:
        radar_log("bi.async_query.cleanup", data={"count": cleaned})
        log.info("bi.async_query cleaned {} expired tasks", cleaned)
    return cleaned
