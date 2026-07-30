"""外键关系提取 — 从数据源的信息模式提取外键关系。

不同数据库有不同的外键查询方式，这里按 db_type 分发。
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

# 不同数据库的外键查询 SQL
_FK_QUERIES = {
    "postgresql": """
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
    """,
    "mysql": """
        SELECT
            TABLE_NAME as table_name,
            COLUMN_NAME as column_name,
            REFERENCED_TABLE_NAME as foreign_table_name,
            REFERENCED_COLUMN_NAME as foreign_column_name,
            CONSTRAINT_NAME as constraint_name
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE REFERENCED_TABLE_NAME IS NOT NULL
    """,
    "sqlite": """
        SELECT
            m.name as table_name,
            fk."from" as column_name,
            m.name as foreign_table_name,
            fk."to" as foreign_column_name,
            'fk_' || m.name || '_' || fk.id as constraint_name
        FROM sqlite_master m
        JOIN pragma_foreign_key_list(m.name) fk
        WHERE m.type = 'table'
    """,
    "clickhouse": "SELECT 1 WHERE 1=0",  # ClickHouse 无外键
    "trino": """
        SELECT
            table_name,
            column_name,
            referenced_table_name AS foreign_table_name,
            referenced_column_name AS foreign_column_name,
            constraint_name
        FROM information_schema.referential_constraints
    """,
}


async def extract_foreign_keys(
    engine: AsyncEngine,
    db_type: str,
) -> list[dict[str, str]]:
    """提取数据源的外键关系。

    Args:
        engine: SQLAlchemy async engine
        db_type: 数据库类型

    Returns:
        外键关系列表，每项含 table_name / column_name / foreign_table_name / foreign_column_name / constraint_name
    """
    query = _FK_QUERIES.get(db_type.lower())
    if query is None:
        return []

    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(query))
            rows = result.fetchall()
            columns = list(result.keys())
            return [dict(zip(columns, row)) for row in rows]
    except Exception:
        # 提取失败不阻断同步流程
        return []
