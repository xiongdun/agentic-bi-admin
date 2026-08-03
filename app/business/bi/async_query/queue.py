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
