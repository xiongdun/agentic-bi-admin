"""BiMaskingRule 加载与缓存服务。"""
from __future__ import annotations

import json

from app.business.bi.async_query.state import get_runtime_redis
from app.business.bi.config import BIZ_SETTINGS
from app.business.bi.models import BiMaskingRule
from app.business.bi.sandbox.masking import mask_columns
from app.core.log import log
from app.utils import StatusType

_CACHE_KEY = "bi:masking:rules:enabled"


async def load_masking_rules() -> list[BiMaskingRule]:
    """加载所有启用的脱敏规则（带 Redis 缓存）。

    缓存 miss 时从 DB 查询并写回缓存；命中时直接返回。
    """
    redis = get_runtime_redis()
    cached = await redis.get(_CACHE_KEY)
    if cached is not None:
        try:
            data = json.loads(cached)
            return [BiMaskingRule(**item) for item in data]
        except Exception:
            log.warning("bi.masking.cache.parse_failed, fallback to DB")

    rules = await BiMaskingRule.filter(status_type=StatusType.enable).all()
    payload = json.dumps(
        [
            {
                "id": r.id,
                "name": r.name,
                "column_pattern": r.column_pattern,
                "mask_type": r.mask_type,
                "mask_char": r.mask_char,
                "keep_prefix": r.keep_prefix,
                "keep_suffix": r.keep_suffix,
                "status_type": r.status_type,
            }
            for r in rules
        ]
    )
    await redis.set(_CACHE_KEY, payload, ex=BIZ_SETTINGS.BI_MASKING_CACHE_TTL)
    return rules


async def invalidate_masking_cache() -> None:
    """失效脱敏规则缓存（CRUD 变更时调用）。"""
    redis = get_runtime_redis()
    await redis.delete(_CACHE_KEY)
    log.info("bi.masking.cache.invalidated")


async def apply_masking(rows: list[dict]) -> list[dict]:
    """对查询结果应用脱敏规则（便捷封装）。

    无规则时直接返回原 rows。
    """
    if not rows:
        return rows
    rules = await load_masking_rules()
    if not rules:
        return rows
    return mask_columns(rows, rules)
