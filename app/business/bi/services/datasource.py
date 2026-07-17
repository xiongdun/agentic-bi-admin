"""数据源 service — CRUD + 连接测试 + 元数据同步触发。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from tortoise.queryset import QuerySet

from app.business.bi.metadata.sync import sync_datasource
from app.business.bi.models import Datasource, DatasourceType, Tenant
from app.business.bi.sandbox.executor import _sqlite_url
from app.utils import encrypt


def _now_naive() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


def _build_url(ds: Datasource) -> str:
    if ds.type == DatasourceType.sqlite:
        return _sqlite_url(ds)
    raise ValueError(f"Phase 1 仅支持 sqlite；got {ds.type.value}")


async def test_connection(ds: Datasource) -> tuple[bool, str | None]:
    """尝试连一下数据源；返回 (ok, error_msg)。"""
    try:
        url = _build_url(ds)
        engine = create_async_engine(url, echo=False, future=True)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        finally:
            await engine.dispose()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    return True, None


async def create_datasource(
    *,
    user_id: int,
    tenant: Tenant | None = None,
    name: str,
    type: str,
    database: str,
    username: str | None = None,
    password: str | None = None,
    host: str | None = None,
    port: int | None = None,
    is_default: bool = False,
    remark: str | None = None,
) -> Datasource:
    """新建数据源（密码 Fernet 加密）。

    接受 ``tenant: Tenant`` 或 ``tenant_id: int``（兼容现有 API 调用）。
    """
    if tenant is None:
        # fallback: 取默认租户
        tenant = await Tenant.filter(code="default").first()
        if tenant is None:
            tenant = await Tenant.create(code="default", name="默认租户", is_active=True)
    password_enc = encrypt(password) if password else None
    ds = await Datasource.create(
        name=name,
        type=DatasourceType(type),
        host=host,
        port=port,
        database=database,
        username=username,
        password_enc=password_enc,
        tenant_id=tenant.id,
        is_default=is_default,
        remark=remark,
        created_by=user_id,
        updated_by=user_id,
    )
    # 审计埋点
    try:
        from app.business.bi.services.audit import record_audit

        await record_audit(
            action="datasource_create",
            user_id=user_id,
            tenant_id=tenant.id,
            datasource=ds,
            detail={"name": name, "type": type, "database": database, "host": host, "port": port},
        )
    except Exception:  # noqa: BLE001
        pass
    return ds


async def update_datasource(ds_id: int, **fields) -> Datasource:
    """按 id 更新字段；若 password 字段在 fields 中，自动 Fernet 加密。"""
    if "password" in fields:
        raw = fields.pop("password")
        fields["password_enc"] = encrypt(raw) if raw else None
    if "type" in fields and isinstance(fields["type"], str):
        fields["type"] = DatasourceType(fields["type"])
    ds = await Datasource.filter(id=ds_id).first()
    if ds is None:
        from tortoise.exceptions import DoesNotExist

        raise DoesNotExist(f"Datasource<{ds_id}> not found")
    for k, v in fields.items():
        setattr(ds, k, v)
    await ds.save()
    # 审计埋点
    try:
        from app.business.bi.services.audit import record_audit

        # 不在 detail 里记录密码
        safe_fields = {k: v for k, v in fields.items() if "password" not in k.lower()}
        await record_audit(
            action="datasource_update",
            datasource=ds,
            detail={"updated_fields": list(safe_fields.keys())},
        )
    except Exception:  # noqa: BLE001
        pass
    return ds


async def delete_datasource(ds_id: int) -> None:
    """按 id 删除数据源（级联 bi_table / bi_column）。"""
    ds = await Datasource.filter(id=ds_id).first()
    if ds is None:
        return
    ds_name = ds.name
    ds_id_val = ds.id
    await ds.delete()
    # 审计埋点
    try:
        from app.business.bi.services.audit import record_audit

        await record_audit(
            action="datasource_delete",
            datasource_id=ds_id_val,
            detail={"name": ds_name},
        )
    except Exception:  # noqa: BLE001
        pass


async def get_datasource(ds_id: int) -> Datasource | None:
    return await Datasource.filter(id=ds_id).first()


async def test_connection_by_id(ds_id: int) -> tuple[bool, str | None]:
    ds = await get_datasource(ds_id)
    if ds is None:
        return False, f"Datasource<{ds_id}> not found"
    return await test_connection(ds)


async def trigger_sync(ds: Datasource) -> tuple[int, int, list[str]]:
    """触发一次元数据同步，返回 (tables, columns, errors)。"""
    result = await sync_datasource(ds)
    return result.tables, result.columns, result.errors


async def trigger_sync_by_id(ds_id: int) -> tuple[int, int, list[str]]:
    ds = await get_datasource(ds_id)
    if ds is None:
        return 0, 0, [f"Datasource<{ds_id}> not found"]
    return await trigger_sync(ds)


def list_datasources(*, name: str | None = None, type_: str | None = None) -> QuerySet[Datasource]:
    """构造数据源 QuerySet（不执行查询）。"""
    qs = Datasource.all()
    if name:
        qs = qs.filter(name__icontains=name)
    if type_:
        qs = qs.filter(type=DatasourceType(type_))
    return qs.order_by("-id")


async def ensure_default_datasource_path() -> None:
    """确保默认 SQLite 文件存在（首次启动 demo 库时占位）。"""
    project_root = Path(__file__).resolve().parents[4]
    db = project_root / "bi_demo.db"
    if not db.exists():
        db.touch()


__all__ = [
    "create_datasource",
    "update_datasource",
    "delete_datasource",
    "get_datasource",
    "list_datasources",
    "test_connection",
    "test_connection_by_id",
    "trigger_sync",
    "trigger_sync_by_id",
    "ensure_default_datasource_path",
]
