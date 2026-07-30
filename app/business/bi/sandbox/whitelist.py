"""SQL 安全白名单校验 — 基于 sqlglot AST。

仅允许 SELECT / WITH；禁止写操作、文件操作、命令执行、导出函数。
无 LIMIT 的 SELECT 自动添加 LIMIT 1000；聚合查询自动添加 LIMIT 100。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlglot import exp, parse_one

from app.core.exceptions import BizError

# SQL 校验失败错误码（4100-4199: BI 模块 SQL 相关）
_SQL_VALIDATION_ERROR_CODE = 4101

# 允许的根语句类型（SELECT / WITH / 集合操作）
ALLOWED_ROOT_TYPES: tuple[type[exp.Expression], ...] = (  # type: ignore[reportPrivateImportUsage]
    exp.Select,
    exp.Union,
    exp.Intersect,
    exp.Except,
    exp.With,
)

# 禁止的语句类型（写操作 / DDL / 通用命令）
FORBIDDEN_TYPES: tuple[type[exp.Expression], ...] = (  # type: ignore[reportPrivateImportUsage]
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.TruncateTable,
    exp.Alter,
    exp.Create,
    exp.Command,
)

# 禁止的函数名（文件操作 / 命令执行 / 导出 / 危险函数）
FORBIDDEN_FUNCTIONS: set[str] = {
    # MySQL 文件操作
    "load_file",
    "into outfile",
    "into dumpfile",
    # PostgreSQL 命令执行 / 文件读取
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "pg_stat_file",
    "lo_import",
    "lo_export",
    # 通用危险函数
    "sleep",
    "benchmark",
    "get_lock",
    "release_lock",
    # PostgreSQL COPY（函数形态兜底）
    "copy",
}

# 方言不兼容函数黑名单 — LLM 训练语料偏 MySQL，容易在 SQLite/PG 等方言下误用
# key: 方言名（sqlglot 命名）；value: 该方言下不存在的函数名集合
# 命中后返回友好错误，避免错误漏到执行层（执行层报错信息更晦涩，如 sqlite3.OperationalError）
# 注意：只列出"该方言确实不存在"的函数；SQLite 3.34+ 已支持 CONCAT/SUBSTRING，不列
_DIALECT_INCOMPATIBLE_FUNCTIONS: dict[str, set[str]] = {
    "sqlite": {
        # MySQL 日期/时间函数（SQLite 用 date('now')/strftime/julianday）
        "curdate",
        "curtime",
        "now",
        "sysdate",
        "datediff",
        "timediff",
        "date_format",
        "str_to_date",
        "unix_timestamp",
        "from_unixtime",
        "last_day",
        "yearweek",
        "weekofyear",
        "dayofweek",
        "dayofmonth",
        "dayofyear",
        "monthname",
        "dayname",
        # MySQL 字符串函数（SQLite 用 || 拼接、substr）
        # 注意: concat/substring SQLite 3.34+ 已支持，不列；concat_ws/locate/lpad 仍不支持
        "concat_ws",
        "group_concat",
        "substring_index",
        "locate",
        "instr",
        "field",
        "lpad",
        "rpad",
        # MySQL 控制流（SQLite 用 CASE WHEN；注意 ifnull SQLite 存在，不列）
        "if",
        # MySQL 数学
        "truncate",
        # PostgreSQL 函数（SQLite 用 strftime）
        "to_char",
        "to_date",
        "to_timestamp",
        "age",
        "extract",
    },
    "postgres": {
        # MySQL 函数在 PostgreSQL 不存在（PG 用 CURRENT_DATE/to_char/||）
        "curdate",
        "curtime",
        "datediff",
        "date_format",
        "str_to_date",
        "unix_timestamp",
        "from_unixtime",
        "substring_index",
        "locate",
        "instr",
        "field",
        "if",
    },
    "clickhouse": {
        # MySQL 函数在 ClickHouse 不存在（CH 用 today()/formatDateTime/concat）
        "curdate",
        "curtime",
        "datediff",
        "date_format",
        "str_to_date",
        "substring_index",
        "locate",
        "instr",
        "field",
        "if",
    },
    "trino": {
        # MySQL 函数在 Trino 不存在（Trino 用 current_date/format_datetime/concat）
        "curdate",
        "curtime",
        "datediff",
        "date_format",
        "str_to_date",
        "substring_index",
        "locate",
        "instr",
        "field",
        "if",
    },
}


def _get_dialect_incompatible_functions(dialect: str) -> set[str]:
    """返回指定方言下不兼容（不存在）的函数名集合。"""
    return _DIALECT_INCOMPATIBLE_FUNCTIONS.get(dialect.lower(), set())


# 禁止访问的系统字典表/视图名（跨方言合并；LLM 习惯走 information_schema 查元数据）
# 命中后返回友好错误，引导用户用业务表或 BiTable 元数据
# 注意：只匹配表名本身（不区分大小写、不含 schema 前缀），覆盖各 DBMS 系统视图
FORBIDDEN_TABLES: set[str] = {
    # 跨方言标准（MySQL/PG/SQLServer/MariaDB 都有）
    "information_schema",  # information_schema.tables / information_schema.columns 等
    # SQLite
    "sqlite_master",
    "sqlite_temp_master",
    "sqlite_schema",
    # PostgreSQL
    "pg_catalog",  # pg_catalog.pg_tables 等（schema 前缀形式）
    "pg_tables",
    "pg_views",
    "pg_class",
    "pg_attribute",
    "pg_namespace",
    "pg_type",
    "pg_proc",
    "pg_database",
    "pg_settings",
    "pg_stat_activity",
    "pg_user",
    "pg_shadow",
    "pg_group",
    # MySQL
    "mysql",  # mysql.user / mysql.db 等（schema 前缀形式）
    "performance_schema",
    "sys",  # sys.schema_table_statistics 等（schema 前缀形式）
    # SQL Server
    "sysobjects",
    "syscolumns",
    "sysindexes",
    "sysusers",
    # ClickHouse
    "system",  # system.tables / system.columns 等（schema 前缀形式）
    # Oracle
    "all_tables",
    "all_tab_columns",
    "all_views",
    "dba_tables",
    "dba_tab_columns",
    "user_tables",
    "user_tab_columns",
    "v$session",
    "v$sql",
}


# 多语句拦截（分号后跟非空白字符）
_MULTI_STMT_PATTERN = re.compile(r";\s*\S")
# 注释拦截
_LINE_COMMENT_PATTERN = re.compile(r"--")
_BLOCK_COMMENT_PATTERN = re.compile(r"/\*")

# 普通查询与聚合查询的默认 LIMIT
_DEFAULT_LIMIT = 1000
_AGGREGATE_LIMIT = 100


@dataclass
class ValidationResult:
    """SQL 校验结果。"""

    is_valid: bool
    sql: str  # 处理后的 SQL（可能加了 LIMIT）
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


def validate_sql(sql: str, dialect: str = "sqlite") -> ValidationResult:
    """校验 SQL 是否符合白名单规则。

    Args:
        sql: 用户输入或 LLM 生成的 SQL
        dialect: 目标数据库方言（postgresql / mysql / clickhouse / trino / sqlite）

    Returns:
        ValidationResult: 校验结果（含处理后的 SQL）

    Raises:
        BizError: SQL 校验失败时抛出（码 4101）
    """
    if not sql or not sql.strip():
        raise BizError(_SQL_VALIDATION_ERROR_CODE, "SQL 校验失败: SQL 为空")

    sql_stripped = sql.strip()

    # 1. 多语句拦截（分号后还有内容）
    if _MULTI_STMT_PATTERN.search(sql_stripped):
        raise BizError(_SQL_VALIDATION_ERROR_CODE, "SQL 校验失败: 禁止多语句执行（检测到分号）")

    # 2. 注释拦截
    if _LINE_COMMENT_PATTERN.search(sql_stripped):
        raise BizError(_SQL_VALIDATION_ERROR_CODE, "SQL 校验失败: 禁止行注释 --")
    if _BLOCK_COMMENT_PATTERN.search(sql_stripped):
        raise BizError(_SQL_VALIDATION_ERROR_CODE, "SQL 校验失败: 禁止块注释 /* */")

    # 3. 解析 AST
    try:
        tree = parse_one(sql_stripped, read=dialect)
    except Exception as e:
        raise BizError(_SQL_VALIDATION_ERROR_CODE, f"SQL 校验失败: 解析错误 - {e}") from e

    if tree is None:
        raise BizError(_SQL_VALIDATION_ERROR_CODE, "SQL 校验失败: 无法解析 SQL")

    # 4. 根节点类型检查
    if isinstance(tree, FORBIDDEN_TYPES):
        raise BizError(
            _SQL_VALIDATION_ERROR_CODE,
            f"SQL 校验失败: 禁止的语句类型 {type(tree).__name__}",
        )

    if not isinstance(tree, ALLOWED_ROOT_TYPES):
        raise BizError(
            _SQL_VALIDATION_ERROR_CODE,
            f"SQL 校验失败: 仅允许 SELECT/WITH，当前为 {type(tree).__name__}",
        )

    # 5. 遍历 AST 检查禁止的函数与 INTO OUTFILE/DUMPFILE
    incompatible_funcs = _get_dialect_incompatible_functions(dialect)
    for node in tree.walk():
        if isinstance(node, exp.Func):
            # 获取函数名：Anonymous 用 node.name（如 CURDATE）；已知函数用 sql_name()（如 DATEDIFF）
            # 注意：date('now') 的 node.name 是 'now'（参数名），不能直接用，必须先判 Anonymous
            if isinstance(node, exp.Anonymous):
                func_name = (node.name or "").lower()
            else:
                func_name = (node.sql_name() or "").lower()
            if not func_name:
                continue
            if func_name in FORBIDDEN_FUNCTIONS:
                raise BizError(
                    _SQL_VALIDATION_ERROR_CODE,
                    f"SQL 校验失败: 禁止的函数 {func_name}",
                )
            # 方言不兼容函数拦截：在执行前给出友好错误，避免漏到 sqlite3.OperationalError 等晦涩报错
            if incompatible_funcs and func_name in incompatible_funcs:
                raise BizError(
                    _SQL_VALIDATION_ERROR_CODE,
                    f"SQL 校验失败: 函数 {func_name} 在 {dialect} 方言下不存在，请使用兼容写法",
                )
        if isinstance(node, exp.Into):
            into_text = node.sql().lower()
            if "outfile" in into_text or "dumpfile" in into_text:
                raise BizError(
                    _SQL_VALIDATION_ERROR_CODE,
                    "SQL 校验失败: 禁止 INTO OUTFILE/DUMPFILE",
                )
        # 系统字典表/视图拦截：禁止 LLM 走 information_schema / sqlite_master 等查元数据
        # 引导用户用业务表或 BiTable 元数据；同时防止误查敏感系统表（如 mysql.user）
        if isinstance(node, exp.Table):
            tbl_name = (node.name or "").lower()
            tbl_db = (node.db or "").lower()
            # 表名或 schema 名任一命中黑名单即拦截
            if tbl_name in FORBIDDEN_TABLES or tbl_db in FORBIDDEN_TABLES:
                # 拼接完整限定名用于错误提示
                full_name = f"{tbl_db}.{tbl_name}" if tbl_db else tbl_name
                raise BizError(
                    _SQL_VALIDATION_ERROR_CODE,
                    f"SQL 校验失败: 禁止访问系统字典表 {full_name}，请只查询业务表",
                )

    # 6. 自动添加 LIMIT
    result_sql = _ensure_limit(tree, dialect)

    return ValidationResult(
        is_valid=True,
        sql=result_sql,
        error=None,
    )


def _ensure_limit(tree: exp.Expression, dialect: str) -> str:  # type: ignore[reportPrivateImportUsage]
    """若无 LIMIT 自动添加；聚合查询加 LIMIT 100，普通 SELECT 加 LIMIT 1000。"""
    main_query = _find_main_query(tree)
    if main_query is None:
        return tree.sql(dialect=dialect)

    # 顶层已有 LIMIT 则不重复添加
    if main_query.args.get("limit") is not None:
        return tree.sql(dialect=dialect)

    # 判断是否为聚合查询（含 GROUP BY 或聚合函数）
    is_aggregate = any(isinstance(node, (exp.Group, exp.AggFunc)) for node in main_query.walk())
    limit_value = _AGGREGATE_LIMIT if is_aggregate else _DEFAULT_LIMIT

    main_query.set("limit", exp.Limit(expression=exp.Literal.number(limit_value)))
    return tree.sql(dialect=dialect)


def _find_main_query(tree: exp.Expression) -> exp.Expression | None:  # type: ignore[reportPrivateImportUsage]
    """定位应添加 LIMIT 的主查询节点。

    - WITH 作为根节点：取最外层 SELECT / 集合操作
    - Select / Union / Intersect / Except：直接返回
    """
    direct_types = (exp.Select, exp.Union, exp.Intersect, exp.Except)
    if isinstance(tree, exp.With):
        for node in tree.walk():
            if isinstance(node, direct_types):
                return node
        return None
    if isinstance(tree, direct_types):
        return tree
    return None
