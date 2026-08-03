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
            f"查询熔断：scope={scope} 在 {cfg.breaker_window_seconds} 秒内失败 {count} 次，超过阈值 {cfg.breaker_threshold}",
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


async def reset_failures(scope: str | None, redis: Redis) -> None:
    """重置失败计数（测试或管理用途）。scope=None 时清所有已知 scope。"""
    if scope is None:
        # 扫描 bi:quota:failures:* —— 测试场景用 fakeredis，生产应避免
        async for key in redis.scan_iter(match="bi:quota:failures:*"):
            await redis.delete(key)
    else:
        await redis.delete(_failures_key(scope))
