"""SQL 沙箱 — 执行器。

通过 SQLAlchemy 异步引擎拉取数据，Phase 1 仅支持 SQLite（本地 demo）。
Phase 2 扩展 PostgreSQL / MySQL / ClickHouse / Trino。
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.business.bi.models import Datasource, DatasourceType
from app.utils import detect_dialect


@dataclass(slots=True)
class QueryResult:
    """沙箱执行结果。"""

    columns: list[str]
    rows: list[list]
    row_count: int
    cost_ms: int


class SqlExecutionError(RuntimeError):
    """SQL 执行错误（含 DB 抛出的所有异常）。"""


def _sqlite_url(ds: Datasource) -> str:
    """从 Datasource 构造 SQLite async URL（aiosqlite）。"""
    db_path = ds.database or ""
    if not db_path:
        raise SqlExecutionError("Datasource.database is empty")
    # relative path → 相对项目根（executor.py = app/business/bi/sandbox/executor.py，parents[4] = 项目根）
    if not db_path.startswith("/"):
        project_root = Path(__file__).resolve().parents[4]
        db_path = str(project_root / db_path)
    if not os.path.exists(db_path):
        # 演示用：允许指向尚不存在的文件，SQLite 会在第一次执行时自动创建
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+aiosqlite:///{db_path}"


# Phase 1：仅 SQLite 适配器；其他方言在 Phase 2 接入。
_BUILDER = {
    DatasourceType.sqlite: _sqlite_url,
}


def build_engine(ds: Datasource) -> AsyncEngine:
    """根据数据源类型构造 SQLAlchemy 异步引擎。"""
    builder = _BUILDER.get(ds.type)
    if builder is None:
        raise SqlExecutionError(f"unsupported_datasource_type: {ds.type.value} (Phase 1 仅支持 sqlite)")
    url = builder(ds)
    # SQLite 单文件，禁用 pool 避免多连接写锁
    return create_async_engine(url, echo=False, future=True)


async def execute(ds: Datasource, sql: str) -> QueryResult:
    """执行一条 SQL，返回列名 / 行 / 耗时。

    使用 ``connect()`` 而非 ``begin()``，避免 DDL/DML 自动事务；
    沙箱里只读 SELECT，所以显式读连接就够。
    """
    engine = build_engine(ds)
    start = time.perf_counter()
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(sql))
            columns: list[str] = list(result.keys())
            rows = [list(row) for row in result.fetchall()]
    except Exception as exc:
        raise SqlExecutionError(str(exc)) from exc
    finally:
        await engine.dispose()
    cost_ms = int((time.perf_counter() - start) * 1000)
    return QueryResult(columns=columns, rows=rows, row_count=len(rows), cost_ms=cost_ms)


def resolve_dialect(ds: Datasource) -> str:
    """由数据源类型映射 sqlglot 方言名。"""
    return detect_dialect(ds.type.value)


__all__ = [
    "QueryResult",
    "SqlExecutionError",
    "build_engine",
    "execute",
    "resolve_dialect",
]
