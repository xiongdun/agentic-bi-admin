"""元数据同步 — 拉取数据源中所有表 / 列结构，写入 bi_table / bi_column。

Phase 1：仅 SQLite 适配器，从 ``sqlite_master`` + ``PRAGMA table_info`` 读取。
Phase 2 扩展 PostgreSQL / MySQL / ClickHouse / Trino。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.business.bi.metadata.sampler import sample_column
from app.business.bi.models import BiColumn, BiTable, Datasource, DatasourceType
from app.business.bi.sandbox.executor import _sqlite_url
from app.core.log import log


def _now_naive() -> datetime:
    """返回无时区信息的当前时间（与项目其他表一致）。"""
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


@dataclass(slots=True)
class SyncResult:
    """同步结果汇总。"""

    tables: int
    columns: int
    skipped: int
    errors: list[str]


def _sqlite_url_for(ds: Datasource) -> str:
    return _sqlite_url(ds)


_BUILDER = {DatasourceType.sqlite: _sqlite_url_for}


async def _list_sqlite_tables(conn) -> list[tuple[str, str | None]]:
    """返回 [(table_name, schema_name)]。SQLite 只有一个 schema。"""
    rows = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
    return [(r[0], None) for r in rows.fetchall()]


async def _list_sqlite_columns(conn, table: str) -> list[dict]:
    """通过 PRAGMA 拉列信息。"""
    rows = await conn.execute(text(f'PRAGMA table_info("{table}")'))
    out: list[dict] = []
    for row in rows.fetchall():
        # cid, name, type, notnull, dflt_value, pk
        out.append({
            "name": row[1],
            "data_type": row[2] or "TEXT",
            "nullable": not bool(row[3]),
            "is_pk": bool(row[5]),
            "default": row[4],
        })
    return out


_HEURISTIC_DIMENSION_TYPES = {"TEXT", "VARCHAR", "CHAR", "DATE", "TIMESTAMP", "DATETIME", "BOOLEAN", "BOOL", "UUID"}
_HEURISTIC_METRIC_TYPES = {"INT", "INTEGER", "BIGINT", "SMALLINT", "REAL", "DOUBLE", "FLOAT", "NUMERIC", "DECIMAL"}


def _guess_role(col_name: str, data_type: str) -> tuple[bool, bool]:
    """简易启发式：根据列名 + 类型猜 dimension / metric。"""
    is_metric = data_type.upper() in _HEURISTIC_METRIC_TYPES and (
        any(kw in col_name.lower() for kw in ("amount", "count", "total", "sum", "qty", "quantity", "price", "cost", "score")) or col_name.lower().endswith("_id") is False
    )
    is_dimension = data_type.upper() in _HEURISTIC_DIMENSION_TYPES or col_name.lower().endswith(("_id", "_at", "_date", "name", "status", "type", "category", "city", "country"))
    return is_dimension, is_metric


async def sync_datasource(ds: Datasource, *, sample_size: int = 10) -> SyncResult:
    """拉取一个数据源的全量 schema 并 upsert 到 bi_table / bi_column。"""
    builder = _BUILDER.get(ds.type)
    if builder is None:
        return SyncResult(tables=0, columns=0, skipped=0, errors=[f"unsupported_type: {ds.type.value}"])

    url = builder(ds)
    engine = create_async_engine(url, echo=False, future=True)
    errors: list[str] = []
    table_count = 0
    column_count = 0

    try:
        async with engine.connect() as conn:
            if ds.type == DatasourceType.sqlite:
                raw_tables = await _list_sqlite_tables(conn)
            else:
                raw_tables = []
        # 第二轮：每张表拉列 + 采样
        for table_name, schema_name in raw_tables:
            try:
                bi_table, _ = await BiTable.update_or_create(
                    defaults={"schema_name": schema_name, "version": 1},
                    datasource_id=ds.id,
                    name=table_name,
                )
                bi_table.version = (bi_table.version or 0) + 1
                bi_table.last_synced_at = _now_naive()
                await bi_table.save(update_fields=["version", "last_synced_at"])
                table_count += 1

                # 拉列
                async with engine.connect() as conn:
                    if ds.type == DatasourceType.sqlite:
                        cols = await _list_sqlite_columns(conn, table_name)
                    else:
                        cols = []

                for ordinal, col in enumerate(cols):
                    is_dim, is_metric = _guess_role(col["name"], col["data_type"])
                    samples = await sample_column(ds, table=table_name, column=col["name"], limit=sample_size)
                    await BiColumn.update_or_create(
                        defaults={
                            "data_type": col["data_type"],
                            "nullable": col["nullable"],
                            "is_dimension": is_dim,
                            "is_metric": is_metric,
                            "sample_values": samples or None,
                            "ordinal": ordinal,
                        },
                        table_id=bi_table.id,
                        name=col["name"],
                    )
                    column_count += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{table_name}: {exc}")
                log.warning(f"bi.metadata.sync: table {table_name} failed: {exc}")
    finally:
        await engine.dispose()

    ds.last_synced_at = _now_naive()
    await ds.save(update_fields=["last_synced_at"])

    return SyncResult(tables=table_count, columns=column_count, skipped=0, errors=errors)


__all__ = ["sync_datasource", "SyncResult"]
