"""SQL 沙箱 — 列脱敏。

把 ``phone`` / ``email`` / ``id_card`` / ``bank_card`` 列在 SELECT 输出层
替换为对应脱敏表达式，使用 sqlglot 内建 AST 节点（``Substring`` / ``DPipe`` /
``Lower`` 等），由 sqlglot 在序列化时按方言渲染（SQLite → ``substr`` + ``||``，
PostgreSQL → ``substring`` + ``||``，MySQL → ``SUBSTRING`` + ``CONCAT``）。
"""

from __future__ import annotations

import hashlib
from typing import cast

from sqlglot import exp

from app.business.bi.models import MaskType
from app.utils import DialectName, safe_parse


def _substr(column: exp.Column, start: int, length: int) -> exp.Substring:
    """构造 ``SUBSTRING(col, start, length)``。sqlglot 按方言输出对应函数。"""
    return exp.Substring(
        this=column.copy(),
        start=exp.Literal.number(start),
        length=exp.Literal.number(length),
    )


def _concat(parts: list[exp.Expr]) -> exp.Expr:
    """用 ``||`` 串接 N 个表达式，跨方言通用。"""
    if not parts:
        return exp.Literal.string("")
    result = parts[0]
    for p in parts[1:]:
        result = exp.DPipe(this=result, expression=p)
    return result


def _build_mask_expr(column: exp.Column, mask_type: MaskType) -> exp.Expr:
    """构造一个脱敏表达式节点。"""
    if mask_type == MaskType.phone:
        return _concat([_substr(column, 1, 3), exp.Literal.string("****"), _substr(column, -4, 4)])
    if mask_type == MaskType.email:
        # 取 @ 后的整段作为 domain；本地名只保留首字符
        at_idx = exp.Anonymous(
            this="INSTR",
            expressions=[column.copy(), exp.Literal.string("@")],
        )
        # SUBSTR(col, 1, 1) || '****' || SUBSTR(col, at_idx + 1)
        return _concat([
            _substr(column, 1, 1),
            exp.Literal.string("****"),
            exp.Substring(this=column.copy(), start=exp.Add(this=at_idx, expression=exp.Literal.number(1))),
        ])
    if mask_type == MaskType.id_card:
        return _concat([_substr(column, 1, 4), exp.Literal.string("**********"), _substr(column, -4, 4)])
    if mask_type == MaskType.bank_card:
        return _concat([_substr(column, 1, 4), exp.Literal.string("********"), _substr(column, -4, 4)])
    if mask_type == MaskType.partial:
        return _concat([_substr(column, 1, 1), exp.Literal.string("***"), _substr(column, -1, 1)])
    if mask_type == MaskType.full:
        return exp.Literal.string("***")
    if mask_type == MaskType.hash:
        # 平台无关的兜底：MD5 字符串。SQLite 无 MD5 时执行会失败。
        return exp.Anonymous(this="MD5", expressions=[column.copy()])
    return column  # 未识别：原样返回


def apply_masking(
    sql: str,
    *,
    dialect: str,
    masking_rules: dict[str, MaskType],
) -> tuple[str, str | None]:
    """按列名 → MaskType 映射改写 SELECT 列表中匹配的列。

    Args:
        masking_rules: ``{"phone": MaskType.phone, "email": MaskType.email, ...}``
            key 必须与 SELECT 中 ``Column.name`` 大小写一致（建议 snake_case）。

    Returns:
        (new_sql, error) — 解析失败时 ``error`` 给出原因。
    """
    if not masking_rules:
        return sql, None

    tree = safe_parse(sql, cast(DialectName, dialect))
    if tree is None:
        return sql, "parse_failed"

    for col in list(tree.find_all(exp.Column)):
        rule = masking_rules.get(col.name)
        if rule is None:
            continue
        # 找到所在 SELECT 列表项并替换
        parent = col.parent
        if isinstance(parent, exp.Select) and col in (parent.expressions or []):
            idx = parent.expressions.index(col)
            parent.expressions[idx] = exp.alias_(_build_mask_expr(col, rule), alias=col.name)

    return tree.sql(dialect=cast(DialectName, dialect)), None


def mask_string(value: str, mask_type: MaskType) -> str:
    """运行时单值脱敏（用于审计 / 日志）。"""
    if value is None or value == "":
        return value
    if mask_type == MaskType.full:
        return "***"
    if mask_type == MaskType.partial:
        if len(value) <= 2:
            return "*" * len(value)
        return value[0] + "*" * (len(value) - 2) + value[-1]
    if mask_type == MaskType.phone and len(value) >= 7:
        return value[:3] + "****" + value[-4:]
    if mask_type == MaskType.email and "@" in value:
        local, _, domain = value.partition("@")
        return (local[0] if local else "*") + "****@" + domain
    if mask_type == MaskType.id_card and len(value) >= 8:
        return value[:4] + "**********" + value[-4:]
    if mask_type == MaskType.bank_card and len(value) >= 8:
        return value[:4] + "********" + value[-4:]
    if mask_type == MaskType.hash:
        return hashlib.md5(value.encode("utf-8")).hexdigest()  # noqa: S324
    return value


__all__ = ["apply_masking", "mask_string"]
