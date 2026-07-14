"""AgenticBI 元数据中心 API — 表/列查询。"""

from __future__ import annotations

from fastapi import APIRouter

from app.business.bi.schemas.datasource import BiTableSearch
from app.business.bi.services.metadata_api import get_table_detail, list_tables
from app.core.base_schema import Success, SuccessExtra
from app.core.sqids import encode_id
from app.core.types import SqidPath

router = APIRouter(prefix="/metadata")


@router.post("/tables/search", name="bi.tables.search", summary="搜索已同步的表")
async def search_tables(obj_in: BiTableSearch):
    """分页列出已同步的表（按数据源/表名模糊）。"""
    total, tables = await list_tables(
        datasource_id=obj_in.datasource_id,
        name=obj_in.name,
        offset=(obj_in.current - 1) * obj_in.size,
        limit=obj_in.size,
    )
    items = [
        {
            "id": encode_id(t.id),
            "datasourceId": encode_id(t.datasource_id),
            "name": t.name,
            "schemaName": t.schema_name,
            "description": t.description,
            "tags": t.tags or [],
            "version": t.version,
            "lastSyncedAt": t.last_synced_at.isoformat() if t.last_synced_at else None,
            "columnCount": getattr(t, "column_count", 0),
        }
        for t in tables
    ]
    return SuccessExtra(
        data={"records": items},
        total=total,
        current=obj_in.current,
        size=obj_in.size,
    )


@router.get("/tables/{item_id}", name="bi.tables.get", summary="获取表详情（含列）")
async def get_table(item_id: SqidPath):
    """返回表 + 全部列定义。"""
    table = await get_table_detail(item_id)
    return Success(
        data={
            "id": encode_id(table.id),
            "datasourceId": encode_id(table.datasource_id),
            "name": table.name,
            "schemaName": table.schema_name,
            "description": table.description,
            "tags": table.tags or [],
            "version": table.version,
            "lastSyncedAt": table.last_synced_at.isoformat() if table.last_synced_at else None,
            "columns": [
                {
                    "id": encode_id(c.id),
                    "name": c.name,
                    "dataType": c.data_type,
                    "nullable": c.nullable,
                    "description": c.description,
                    "isDimension": c.is_dimension,
                    "isMetric": c.is_metric,
                    "sampleValues": c.sample_values or [],
                    "ordinal": c.ordinal,
                }
                for c in table.columns
            ],
        }
    )
