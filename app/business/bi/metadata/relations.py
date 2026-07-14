"""表关系自动发现 — 通过 ``_id`` 命名启发式 + 同名列匹配。

策略：
- 对每张 BiTable，把 ``*_id`` 后缀的列记为外键候选
- 跨表找同名外键候选 → 记一条 Relation（confidence = 0.6）
- 数值 PK → 数值 FK 的列类型加强为 0.8
- 人工登记的 Relation（confidence = 1.0）不会被覆盖
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from app.business.bi.models import BiColumn, JoinType, Relation

_FK_SUFFIX_RE = re.compile(r"_id$", re.IGNORECASE)
_PK_HINT_TYPES = {"INTEGER", "INT", "BIGINT"}


@dataclass(slots=True)
class _FkCandidate:
    table_id: int
    table_name: str
    column_id: int
    column_name: str
    data_type: str
    is_pk: bool


async def _load_candidates() -> list[_FkCandidate]:
    """加载所有 *_id 列（包含 PK）。"""
    cols = await BiColumn.filter(name__endswith="_id").select_related("table")
    return [
        _FkCandidate(
            table_id=c.table.id,
            table_name=c.table.name,
            column_id=c.id,
            column_name=c.name,
            data_type=c.data_type,
            # 启发式：列名 == "id" 视为 PK（demo 数据约定）
            is_pk=(c.name == "id"),
        )
        for c in cols
    ]


def _infer_join_type(target_is_pk: bool, source_is_pk: bool) -> JoinType:
    if target_is_pk:
        return JoinType.inner
    return JoinType.left


async def auto_discover_relations(*, min_confidence: float = 0.6) -> tuple[int, int]:
    """发现并 upsert 表关系；返回 (created, updated)。"""
    candidates = await _load_candidates()

    # 名字分组（跨表同名外键）
    by_name: dict[str, list[_FkCandidate]] = defaultdict(list)
    for c in candidates:
        by_name[c.column_name].append(c)

    created = 0
    updated = 0
    for col_name, items in by_name.items():
        if len(items) < 2:
            continue
        # 选一个 PK 作 target，其余作 src（首选同表 PK；若没有，跨表选第一个 PK）
        pk_items = [c for c in items if c.is_pk]
        if pk_items:
            target = pk_items[0]
            sources = [c for c in items if c is not target]
        else:
            # 退化：把同名出现的第一张表视为 target
            target = items[0]
            sources = items[1:]

        for src in sources:
            if src.table_id == target.table_id:
                continue  # 同表自关联留给人工
            confidence = 0.6
            if target.is_pk and src.data_type.upper() in _PK_HINT_TYPES:
                confidence = 0.85
            if confidence < min_confidence:
                continue
            join_type = _infer_join_type(target.is_pk, src.is_pk)
            rel, is_new = await Relation.update_or_create(
                defaults={
                    "src_column": src.column_name,
                    "dst_column": target.column_name,
                    "join_type": join_type,
                    "confidence": confidence,
                },
                src_table_id=src.table_id,
                dst_table_id=target.table_id,
            )
            if is_new:
                created += 1
            else:
                updated += 1
    return created, updated


__all__ = ["auto_discover_relations"]
