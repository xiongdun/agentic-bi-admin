"""SQL 沙箱 — 配额与限流。

- ``Quota`` 数据类描述单次执行 / 单用户的资源上限
- ``QuotaExceeded`` 业务异常 — pipeline 在超出时抛出
- ``RateLimiter`` 基于 Redis 的"每用户每分钟 N 次"令牌桶简化版（用 INCR + EXPIRE）

Phase 1 用最简单的实现：超限直接抛 ``QuotaExceeded``（400 系列业务码）。
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from redis.asyncio import Redis

from app.core.config import APP_SETTINGS
from app.core.exceptions import BizError


@dataclass(slots=True)
class Quota:
    """单次执行 / 单用户的资源上限。"""

    max_rows: int = 10_000
    timeout_seconds: float = 30.0
    slow_query_threshold_ms: int = 5_000
    rate_limit_per_minute: int = 30  # 每用户每分钟


class QuotaExceeded(BizError):
    """配额超限。code 借 1001（参数错误）系列，统一在 pipeline 中转译。"""

    def __init__(self, message: str, *, kind: str) -> None:
        super().__init__(code=1001, msg=message)
        self.data = {"kind": kind}
        self.kind = kind


class RateLimiter:
    """基于 Redis 的"每用户每分钟 N 次"简易限流。"""

    KEY_PREFIX = "bi:ratelimit:query:"

    def __init__(self, redis: Redis | None = None) -> None:
        self._redis = redis

    async def _get_redis(self) -> Redis:
        if self._redis is None:
            from redis.asyncio import from_url

            self._redis = from_url(APP_SETTINGS.REDIS_URL, decode_responses=True)
        return self._redis

    async def check(self, *, user_id: int, per_minute: int) -> None:
        """校验用户是否超出每分钟 N 次限制；超限抛 ``QuotaExceeded``。"""
        if per_minute <= 0:
            return
        redis = await self._get_redis()
        bucket = int(time.time() // 60)
        key = f"{self.KEY_PREFIX}{user_id}:{bucket}"
        # pipeline: INCR + EXPIRE
        async with redis.pipeline(transaction=False) as pipe:
            pipe.incr(key)
            pipe.expire(key, 70)  # 70s 留 buffer
            count, _ = await pipe.execute()
        if count > per_minute:
            raise QuotaExceeded(
                f"查询过于频繁：每分钟最多 {per_minute} 次，请稍后再试。",
                kind="rate_limit",
            )


async def enforce_row_limit(row_count: int, quota: Quota) -> None:
    """行数检查（pipeline 在拿到结果后调用）。"""
    if row_count > quota.max_rows:
        raise QuotaExceeded(
            f"结果集超过 {quota.max_rows} 行（实际 {row_count}），请加 LIMIT 或收窄筛选。",
            kind="row_limit",
        )


async def enforce_timeout(start: float, quota: Quota) -> None:
    """耗时检查（pipeline 在执行完成时调用）。"""
    elapsed = (time.perf_counter() - start) * 1000
    if elapsed > quota.timeout_seconds * 1000:
        raise QuotaExceeded(
            f"查询超时：{elapsed:.0f}ms > {quota.timeout_seconds * 1000:.0f}ms。",
            kind="timeout",
        )


def is_slow_query(cost_ms: int, quota: Quota) -> bool:
    """判定是否触发慢查询告警阈值。"""
    return cost_ms > quota.slow_query_threshold_ms
