"""BI 元数据查询路由 — 表 / 列只读 CRUD + 表详情聚合。

元数据由数据源同步产生（``POST /datasources/{id}/sync``），本路由仅提供
只读查询入口，不开放写接口。表详情接口聚合列 / 索引 / 外键，供前端
"表结构抽屉" 一次性拉取。

路由前缀由 ``api/__init__.py`` 聚合后再挂到 ``/business/bi``，最终 URL 形如
``/api/v1/business/bi/tables/search``。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.business.bi.controllers import bi_column_controller, bi_table_controller
from app.business.bi.schemas import BiColumnSearch, BiTableSearch
from app.business.bi.services import get_table_detail, list_columns, list_tables
from app.utils import (
    CRUDRouter,
    SearchFieldConfig,
    SqidPath,
    Success,
    SuccessExtra,
)

# ---- 表元数据：只读 CRUD（list / get）----
table_crud = CRUDRouter(
    prefix="/tables",
    controller=bi_table_controller,
    list_schema=BiTableSearch,
    search_fields=SearchFieldConfig(contains_fields=["name"]),
    summary_prefix="表元数据",
    enable_routes={"list", "get"},
    route_key_prefix="bi.tables",
)


@table_crud.override("list")
async def _list_tables(obj_in: BiTableSearch):
    """列出表元数据（支持按 datasource_id / name 过滤）。

    ``datasource_id`` 在 schema 中为 sqid 字符串，由 service 层解码后精确匹配。
    """
    total, records = await list_tables(obj_in)
    return SuccessExtra(data={"records": records}, total=total, current=obj_in.current, size=obj_in.size)


# ---- 列元数据：只读 CRUD（list / get）----
column_crud = CRUDRouter(
    prefix="/columns",
    controller=bi_column_controller,
    list_schema=BiColumnSearch,
    search_fields=SearchFieldConfig(contains_fields=["name"]),
    summary_prefix="列元数据",
    enable_routes={"list", "get"},
    route_key_prefix="bi.columns",
)


@column_crud.override("list")
async def _list_columns(obj_in: BiColumnSearch):
    """列出列元数据（支持按 table_id / name 过滤）。"""
    total, records = await list_columns(obj_in)
    return SuccessExtra(data={"records": records}, total=total, current=obj_in.current, size=obj_in.size)


# ---- 聚合 router ----
router = APIRouter()
router.include_router(table_crud.router)
router.include_router(column_crud.router)


@router.get(
    "/tables/{table_id}/detail",
    summary="查看表详情（含列/索引/外键）",
    name="bi.tables.detail",
)
async def get_table_detail_endpoint(table_id: SqidPath):
    """获取表详情，聚合列 / 索引 / 外键元数据。"""
    return Success(data=await get_table_detail(table_id))
