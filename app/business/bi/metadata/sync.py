"""元数据同步 — 采集数据源的表/列/索引/外键元数据。

分批采集（每次 BI_METADATA_BATCH_SIZE 张表），结果写入 biz_bi_table / biz_bi_column / biz_bi_index / biz_bi_foreign_key。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.business.bi.metadata.relations import extract_foreign_keys
from app.business.bi.models import BiColumn, BiDatasource, BiForeignKey, BiIndex, BiTable
from app.business.bi.sandbox.executor import get_engine
from app.utils import BizError


@dataclass
class SyncResult:
    """同步结果。"""

    datasource_id: int
    tables_synced: int = 0
    columns_synced: int = 0
    indexes_synced: int = 0
    foreign_keys_synced: int = 0
    elapsed_ms: int = 0
    errors: list[str] = field(default_factory=list)


# 不同数据库的表查询 SQL
_TABLE_QUERIES = {
    "postgresql": """
        SELECT
            t.table_name,
            pg_catalog.obj_description(c.oid) as table_comment,
            pg_stat_get_tuples(c.oid) as row_count
        FROM information_schema.tables t
        LEFT JOIN pg_catalog.pg_class c ON c.relname = t.table_name
        WHERE t.table_schema = 'public' AND t.table_type = 'BASE TABLE'
    """,
    "mysql": """
        SELECT
            TABLE_NAME as table_name,
            TABLE_COMMENT as table_comment,
            TABLE_ROWS as row_count
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE'
    """,
    "sqlite": """
        SELECT
            m.name as table_name,
            m.name as table_comment,
            0 as row_count
        FROM sqlite_master m
        WHERE m.type = 'table' AND m.name NOT LIKE 'sqlite_%'
    """,
    "clickhouse": """
        SELECT
            name as table_name,
            name as table_comment,
            0 as row_count
        FROM system.tables
        WHERE database = currentDatabase()
    """,
    "trino": """
        SELECT
            table_name,
            NULL as table_comment,
            0 as row_count
        FROM information_schema.tables
        WHERE table_schema = current_schema
    """,
}


async def sync_datasource(datasource: BiDatasource) -> SyncResult:
    """同步数据源元数据。

    采集流程：
    1. 获取 SQLAlchemy engine
    2. 删除该数据源的旧元数据
    3. 分批采集表信息
    4. 对每张表采集列/索引
    5. 采集外键关系
    6. 更新 datasource.last_synced_at

    Args:
        datasource: BiDatasource 模型实例

    Returns:
        SyncResult: 同步结果统计

    Raises:
        BizError(4001): 数据源连接失败
    """
    start = datetime.now()
    result = SyncResult(datasource_id=datasource.id)

    engine = await get_engine(datasource)
    db_type = datasource.db_type.lower()

    # 1. 获取表列表
    tables_info = await _fetch_tables(engine, db_type)
    if tables_info is None:
        # 连接失败
        raise BizError(4001, f"数据源连接失败: {datasource.name}")

    # 2. 删除旧元数据
    await _clear_old_metadata(datasource.id)

    # 3. 分批采集
    batch_size = int(os.getenv("BI_METADATA_BATCH_SIZE", "100"))

    for i in range(0, len(tables_info), batch_size):
        batch = tables_info[i : i + batch_size]
        for table_info in batch:
            try:
                await _sync_single_table(datasource.id, engine, db_type, table_info, result)
            except Exception as e:
                result.errors.append(f"表 {table_info.get('table_name')}: {e}")

    # 4. 采集外键关系
    try:
        fks = await extract_foreign_keys(engine, db_type)
        for fk in fks:
            # 找到对应的 BiTable
            bi_table = await BiTable.filter(
                datasource_id=datasource.id,
                name=fk["table_name"],
            ).first()
            if bi_table:
                await BiForeignKey.create(
                    table_id=bi_table.id,
                    name=fk.get("constraint_name", ""),
                    column_name=fk["column_name"],
                    ref_table=fk["foreign_table_name"],
                    ref_column=fk.get("foreign_column_name", ""),
                )
                result.foreign_keys_synced += 1
    except Exception as e:
        result.errors.append(f"外键提取: {e}")

    # 5. 更新 last_synced_at
    await BiDatasource.filter(id=datasource.id).update(last_synced_at=datetime.now())

    result.elapsed_ms = int((datetime.now() - start).total_seconds() * 1000)
    return result


async def _fetch_tables(engine: AsyncEngine, db_type: str) -> list[dict] | None:
    """获取数据源的表列表。"""
    query = _TABLE_QUERIES.get(db_type.lower())
    if query is None:
        return []

    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(query))
            rows = result.fetchall()
            columns = list(result.keys())
            return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return None


async def _clear_old_metadata(datasource_id: int) -> None:
    """清除数据源的旧元数据。"""
    # 先获取所有表 ID
    tables = await BiTable.filter(datasource_id=datasource_id).values("id")
    table_ids = [t["id"] for t in tables]

    if table_ids:
        await BiColumn.filter(table_id__in=table_ids).delete()
        await BiIndex.filter(table_id__in=table_ids).delete()
        await BiForeignKey.filter(table_id__in=table_ids).delete()

    await BiTable.filter(datasource_id=datasource_id).delete()


async def _sync_single_table(
    datasource_id: int,
    engine: AsyncEngine,
    db_type: str,
    table_info: dict,
    result: SyncResult,
) -> None:
    """同步单张表的元数据。"""
    table_name = table_info["table_name"]

    # 创建 BiTable 记录
    bi_table = await BiTable.create(
        datasource_id=datasource_id,
        name=table_name,
        comment=table_info.get("table_comment"),
        row_count=table_info.get("row_count", 0) or 0,
    )
    result.tables_synced += 1

    # 采集列信息
    columns = await _fetch_columns(engine, db_type, table_name)
    for col in columns:
        await BiColumn.create(
            table_id=bi_table.id,
            name=col["name"],
            data_type=col["data_type"],
            is_primary=col.get("is_primary", False),
            is_nullable=col.get("is_nullable", True),
            default_value=col.get("default_value"),
            comment=col.get("comment"),
        )
        result.columns_synced += 1

    # 采集索引
    indexes = await _fetch_indexes(engine, db_type, table_name)
    for idx in indexes:
        await BiIndex.create(
            table_id=bi_table.id,
            name=idx["name"],
            index_type=idx.get("index_type", ""),
            columns=idx.get("columns", []),
            is_unique=idx.get("is_unique", False),
        )
        result.indexes_synced += 1


async def _fetch_columns(engine: AsyncEngine, db_type: str, table_name: str) -> list[dict]:
    """获取表的列信息。"""
    queries = {
        "postgresql": f"""
            SELECT
                c.column_name as name,
                c.data_type,
                c.is_nullable = 'YES' as is_nullable,
                c.column_default as default_value,
                pg_catalog.col_description(c.table_name::regclass::oid, c.ordinal_position) as comment,
                EXISTS(
                    SELECT 1 FROM information_schema.key_column_usage k
                    JOIN information_schema.table_constraints tc
                        ON k.constraint_name = tc.constraint_name
                    WHERE k.table_name = '{table_name}'
                        AND k.column_name = c.column_name
                        AND tc.constraint_type = 'PRIMARY KEY'
                ) as is_primary
            FROM information_schema.columns c
            WHERE c.table_name = '{table_name}'
            ORDER BY c.ordinal_position
        """,
        "mysql": f"""
            SELECT
                COLUMN_NAME as name,
                DATA_TYPE as data_type,
                IS_NULLABLE = 'YES' as is_nullable,
                COLUMN_DEFAULT as default_value,
                COLUMN_COMMENT as comment,
                COLUMN_KEY = 'PRI' as is_primary
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{table_name}'
            ORDER BY ORDINAL_POSITION
        """,
        "sqlite": f"PRAGMA table_info('{table_name}')",
        "clickhouse": f"""
            SELECT
                name,
                type as data_type,
                1 as is_nullable,
                NULL as default_value,
                name as comment,
                0 as is_primary
            FROM system.columns
            WHERE database = currentDatabase() AND table = '{table_name}'
        """,
        "trino": f"""
            SELECT
                column_name as name,
                data_type,
                is_nullable = 'YES' as is_nullable,
                column_default as default_value,
                NULL as comment,
                0 as is_primary
            FROM information_schema.columns
            WHERE table_schema = current_schema AND table_name = '{table_name}'
            ORDER BY ordinal_position
        """,
    }

    query = queries.get(db_type.lower())
    if query is None:
        return []

    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(query))
            rows = result.fetchall()
            columns = list(result.keys())
            items = [dict(zip(columns, row)) for row in rows]

            # sqlite PRAGMA 特殊处理
            if db_type.lower() == "sqlite":
                return [
                    {
                        "name": r["name"],
                        "data_type": r["type"],
                        "is_nullable": r.get("notnull", 0) == 0,
                        "default_value": r.get("dflt_value"),
                        "comment": None,
                        "is_primary": r.get("pk", 0) != 0,
                    }
                    for r in items
                ]

            return items
    except Exception:
        return []


async def _fetch_indexes(engine: AsyncEngine, db_type: str, table_name: str) -> list[dict]:
    """获取表的索引信息。"""
    queries = {
        "postgresql": f"SELECT indexname as name, indexdef as index_type, tablename = '{table_name}' FROM pg_indexes WHERE tablename = '{table_name}'",
        "mysql": f"""
            SELECT
                INDEX_NAME as name,
                INDEX_TYPE as index_type,
                GROUP_CONCAT(COLUMN_NAME) as columns,
                NON_UNIQUE = 0 as is_unique
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{table_name}'
            GROUP BY INDEX_NAME, INDEX_TYPE, NON_UNIQUE
        """,
        "sqlite": f"PRAGMA index_list('{table_name}')",
        "clickhouse": "SELECT 1 WHERE 1=0",  # ClickHouse 无传统索引
        "trino": "SELECT 1 WHERE 1=0",  # Trino 无传统索引
    }

    query = queries.get(db_type.lower())
    if query is None:
        return []

    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(query))
            rows = result.fetchall()
            columns = list(result.keys())
            items = [dict(zip(columns, row)) for row in rows]

            if db_type.lower() == "sqlite":
                # PRAGMA index_list 返回 seq, name, unique, origin, partial
                indexes = []
                for item in items:
                    idx_name = item.get("name")
                    if idx_name:
                        # 查询索引列
                        idx_cols_result = await conn.execute(text(f"PRAGMA index_info('{idx_name}')"))
                        idx_cols = [row[2] for row in idx_cols_result.fetchall()]
                        indexes.append({
                            "name": idx_name,
                            "index_type": "btree",
                            "columns": idx_cols,
                            "is_unique": bool(item.get("unique", 0)),
                        })
                return indexes

            return items
    except Exception:
        return []


async def _ensure_default_datasource_metadata(datasource: BiDatasource | None) -> None:
    """确保默认数据源的元数据已同步。

    项目历史教训：BiTable 为空时自动触发 sync_datasource。

    Args:
        datasource: 默认数据源（None 表示无默认数据源，跳过）
    """
    if datasource is None:
        return

    # 检查 BiTable 是否为空
    table_count = await BiTable.filter(datasource_id=datasource.id).count()
    if table_count == 0:
        try:
            await sync_datasource(datasource)
        except Exception:
            # 同步失败不阻断启动
            pass
