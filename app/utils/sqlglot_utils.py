"""SQL 方言工具函数 — 通用层。

提供与具体业务无关的 sqlglot 包装：
- 格式化 / 美化
- 方言互转
- 标识符提取（表/列）
- 安全的 parse 包装
- AST 差异比较

业务沙箱规则（白名单 / 租户注入 / 列脱敏）属于 sandbox 层，
不在本模块内。
"""

from __future__ import annotations

from typing import Any, Iterable, Literal

import sqlglot
from sqlglot import exp

DialectName = Literal[
    "sqlite",
    "postgresql",
    "mysql",
    "clickhouse",
    "trino",
    "duckdb",
    "tsql",
    "snowflake",
    "bigquery",
]


def safe_parse(sql: str, dialect: DialectName = "sqlite") -> exp.Expr | None:
    """解析 SQL，失败时返回 None。"""
    try:
        return sqlglot.parse_one(sql, dialect=dialect)
    except Exception:
        return None


def format_sql(sql: str, dialect: DialectName = "sqlite", pretty: bool = True) -> str:
    """格式化 SQL。解析失败时返回原始 SQL。"""
    tree = safe_parse(sql, dialect)
    if tree is None:
        return sql
    return tree.sql(dialect=dialect, pretty=pretty)


def transpile_sql(
    sql: str,
    *,
    read: DialectName = "sqlite",
    write: DialectName | None = None,
    pretty: bool = True,
) -> str:
    """方言转换。`write=None` 时保持原方言。"""
    if write is None or write == read:
        return format_sql(sql, read, pretty=pretty)
    return sqlglot.transpile(sql, read=read, write=write, pretty=pretty)[0]


def extract_table_names(sql: str, dialect: DialectName = "sqlite") -> list[str]:
    """提取 SQL 中出现的表名（去重、保序）。"""
    tree = safe_parse(sql, dialect)
    if tree is None:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for table in tree.find_all(exp.Table):
        name = table.name
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def extract_column_names(sql: str, dialect: DialectName = "sqlite") -> list[str]:
    """提取 SQL 中出现的列名（去重、保序）。不含 `*`。"""
    tree = safe_parse(sql, dialect)
    if tree is None:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for col in tree.find_all(exp.Column):
        name = col.name
        if name == "*" or not name:
            continue
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def extract_functions(sql: str, dialect: DialectName = "sqlite") -> list[str]:
    """提取 SQL 中使用的函数名（去重、大写）。

    sqlglot 把所有 SQL 函数（命名/匿名）都建模为 `exp.Anonymous` 子类，
    用 `this` 携带函数名。
    """
    tree = safe_parse(sql, dialect)
    if tree is None:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for func in tree.find_all(exp.Anonymous):
        name = (func.this or "").upper()
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def ast_diff(
    before_sql: str,
    after_sql: str,
    dialect: DialectName = "sqlite",
) -> dict[str, Any]:
    """比较两棵 AST 之间的结构性差异（用于 LLM 自检 / 解释）。"""
    before = safe_parse(before_sql, dialect)
    after = safe_parse(after_sql, dialect)
    if before is None or after is None:
        return {"ok": False, "reason": "parse_failed"}

    return {
        "ok": True,
        "added_tables": sorted(set(extract_table_names(after_sql, dialect)) - set(extract_table_names(before_sql, dialect))),
        "removed_tables": sorted(set(extract_table_names(before_sql, dialect)) - set(extract_table_names(after_sql, dialect))),
        "added_columns": sorted(set(extract_column_names(after_sql, dialect)) - set(extract_column_names(before_sql, dialect))),
        "removed_columns": sorted(set(extract_column_names(before_sql, dialect)) - set(extract_column_names(after_sql, dialect))),
        "added_functions": sorted(set(extract_functions(after_sql, dialect)) - set(extract_functions(before_sql, dialect))),
    }


def first_non_comment_line(sql: str) -> str:
    """返回 SQL 中第一个非注释行（用于 LLM prompt 提示行号等）。"""
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("--") and not stripped.startswith("#"):
            return stripped
    return ""


def normalize_whitespace(sql: str) -> str:
    """合并多余空白行/空行，保留缩进。"""
    lines = [line.rstrip() for line in sql.splitlines()]
    out: list[str] = []
    blank = False
    for line in lines:
        if not line.strip():
            if not blank:
                out.append("")
            blank = True
        else:
            out.append(line)
            blank = False
    return "\n".join(out).strip()


def detect_dialect(url: str) -> DialectName:
    """根据 SQLAlchemy URL 推断 sqlglot 方言名。

    >>> detect_dialect("sqlite:///foo.db")
    'sqlite'
    >>> detect_dialect("postgresql+asyncpg://...")
    'postgresql'
    """
    url = url.lower()
    for key in ("postgresql", "postgres"):
        if key in url:
            return "postgresql"
    for key in ("mysql", "mariadb"):
        if key in url:
            return "mysql"
    for key in ("clickhouse",):
        if key in url:
            return "clickhouse"
    for key in ("trino", "presto"):
        if key in url:
            return "trino"
    for key in ("sqlite",):
        if key in url:
            return "sqlite"
    return "sqlite"


__all__: Iterable[str] = (
    "DialectName",
    "safe_parse",
    "format_sql",
    "transpile_sql",
    "extract_table_names",
    "extract_column_names",
    "extract_functions",
    "ast_diff",
    "first_non_comment_line",
    "normalize_whitespace",
    "detect_dialect",
)
