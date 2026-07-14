"""AgenticBI 数据源 API — CRUD + 测试连接 + 同步元数据。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.business.bi.schemas.datasource import (
    DatasourceCreate,
    DatasourceSearch,
    DatasourceTestResponse,
    DatasourceUpdate,
)
from app.business.bi.services import datasource as ds_service
from app.business.bi.services.metadata_api import ensure_demo_data
from app.core.base_schema import Fail, Success, SuccessExtra
from app.core.ctx import get_current_user_id
from app.core.dependency import require_buttons
from app.core.sqids import encode_id
from app.core.types import SqidPath

router = APIRouter(prefix="/datasources")


@router.post("/search", name="bi.datasources.search", summary="搜索数据源")
async def search_datasources(obj_in: DatasourceSearch):
    """分页搜索数据源（按名称/类型模糊）。"""
    qs = ds_service.list_datasources(name=obj_in.name, type_=obj_in.type)
    total = await qs.count()
    records = await qs.offset((obj_in.current - 1) * obj_in.size).limit(obj_in.size)
    items = [
        {
            "id": encode_id(d.id),
            "name": d.name,
            "type": d.type.value,
            "host": d.host,
            "port": d.port,
            "database": d.database,
            "username": d.username,
            "isDefault": d.is_default,
            "lastSyncedAt": d.last_synced_at.isoformat() if d.last_synced_at else None,
            "statusType": d.status_type.value,
            "remark": d.remark,
            "tenantId": d.tenant_id,
        }
        for d in records
    ]
    return SuccessExtra(
        data={"records": items},
        total=total,
        current=obj_in.current,
        size=obj_in.size,
    )


@router.post("", name="bi.datasource.create", summary="创建数据源", dependencies=[require_buttons("B_BI_DS_CREATE")])
async def create_datasource(obj_in: DatasourceCreate, request: Request):
    """创建数据源（密码自动 Fernet 加密）。"""
    user_id = get_current_user_id()
    if user_id is None:
        return Fail(msg="无法识别当前用户")
    ds = await ds_service.create_datasource(
        user_id=user_id,
        name=obj_in.name,
        type=obj_in.type,
        database=obj_in.database,
        username=obj_in.username,
        password=obj_in.password,
        host=obj_in.host,
        port=obj_in.port,
        is_default=obj_in.is_default,
        remark=obj_in.remark,
    )
    return Success(msg="创建成功", data={"createdId": encode_id(ds.id)})


@router.patch("/{item_id}", name="bi.datasource.update", summary="更新数据源", dependencies=[require_buttons("B_BI_DS_CREATE")])
async def update_datasource(item_id: SqidPath, obj_in: DatasourceUpdate):  # type: ignore[valid-type]
    """更新数据源（密码字段若传入则重新加密）。"""
    ds = await ds_service.update_datasource(item_id, **obj_in.model_dump(exclude_unset=True))
    return Success(msg="更新成功", data={"updatedId": encode_id(ds.id)})


@router.delete("/{item_id}", name="bi.datasource.delete", summary="删除数据源", dependencies=[require_buttons("B_BI_DS_DELETE")])
async def delete_datasource(item_id: SqidPath):
    """删除数据源（同时会级联删除 bi_table/bi_column）。"""
    await ds_service.delete_datasource(item_id)
    return Success(msg="删除成功")


@router.post("/{item_id}/test", name="bi.datasources.test", summary="测试数据源连接", dependencies=[require_buttons("B_BI_DS_TEST")])
async def test_datasource_connection(item_id: SqidPath) -> DatasourceTestResponse:
    """测试连接并返回 (ok, error)。"""
    ok, err = await ds_service.test_connection_by_id(item_id)
    return DatasourceTestResponse(ok=ok, error=err)


@router.post("/{item_id}/sync", name="bi.datasources.sync", summary="同步数据源元数据", dependencies=[require_buttons("B_BI_DS_SYNC")])
async def sync_datasource_metadata(item_id: SqidPath):
    """拉取数据源全量 schema（SQLite / Phase 1）并写入 bi_table / bi_column。"""
    tables, columns, errors = await ds_service.trigger_sync_by_id(item_id)
    return Success(
        msg="同步完成",
        data={"tables": tables, "columns": columns, "errors": errors},
    )


@router.post("/demo", name="bi.datasources.demo", summary="生成/重建电商 demo 数据库")
async def bootstrap_demo_datasource():
    """无 demo.db 时一键生成 SQLite 电商示例库（10 个产品分类、50 个商品、5 千条订单）。

    用于 Phase 1 演示"本月各产品线销售额排名"端到端场景。
    """
    result = await ensure_demo_data()
    return Success(msg="demo 库就绪", data=result)
