"""SQLAlchemy 异步执行器 — 对外部数据源执行用户 SQL。

系统库仍用 Tortoise ORM；外部数据源（用户配置的 PostgreSQL / MySQL / ClickHouse / Trino / SQLite）用 SQLAlchemy async engine 执行。
引擎按 datasource_id 缓存复用。

注：``decrypt`` 来自 ``app.business.bi.security.crypto``（Task 7），``get_dialect_name``
当前未使用——Task 9 提供的是 ``to_dialect``。在 crypto 模块落地前，``decrypt`` 采用
函数内懒导入，避免本模块在占位阶段 import 失败。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.business.bi.models import BiDatasource
from app.business.bi.sandbox.quota import (
    check_quota,
    check_row_limit,
    get_timeout,
    record_failure,
    record_success,
)
from app.core.exceptions import BizError

# 方言 -> SQLAlchemy async driver 映射
_DRIVER_MAP = {
    "postgresql": "postgresql+asyncpg",
    "mysql": "mysql+asyncmy",
    "clickhouse": "clickhouse+asynch",  # 需要 clickhouse-connect 或 asynch
    "trino": "trino",  # trino SQLAlchemy 方言
    "sqlite": "sqlite+aiosqlite",
}

# 引擎缓存：{datasource_id: AsyncEngine}
_engine_cache: dict[int, AsyncEngine] = {}


@dataclass
class ExecutionResult:
    """SQL 执行结果。"""

    rows: list[dict[str, Any]]
    columns: list[str]
    elapsed_ms: int
    row_count: int


def _build_connection_url(datasource: BiDatasource) -> str:
    """构建 SQLAlchemy 连接 URL。"""
    driver = _DRIVER_MAP.get(datasource.db_type)
    if driver is None:
        raise BizError(4000, f"不支持的数据源类型: {datasource.db_type}")

    if datasource.db_type == "sqlite":
        # SQLite 用文件路径，不需要密码
        return f"sqlite+aiosqlite:///{datasource.database}"

    # 懒导入：Task 7（crypto）落地前避免本模块 import 失败
    from app.business.bi.security.crypto import decrypt

    password = decrypt(datasource.password) if datasource.password else ""

    return f"{driver}://{datasource.username}:{password}@{datasource.host}:{datasource.port}/{datasource.database}"


async def get_engine(datasource: BiDatasource) -> AsyncEngine:
    """获取或创建数据源的 SQLAlchemy async engine（按 datasource_id 缓存）。

    Task 12.3: 引擎缓存按 datasource_id 复用，避免每次创建。
    """
    ds_id = datasource.id
    if ds_id in _engine_cache:
        return _engine_cache[ds_id]

    url = _build_connection_url(datasource)

    # 创建引擎（连接池配置）
    engine = create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    _engine_cache[ds_id] = engine
    return engine


async def execute_sql(
    sql: str,
    datasource: BiDatasource,
    user_id: int,
    timeout: int | None = None,
    max_rows: int | None = None,
    redis: Redis | None = None,
) -> ExecutionResult:
    """执行 SQL 并返回结果。

    Args:
        sql: 已通过白名单校验的 SQL
        datasource: 数据源实例
        user_id: 用户 ID（用于配额检查）
        timeout: 超时秒数（None 用默认）
        max_rows: 最大行数（None 用默认）
        redis: Redis 客户端（用于熔断计数）。None 时跳过熔断（向后兼容）。

    Returns:
        ExecutionResult: 执行结果

    Raises:
        BizError: 执行失败 / 配额超限 / 超时
    """
    scope = f"user:{user_id}"

    # 加载配额配置（链式查找：datasource > user > global > env 默认）
    from app.business.bi.services_quota import load_quota_config

    cfg = await load_quota_config("user", user_id)

    # 配额检查（多 worker 共享 Redis ZSet）
    if redis is not None:
        await check_quota(scope, redis, config=cfg)

    engine = await get_engine(datasource)
    timeout_seconds = timeout or get_timeout(cfg)

    start = time.time()
    try:
        async with engine.connect() as conn:
            # 执行 SQL（用 text 包装以支持参数化，这里 SQL 已校验过）
            # 应用查询超时（SubTask 12.1）：超时抛 asyncio.TimeoutError，由下方 except 捕获转 BizError(4104)
            result = await asyncio.wait_for(conn.execute(text(sql)), timeout=timeout_seconds)

            # 获取列名
            columns = list(result.keys()) if result.returns_rows else []

            # 获取行数据
            rows: list[dict[str, Any]] = []
            if result.returns_rows:
                fetched = result.fetchmany(max_rows or cfg.max_rows)
                for row in fetched:
                    rows.append(dict(row._mapping))

        elapsed_ms = int((time.time() - start) * 1000)

        # 行数检查
        check_row_limit(len(rows), config=cfg)

        # 记录成功
        if redis is not None:
            await record_success(scope, redis)

        return ExecutionResult(
            rows=rows,
            columns=columns,
            elapsed_ms=elapsed_ms,
            row_count=len(rows),
        )

    except BizError:
        # 配额 / 行数错误直接抛出
        if redis is not None:
            await record_failure(scope, redis, config=cfg)
        raise
    except Exception as e:
        if redis is not None:
            await record_failure(scope, redis, config=cfg)
        elapsed_ms = int((time.time() - start) * 1000)
        raise BizError(4104, f"SQL 执行失败: {e}") from e


async def test_connection(datasource: BiDatasource) -> tuple[bool, str, int]:
    """测试数据源连接。

    Returns:
        (success, message, elapsed_ms)
    """
    start = time.time()
    try:
        engine = await get_engine(datasource)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        elapsed_ms = int((time.time() - start) * 1000)
        return True, "连接成功", elapsed_ms
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return False, f"连接失败: {e}", elapsed_ms


async def dispose_engine(datasource_id: int) -> None:
    """释放指定数据源的引擎（数据源删除/更新时调用）。"""
    engine = _engine_cache.pop(datasource_id, None)
    if engine:
        await engine.dispose()


async def dispose_all_engines() -> None:
    """释放所有引擎（应用关闭时调用）。"""
    for ds_id in list(_engine_cache.keys()):
        await dispose_engine(ds_id)
