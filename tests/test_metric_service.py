"""Metric service 单元测试。

不依赖 conftest.py 的全量 FastAPI 应用，直接在 SQLite 内存库中初始化业务表。
"""

import uuid

import pytest
import pytest_asyncio
from tortoise import Tortoise

from app.business.bi.models.metadata import Datasource, DatasourceType
from app.business.bi.models.semantic import Metric
from app.business.bi.services.metric import (
    create_metric, delete_metric, get_metric,
    list_for_intent, list_metrics, update_metric,
)

# 最小化 Tortoise 配置：只装业务模型，避免拉起整个 system 库导致测试慢
_LITE_TORTOISE_ORM = {
    "connections": {
        "default": "sqlite://:memory:",
    },
    "apps": {
        "app_system": {
            "models": ["app.business.bi.models"],
            "default_connection": "default",
        },
    },
    "use_tz": False,
    "timezone": "Asia/Shanghai",
}


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def lite_db():
    await Tortoise.init(config=_LITE_TORTOISE_ORM)
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()


@pytest_asyncio.fixture(loop_scope="session")
async def ds(lite_db):
    """每个测试一个独立 datasource。"""
    d = await Datasource.create(
        name=f"ds_test_{uuid.uuid4().hex[:8]}",
        type=DatasourceType.sqlite,
        database=":memory:",
        tenant_id=1,
        is_default=False,
    )
    return d


@pytest.mark.asyncio(loop_scope="session")
async def test_create_and_get_metric(ds):
    m = await create_metric(
        name="test_sales", display_name="测试销售额",
        sql_template="SUM({order}.amount)", datasource_id=ds.id,
        description="x", unit="元", owner_id=1,
    )
    assert m.id is not None
    fetched = await get_metric(m.id)
    assert fetched is not None
    assert fetched.name == "test_sales"
    assert fetched.datasource_id == ds.id


@pytest.mark.asyncio(loop_scope="session")
async def test_list_metrics_filter_by_datasource(ds):
    ds2 = await Datasource.create(
        name=f"ds_metric_2_{uuid.uuid4().hex[:8]}",
        type=DatasourceType.sqlite, database=":memory:",
        tenant_id=1, is_default=False,
    )
    await create_metric(
        name="m1", display_name="m1", sql_template="1",
        datasource_id=ds.id, owner_id=1,
    )
    await create_metric(
        name="m2", display_name="m2", sql_template="2",
        datasource_id=ds2.id, owner_id=1,
    )

    total1, rows1 = await list_metrics(datasource_id=ds.id)
    total2, rows2 = await list_metrics(datasource_id=ds2.id)
    assert total1 == 1
    assert total2 == 1
    assert rows1[0].name == "m1"
    assert rows2[0].name == "m2"


@pytest.mark.asyncio(loop_scope="session")
async def test_list_metrics_name_filter_icontains(ds):
    await create_metric(
        name="revenue_q1", display_name="Q1 收入", sql_template="1",
        datasource_id=ds.id, owner_id=1,
    )
    await create_metric(
        name="cost_q1", display_name="Q1 成本", sql_template="2",
        datasource_id=ds.id, owner_id=1,
    )
    total, rows = await list_metrics(name="revenue", datasource_id=ds.id)
    assert total == 1
    assert rows[0].name == "revenue_q1"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_metric(ds):
    m = await create_metric(
        name="m3", display_name="m3", sql_template="3",
        datasource_id=ds.id, owner_id=1,
    )
    # status_type 字段是 CharEnumField,存 enum 的 value("2"=disable)
    updated = await update_metric(m.id, display_name="新展示名", status_type="2")
    assert updated.display_name == "新展示名"
    assert str(updated.status_type) == "2"


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_metric(ds):
    m = await create_metric(
        name="m4", display_name="m4", sql_template="4",
        datasource_id=ds.id, owner_id=1,
    )
    await delete_metric(m.id)
    assert await get_metric(m.id) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_list_for_intent_returns_minimal_fields(ds):
    await create_metric(
        name="m5", display_name="m5", sql_template="SUM({order}.amount)",
        datasource_id=ds.id, owner_id=1,
    )
    rows = await list_for_intent(datasource_id=ds.id)
    assert len(rows) == 1
    r = rows[0]
    assert set(r.keys()) == {"id", "name", "description", "sql_template"}
    assert r["name"] == "m5"


@pytest.mark.asyncio(loop_scope="session")
async def test_list_for_intent_excludes_disabled(ds):
    m = await create_metric(
        name="disabled_one", display_name="d", sql_template="1",
        datasource_id=ds.id, owner_id=1,
    )
    await update_metric(m.id, status_type="2")  # StatusType.disable
    rows = await list_for_intent(datasource_id=ds.id)
    assert rows == []
