"""SQL 沙箱 — 多租户行级隔离。

对带 FROM 子句且**主表确实有 tenant_id 字段**的 SELECT 注入
``alias.tenant_id = :scope``;如已存在 WHERE 则用 AND 拼接。无 FROM 的
裸 SELECT(典型: ``SELECT (SELECT ... FROM t) AS x``) 跳过,避免语法错误。

主表无 tenant_id 字段(如 ``categories`` / ``products`` 等公共维表)
时也跳过,避免 ``no such column: tenant_id`` 错误。子查询里的 SELECT 由
各自的 FROM 解析。
"""

from __future__ import annotations

from typing import cast

from sqlglot import exp

from app.utils import DialectName, safe_parse, transpile_sql


def inject_tenant_filter(
    sql: str,
    *,
    tenant_id: int,
    dialect: str,
    tenant_id_field: str = "tenant_id",
    tables_with_tenant: set[str] | None = None,
) -> tuple[str, str | None]:
    """对**主表有 tenant_id 字段**的 SELECT 注入 ``alias.tenant_id = :tenant_id``。

    Args:
        sql: 待注入的 SQL。
        tenant_id: 租户 ID。
        dialect: SQL 方言。
        tenant_id_field: 租户字段名,默认 ``tenant_id``。
        tables_with_tenant: 该数据源下**有 tenant_id 字段的表名集合(全小写)**。
            None 表示不限制 — 所有 FROM 子句都注入(旧行为,不推荐,
            会因维表无 tenant_id 而 ``no such column``)。

    Returns:
        (new_sql, error) — 解析失败或无法注入时 ``error`` 给出原因。
    """
    tree = safe_parse(sql, cast(DialectName, dialect))
    if tree is None:
        return sql, "parse_failed"

    selects = list(tree.find_all(exp.Select))
    if not selects:
        return tree.sql(dialect=cast(DialectName, dialect)), None

    for select in selects:
        # 跳过无 FROM 的裸 SELECT(典型: SELECT (SELECT ...) AS x)
        # 给它注入 WHERE 会变成 SELECT ... WHERE tenant_id=1 → 语法错误
        from_clause = select.args.get("from")
        if from_clause is None:
            continue

        # 拿主表(FROM 子句的第一个表)的真实表名 + 别名
        main_table = from_clause.this
        if not isinstance(main_table, exp.Table):
            continue
        real_name = main_table.name
        alias_name = main_table.alias_or_name

        # 主表不在 tables_with_tenant 集合里 → 跳过(避免维表无 tenant_id 字段)
        if tables_with_tenant is not None and real_name.lower() not in tables_with_tenant:
            continue

        # 用 alias.tenant_id 形式注入,避免多表 JOIN 时字段歧义
        tenant_cond = exp.EQ(
            this=exp.column(tenant_id_field, table=alias_name),
            expression=exp.convert(tenant_id),
        )
        existing_where = select.args.get("where")
        if existing_where is None:
            select.set("where", exp.Where(this=tenant_cond))
        else:
            current = existing_where.args.get("this")
            if current is not None:
                existing_where.set("this", exp.And(this=current, expression=tenant_cond))
            else:
                existing_where.set("this", tenant_cond)

    return tree.sql(dialect=cast(DialectName, dialect)), None


def reparse_dialect(sql: str, *, read: str, write: str) -> str:
    """方言互转（保持语义、改字面量）。"""
    return transpile_sql(sql, read=cast(DialectName, read), write=cast(DialectName, write), pretty=True)


__all__ = ["inject_tenant_filter", "reparse_dialect"]
