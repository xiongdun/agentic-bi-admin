"""SQL 方言转换 — 基于 sqlglot。

支持 PostgreSQL / MySQL / ClickHouse / Trino / SQLite 之间的方言转换。
"""

from __future__ import annotations

from sqlglot import parse_one, transpile

# 支持的方言
SUPPORTED_DIALECTS = {"postgresql", "mysql", "clickhouse", "trino", "sqlite"}

# sqlglot 方言名映射（项目命名 -> sqlglot 命名）
_DIALECT_MAP = {
    "postgresql": "postgres",
    "postgres": "postgres",
    "mysql": "mysql",
    "clickhouse": "clickhouse",
    "trino": "trino",
    "sqlite": "sqlite",
}


def to_dialect(sql: str, target_dialect: str, source_dialect: str | None = None) -> str:
    """将 SQL 转换为目标方言。

    Args:
        sql: 原始 SQL
        target_dialect: 目标方言（postgresql / mysql / clickhouse / trino / sqlite）
        source_dialect: 源方言（None 表示自动检测）

    Returns:
        转换后的 SQL

    Raises:
        ValueError: 不支持的方言
    """
    target = _DIALECT_MAP.get(target_dialect.lower())
    if target is None:
        raise ValueError(f"不支持的方言: {target_dialect}，支持: {SUPPORTED_DIALECTS}")

    source = _DIALECT_MAP.get(source_dialect.lower()) if source_dialect else None

    try:
        # transpile 返回列表，取第一个
        result = transpile(sql, read=source, write=target, pretty=False)
        return result[0] if result else sql
    except Exception:
        # 转换失败返回原 SQL（让后续校验节点捕获语法错误）
        return sql


def get_dialect_name(db_type: str) -> str:
    """将数据库类型转换为 sqlglot 方言名。

    Args:
        db_type: 数据库类型（postgresql / mysql / clickhouse / trino / sqlite）

    Returns:
        sqlglot 方言名
    """
    return _DIALECT_MAP.get(db_type.lower(), "sqlite")


def format_sql(sql: str, dialect: str = "sqlite") -> str:
    """格式化 SQL（美化输出）。"""
    target = _DIALECT_MAP.get(dialect.lower(), "sqlite")
    try:
        tree = parse_one(sql, read=target)
        return tree.sql(dialect=target, pretty=True)
    except Exception:
        return sql
