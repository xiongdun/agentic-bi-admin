"""AgenticBI 列脱敏 service — 按角色取列脱敏规则。

入口：
- ``get_masking_rules(role_code, datasource_id) -> dict[str, MaskType]``
  返回 ``{column_name: mask_type}``；调用方传给 ``PipelineContext.masking_rules``。

实现要点：
- 关联 ``ColumnMasking`` ↔ ``BiColumn`` ↔ ``BiTable`` ↔ ``Datasource``
- 不存在规则时返回空 dict（pipeline 不脱敏）
- 失败不抛 — 审计缺规则不能让业务请求挂掉
"""

from __future__ import annotations

from app.business.bi.models import BiColumn, BiTable, ColumnMasking, MaskType
from app.core.log import log


async def get_masking_rules(
    *,
    role_code: str | None,
    datasource_id: int | None,
) -> dict[str, MaskType]:
    """按角色 + 数据源取该角色可见的列脱敏规则。

    Returns:
        ``{column_name: MaskType}``。``role_code`` 为 None 时返回空（保守）。
    """
    if not role_code or not datasource_id:
        return {}
    try:
        rows = await ColumnMasking.filter(role_code=role_code).filter(column__table__datasource_id=datasource_id).prefetch_related("column", "column__table").all()
    except Exception as exc:  # noqa: BLE001
        log.warning("bi.masking: query ColumnMasking failed: %s", exc)
        return {}
    rules: dict[str, MaskType] = {}
    for cm in rows:
        col: BiColumn = cm.column
        tbl: BiTable = col.table
        # 输出列名（无表名前缀，pipeline 的 masking 改写按列名匹配）
        rules[col.name] = cm.mask_type
        # 同时记录带表名的别名（pipeline 也可选用）
        rules[f"{tbl.name}.{col.name}"] = cm.mask_type
    return rules


async def upsert_masking(
    *,
    column_id: int,
    role_code: str,
    mask_type: str,
    user_id: int,
) -> ColumnMasking:
    """创建或更新一条脱敏策略。"""
    cm, _ = await ColumnMasking.update_or_create(
        column_id=column_id,
        role_code=role_code,
        defaults={
            "mask_type": MaskType(mask_type),
            "created_by": user_id,
            "updated_by": user_id,
        },
    )
    return cm


__all__ = ["get_masking_rules", "upsert_masking"]
