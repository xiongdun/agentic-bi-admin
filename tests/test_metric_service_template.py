"""test_metric_template 服务测试。"""

import uuid

import pytest
import pytest_asyncio
from tortoise import Tortoise

from app.business.bi.models.metadata import Datasource, DatasourceType
from app.business.bi.services.metric import create_metric, validate_template

_LITE_TORTOISE_ORM = {
    "connections": {"default": "sqlite://:memory:"},
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
    d = await Datasource.create(
        name=f"ds_tpl_{uuid.uuid4().hex[:8]}",
        type=DatasourceType.sqlite, database=":memory:",
        tenant_id=1, is_default=False,
    )
    return d


@pytest.mark.asyncio(loop_scope="session")
async def test_template_with_placeholder_success(ds):
    m = await create_metric(
        name="sales", display_name="销售额",
        sql_template="SUM({order}.amount) WHERE {order}.status='paid'",
        datasource_id=ds.id, owner_id=1,
    )
    result = await validate_template(m.id)
    assert result["success"] is True
    assert "order" in result["placeholders"]


@pytest.mark.asyncio(loop_scope="session")
async def test_template_without_placeholder_fails(ds):
    m = await create_metric(
        name="bad", display_name="bad",
        sql_template="SUM(amount)",  # 无占位符
        datasource_id=ds.id, owner_id=1,
    )
    result = await validate_template(m.id)
    assert result["success"] is False
    assert "占位符" in result["error"]


@pytest.mark.asyncio(loop_scope="session")
async def test_template_with_dangerous_sql_denied(ds):
    m = await create_metric(
        name="danger", display_name="danger",
        sql_template="DROP TABLE users",  # 无占位符 + 白名单拒绝
        datasource_id=ds.id, owner_id=1,
    )
    result = await validate_template(m.id)
    # 无占位符先 fail;不会到达白名单校验
    assert result["success"] is False


@pytest.mark.asyncio(loop_scope="session")
async def test_template_with_placeholder_but_dangerous_op_fails(ds):
    """占位符存在但模板里出现禁止操作 → 白名单拒绝。"""
    m = await create_metric(
        name="danger2", display_name="danger2",
        sql_template="DROP TABLE {order}",  # 有占位符,但 DROP 被拒
        datasource_id=ds.id, owner_id=1,
    )
    result = await validate_template(m.id)
    assert result["success"] is False


@pytest.mark.asyncio(loop_scope="session")
async def test_template_metric_not_found():
    result = await validate_template(99999)
    assert result["success"] is False
    assert "not found" in result["error"]


@pytest.mark.asyncio(loop_scope="session")
async def test_template_returns_metadata_on_success(ds):
    m = await create_metric(
        name="orders_count", display_name="订单数",
        sql_template="COUNT({order}.id)",
        datasource_id=ds.id, owner_id=1,
    )
    result = await validate_template(m.id)
    assert result["success"] is True
    assert result["datasource"].startswith("ds_tpl_")
    assert result["dialect"] == "sqlite"
    assert result["placeholders"] == ["order"]
