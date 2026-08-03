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
    await redis.hset(  # type: ignore[arg-type]
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
    await redis.hset(_task_key(task_id), mapping=fields)  # type: ignore[arg-type]


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
        await redis.hset(_task_key(task_id), mapping=fields)  # type: ignore[arg-type]


async def set_started_at(task_id: int, redis: Redis, started_at: datetime) -> None:
    await redis.hset(_task_key(task_id), mapping={"started_at": started_at.isoformat()})  # type: ignore[arg-type]


async def get_state(task_id: int, redis: Redis) -> dict[str, Any]:
    """读取任务实时状态。"""
    raw = await redis.hgetall(_task_key(task_id))  # type: ignore[arg-type]
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
