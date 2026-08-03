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
        raise BizError(
            Code.BI_ASYNC_QUERY_USER_CONCURRENCY_EXCEEDED,
            f"用户并发任务数超限：{user_running} >= {BIZ_SETTINGS.BI_ASYNC_QUERY_USER_MAX_CONCURRENCY}",
        )

    global_running = await redis.get(_GLOBAL_KEY)
    global_running = int(global_running) if global_running else 0
    if global_running >= BIZ_SETTINGS.BI_ASYNC_QUERY_GLOBAL_MAX_CONCURRENCY:
        raise BizError(
            Code.BI_ASYNC_QUERY_GLOBAL_CONCURRENCY_EXCEEDED,
            f"全局并发任务数超限：{global_running} >= {BIZ_SETTINGS.BI_ASYNC_QUERY_GLOBAL_MAX_CONCURRENCY}",
        )


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
