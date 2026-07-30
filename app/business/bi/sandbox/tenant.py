"""多租户行级注入 — 基于 sqlglot AST。

自动给 SELECT 语句注入 WHERE tenant_id = :scope 条件。
跳过无 FROM 子句的 SELECT 节点（项目历史教训）。
"""

from __future__ import annotations

from sqlglot import exp, parse_one


def inject_tenant_filter(
    sql: str,
    tenant_id: int,
    dialect: str = "sqlite",
    tenant_column: str = "tenant_id",
) -> str:
    """给 SQL 注入 WHERE tenant_id = :scope 条件。

    Args:
        sql: 原始 SQL
        tenant_id: 租户 ID
        dialect: 目标方言
        tenant_column: 租户列名（默认 tenant_id）

    Returns:
        注入后的 SQL

    注意:
        - 跳过无 FROM 子句的 SELECT 节点（项目历史教训）
        - 只处理 SELECT / WITH / UNION 语句
        - 对每个有 FROM 的 SELECT 节点添加 WHERE 条件
    """
    if tenant_id is None:
        return sql

    try:
        tree = parse_one(sql, read=dialect)
    except Exception:
        # 解析失败返回原 SQL（让后续校验节点捕获）
        return sql

    # 遍历所有 SELECT 节点
    for select in tree.find_all(exp.Select):
        # 项目历史教训：跳过无 FROM 子句的 SELECT 节点。
        # 注意：sqlglot 30.x 将 from 的 arg key 从 "from" 改为 "from_"（Python 关键字避让），
        # 这里同时兼容两种写法，避免因版本差异导致所有 SELECT 被错误跳过。
        from_clause = select.args.get("from") or select.args.get("from_")
        if from_clause is None:
            continue

        # 构造 WHERE 条件: tenant_id = <tenant_id>
        condition = exp.EQ(
            this=exp.Column(this=exp.to_identifier(tenant_column)),
            expression=exp.Literal.number(tenant_id),
        )

        # 获取现有 WHERE
        existing_where = select.args.get("where")
        if existing_where:
            # AND 组合现有 WHERE 与新条件
            new_where = exp.And(this=existing_where.this, expression=condition)
            select.set("where", exp.Where(this=new_where))
        else:
            select.set("where", exp.Where(this=condition))

    return tree.sql(dialect=dialect)


def should_inject_tenant(data_scope: str) -> bool:
    """判断是否需要注入租户过滤。

    Args:
        data_scope: 用户的 data_scope（all / scope / self / custom）

    Returns:
        True 表示需要注入（data_scope != all）
    """
    return data_scope != "all"
