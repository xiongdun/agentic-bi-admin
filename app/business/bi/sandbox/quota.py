"""查询配额限制 — 行数 / 超时 / 熔断。

默认值从 BI_QUERY_* 环境变量读取。
"""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from app.core.exceptions import BizError


@dataclass
class QuotaConfig:
    """配额配置。"""

    max_rows: int = int(os.getenv("BI_QUERY_MAX_ROWS", "10000"))
    timeout_seconds: int = int(os.getenv("BI_QUERY_TIMEOUT", "30"))
    breaker_threshold: int = int(os.getenv("BI_QUERY_BREAKER_THRESHOLD", "10"))
    breaker_window_seconds: int = 60


# 默认配额（模块加载时读取环境变量）
_default_config = QuotaConfig()

# 用户失败计数（用于熔断）—— 进程内字典，按 user_id 维护
# {user_id: deque[(timestamp,)]}
_failure_records: dict[int, deque[float]] = defaultdict(deque)


def check_quota(user_id: int, config: QuotaConfig | None = None) -> None:
    """检查用户是否触发熔断。

    Args:
        user_id: 用户 ID
        config: 配额配置（None 用默认）

    Raises:
        BizError(4102): 触发熔断
    """
    cfg = config or _default_config
    now = time.time()
    window_start = now - cfg.breaker_window_seconds

    # 清理过期记录
    records = _failure_records[user_id]
    while records and records[0] < window_start:
        records.popleft()

    # 检查熔断
    if len(records) >= cfg.breaker_threshold:
        raise BizError(
            4102,
            f"查询熔断：用户 {user_id} 在 {cfg.breaker_window_seconds} 秒内失败 {len(records)} 次，超过阈值 {cfg.breaker_threshold}",
        )


def record_failure(user_id: int, config: QuotaConfig | None = None) -> None:
    """记录用户查询失败（用于熔断统计）。"""
    _ = config  # 保留参数以与其它配额函数 API 一致；失败计数不依赖 config
    _failure_records[user_id].append(time.time())


def record_success(user_id: int) -> None:
    """记录用户查询成功（清空失败计数）。"""
    if user_id in _failure_records:
        _failure_records[user_id].clear()


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


def reset_failures(user_id: int | None = None) -> None:
    """重置失败计数（测试或管理用途）。"""
    if user_id is None:
        _failure_records.clear()
    else:
        _failure_records.pop(user_id, None)
