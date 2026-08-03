"""BiQuotaConfig 加载与缓存服务。"""
from __future__ import annotations

import json

from app.business.bi.async_query.state import get_runtime_redis
from app.business.bi.config import BIZ_SETTINGS
from app.business.bi.models import BiQuotaConfig
from app.business.bi.sandbox.quota import QuotaConfig, _default_config
from app.core.log import log
from app.utils import StatusType


def _cache_key(scope_type: str, scope_id: int | None) -> str:
    return f"bi:quota:config:{scope_type}:{scope_id}"


async def _load_one(scope_type: str, scope_id: int | None) -> BiQuotaConfig | None:
    """从 DB 查询单条启用配置。"""
    qs = BiQuotaConfig.filter(scope_type=scope_type, status_type=StatusType.enable)
    if scope_id is None:
        qs = qs.filter(scope_id__isnull=True)
    else:
        qs = qs.filter(scope_id=scope_id)
    return await qs.first()


async def load_quota_config(
    scope_type: str, scope_id: int | None, *, user_id: int | None = None
) -> QuotaConfig:
    """链式查找配额配置（datasource > user > global > env 默认）。

    Args:
        scope_type: 初始查找作用域（'datasource' 或 'user'）
        scope_id: 初始查找作用域 ID
        user_id: 用户 ID（datasource 查找失败时回退到 user 作用域用）
    Returns:
        QuotaConfig dataclass（sandbox 可直接使用）
    """
    redis = get_runtime_redis()

    # 构建查找链
    chain: list[tuple[str, int | None]] = []
    if scope_type == "datasource" and scope_id is not None:
        chain.append(("datasource", scope_id))
        if user_id is not None:
            chain.append(("user", user_id))
    elif scope_type == "user" and scope_id is not None:
        chain.append(("user", scope_id))
    chain.append(("global", None))

    for st, sid in chain:
        key = _cache_key(st, sid)
        cached = await redis.get(key)
        if cached is not None:
            try:
                data = json.loads(cached)
                if data:  # 非空字典表示命中
                    return QuotaConfig(
                        max_rows=data["max_rows"],
                        timeout_seconds=data["timeout_seconds"],
                        breaker_threshold=data["breaker_threshold"],
                        breaker_window_seconds=data["breaker_window_seconds"],
                    )
                # 空字典表示"已查过但无配置"，跳过
                continue
            except Exception:
                log.warning("bi.quota.cache.parse_failed key={}", key)

        # 查 DB
        cfg = await _load_one(st, sid)
        if cfg:
            payload = json.dumps(
                {
                    "max_rows": cfg.max_rows,
                    "timeout_seconds": cfg.timeout_seconds,
                    "breaker_threshold": cfg.breaker_threshold,
                    "breaker_window_seconds": cfg.breaker_window_seconds,
                }
            )
            await redis.set(key, payload, ex=BIZ_SETTINGS.BI_QUOTA_CACHE_TTL)
            return QuotaConfig(
                max_rows=cfg.max_rows,
                timeout_seconds=cfg.timeout_seconds,
                breaker_threshold=cfg.breaker_threshold,
                breaker_window_seconds=cfg.breaker_window_seconds,
            )
        # 写空字典标记"已查无"，避免重复查 DB
        await redis.set(key, "{}", ex=BIZ_SETTINGS.BI_QUOTA_CACHE_TTL)

    # 全链路都没命中，回退 env 默认
    return _default_config


async def invalidate_quota_cache(scope_type: str | None = None, scope_id: int | None = None) -> None:
    """失效配额配置缓存。

    传参时只失效对应 key；不传参时清空所有 bi:quota:config:* 前缀。
    """
    redis = get_runtime_redis()
    if scope_type is not None:
        await redis.delete(_cache_key(scope_type, scope_id))
    else:
        async for key in redis.scan_iter("bi:quota:config:*"):
            await redis.delete(key)
    log.info("bi.quota.cache.invalidated scope_type={} scope_id={}", scope_type, scope_id)
