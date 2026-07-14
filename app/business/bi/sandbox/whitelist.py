"""SQL 沙箱 — AST 白名单 + 禁用函数 / 关键字。

只允许 SELECT / WITH / EXPLAIN，拒绝 INSERT / UPDATE / DELETE / DROP /
TRUNCATE / COPY 等所有写操作。允许的函数名集合按方言可调，禁止调用
``pg_read_file`` / ``load_file`` / ``xp_cmdshell`` 等危险函数。
"""

from __future__ import annotations

from sqlglot import exp

ALLOWED_TOP_LEVEL: tuple[type[exp.Expr], ...] = (exp.Select, exp.Union, exp.Intersect, exp.Except, exp.Subquery, exp.CTE)

ALLOWED_DDL: tuple[type[exp.Expr], ...] = ()  # 永远禁止 DDL

# 永远禁止的关键字（无论包裹在何种 AST 节点里）
FORBIDDEN_KEYWORDS: set[str] = {"INTO", "UNLOAD", "COPY", "EXPORT", "VACUUM", "ATTACH", "DETACH"}

# 各方言共用的危险函数；具体方言可在 QUERY_DANGEROUS_FUNCTIONS 扩展
COMMON_DANGEROUS_FUNCTIONS: set[str] = {
    "pg_read_file",
    "pg_ls_dir",
    "pg_stat_file",
    "lo_import",
    "lo_export",
    "lo_get",
    "lo_put",
    "xp_cmdshell",
    "xp_dirtree",
    "xp_fileexist",
    "load_file",
    "into_outfile",
    "load_extension",
    "system",
    "shell",
    "exec",
    "evaluate",
    "do",
}

# 方言特化：SQLite / PostgreSQL / MySQL / ClickHouse / Trino
DIALECT_DANGEROUS_FUNCTIONS: dict[str, set[str]] = {
    "sqlite": set(),
    "postgresql": set(),
    "mysql": set(),
    "clickhouse": {
        "url",
        "catboost",
        "mysql",
        "postgresql",
        "odbc",
        "jdbc",
        "hdfs",
        "s3",
        "remote",
        "remotesecure",
    },
    "trino": {
        "system_metadata",
    },
}


def get_dangerous_functions(dialect: str) -> set[str]:
    """获取某方言的禁用函数集合（统一大写比对）。"""
    common = {name.upper() for name in COMMON_DANGEROUS_FUNCTIONS}
    extra = {name.upper() for name in DIALECT_DANGEROUS_FUNCTIONS.get(dialect, set())}
    return common | extra


def _is_with_only(tree: exp.Expr) -> bool:
    """``WITH`` 节点单独出现也算合法（``WITH cte AS (...) SELECT ...``）。"""
    return isinstance(tree, exp.CTE) or any(isinstance(node, (exp.Select, exp.Union, exp.Subquery)) for node in tree.walk())


def validate_tree(tree: exp.Expr, *, dialect: str) -> tuple[bool, str | None]:
    """校验 AST 是否在沙箱白名单内。

    Returns:
        (ok, reason) — ``ok=True`` 时 ``reason=None``。
    """
    if tree is None:
        return False, "parse_failed"

    # 1. 顶层节点必须是 SELECT / WITH / UNION 家族
    if not (isinstance(tree, ALLOWED_TOP_LEVEL) or _is_with_only(tree)):
        return False, f"top_level_not_allowed: {type(tree).__name__}"

    # 2. 危险关键字扫描（任何子节点）
    sql_text = tree.sql(dialect=dialect).upper()
    for kw in FORBIDDEN_KEYWORDS:
        # 用 word boundary 避免误判（如 INTO 出现在表名里时）
        if _contains_keyword(sql_text, kw):
            return False, f"forbidden_keyword: {kw}"

    # 3. 危险函数扫描
    dangerous = get_dangerous_functions(dialect)
    for func in tree.find_all(exp.Anonymous):
        name = (func.this or "").upper()
        if name in dangerous:
            return False, f"forbidden_function: {name.lower()}"
    # 一些方言用 exp.Window / exp.AggFunc 建模窗口 / 聚合函数
    for func in tree.find_all(exp.Window):
        this = func.args.get("this")
        if isinstance(this, exp.Anonymous):
            name = (this.this or "").upper()
            if name in dangerous:
                return False, f"forbidden_function: {name.lower()}"

    return True, None


def _contains_keyword(sql_upper: str, keyword: str) -> bool:
    """朴素 word-boundary 检测：A-Z0-9_ 视为单词字符。"""
    kw = keyword.upper()
    padded = f" {sql_upper} "
    token = f" {kw} "
    if token in padded:
        return True
    # 处理 ``column INTO`` 之类语法
    head = padded.find(f" {kw} ")
    if head >= 0:
        before = padded[head - 1]
        after = padded[head + 2 + len(kw)]
        return not (before.isalnum() or before == "_" or after.isalnum() or after == "_")
    return False


__all__ = [
    "ALLOWED_TOP_LEVEL",
    "ALLOWED_DDL",
    "FORBIDDEN_KEYWORDS",
    "COMMON_DANGEROUS_FUNCTIONS",
    "DIALECT_DANGEROUS_FUNCTIONS",
    "get_dangerous_functions",
    "validate_tree",
]
