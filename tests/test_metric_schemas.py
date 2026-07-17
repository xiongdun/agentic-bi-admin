"""Metric Pydantic schema 测试。"""

from app.business.bi.schemas.semantic import (
    MetricCreate,
    MetricOut,
    MetricPageQuery,
    MetricUpdate,
)


def test_metric_create_required_fields():
    m = MetricCreate(
        name="x", display_name="x", sql_template="1", datasource_id="DSQID",
    )
    assert m.name == "x"
    assert m.datasource_id == "DSQID"
    assert m.description is None
    assert m.unit is None
    assert m.dataset_id is None


def test_metric_update_all_optional():
    u = MetricUpdate()
    # name / datasource_id 应在显式 schema 中被剔除
    assert not hasattr(u, "name")
    assert not hasattr(u, "datasource_id")
    # 允许的字段都是 Optional
    assert u.display_name is None
    assert u.description is None
    assert u.sql_template is None
    assert u.unit is None
    assert u.status_type is None


def test_metric_page_query_defaults():
    q = MetricPageQuery()
    assert q.current == 1
    assert q.size == 10  # PageQueryBase 默认 10
    assert q.name is None
    assert q.datasource_id is None
    assert q.status_type is None


def test_metric_out_serializes_camel_case():
    o = MetricOut(
        id="ABC", name="n", display_name="d", sql_template="1",
        unit="元", owner_id=1, status_type="enable",
    )
    dumped = o.model_dump(by_alias=True)
    assert "displayName" in dumped
    assert "sqlTemplate" in dumped
    assert "ownerId" in dumped
    assert "statusType" in dumped
