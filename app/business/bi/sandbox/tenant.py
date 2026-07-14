"""SQL 沙箱 — 多租户行级隔离。

对 SELECT / UNION 自动在最外层 WHERE 注入 ``tenant_id = :scope``；
如已存在 WHERE 则用 AND 拼接。WITH (CTE) 不会注入，由内层 SELECT 各自
负责。
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
) -> tuple[str, str | None]:
    """在每个最外层 SELECT 上加 ``WHERE tenant_id = :tenant_id``。

    Returns:
        (new_sql, error) — 解析失败或无法注入时 ``error`` 给出原因。
    """
    tree = safe_parse(sql, cast(DialectName, dialect))
    if tree is None:
        return sql, "parse_failed"

    selects = list(tree.find_all(exp.Select))
    if not selects:
        # 没有 SELECT 节点（CET-only / EXPLAIN），不必注入
        return tree.sql(dialect=cast(DialectName, dialect)), None

    for select in selects:
        tenant_cond = exp.EQ(
            this=exp.column(tenant_id_field),
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
