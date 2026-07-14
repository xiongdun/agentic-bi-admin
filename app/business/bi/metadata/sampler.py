"""元数据采样 — 从数据源拉列采样值（最多 10 个非空样本）。

Phase 1：SQLite 实现，Phase 2 扩展其他方言。
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.business.bi.models import Datasource, DatasourceType
from app.business.bi.sandbox.executor import SqlExecutionError

SAMPLE_LIMIT = 10


def _sqlite_url(ds: Datasource) -> str:
    from app.business.bi.sandbox.executor import _sqlite_url  # noqa: PLC0415

    return _sqlite_url(ds)


_BUILDER = {DatasourceType.sqlite: _sqlite_url}


async def sample_column(ds: Datasource, *, table: str, column: str, limit: int = SAMPLE_LIMIT) -> list[str]:
    """从 ``SELECT DISTINCT column FROM table WHERE column IS NOT NULL LIMIT n`` 取样本。"""
    builder = _BUILDER.get(ds.type)
    if builder is None:
        return []
    url = builder(ds)
    engine = create_async_engine(url, echo=False, future=True)
    sql = f'SELECT DISTINCT "{column}" AS v FROM "{table}" WHERE "{column}" IS NOT NULL LIMIT {int(limit)}'
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(sql))
            return [str(row[0]) for row in result.fetchall() if row[0] is not None]
    except SqlExecutionError:
        return []
    except Exception:
        return []
    finally:
        await engine.dispose()


__all__ = ["sample_column", "SAMPLE_LIMIT"]
