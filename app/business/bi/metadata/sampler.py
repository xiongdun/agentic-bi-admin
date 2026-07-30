"""列采样 — 采集表的前 N 行样例数据。

用于 LLM 生成 SQL 时提供数据样例，提升 NL2SQL 准确率。
"""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def sample_table_data(
    engine: AsyncEngine,
    table_name: str,
    sample_rows: int | None = None,
) -> list[dict[str, Any]]:
    """采集表的前 N 行样例数据。

    Args:
        engine: SQLAlchemy async engine
        table_name: 表名
        sample_rows: 采样行数（None 用默认 BI_METADATA_SAMPLE_ROWS）

    Returns:
        样例数据行列表
    """
    if sample_rows is None:
        sample_rows = int(os.getenv("BI_METADATA_SAMPLE_ROWS", "5"))

    if sample_rows <= 0:
        return []

    try:
        async with engine.connect() as conn:
            # 用引号包裹表名防止关键字冲突
            result = await conn.execute(text(f'SELECT * FROM "{table_name}" LIMIT {sample_rows}'))
            rows = result.fetchall()
            if not rows:
                return []
            columns = list(result.keys())
            return [dict(zip(columns, row)) for row in rows]
    except Exception:
        # 采样失败不阻断同步流程
        return []


async def sample_column_values(
    engine: AsyncEngine,
    table_name: str,
    column_name: str,
    sample_rows: int = 5,
) -> list[Any]:
    """采集单列的去重样例值（用于 LLM 理解字段值域）。"""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(f'SELECT DISTINCT "{column_name}" FROM "{table_name}" LIMIT {sample_rows}'))
            return [row[0] for row in result.fetchall()]
    except Exception:
        return []
