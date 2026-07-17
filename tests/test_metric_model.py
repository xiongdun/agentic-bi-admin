"""Metric 模型字段存在性测试。"""

from app.business.bi.models.semantic import Metric


def test_metric_has_datasource_relation():
    """Metric 模型必须有 datasource FK 关系。"""
    assert "datasource" in Metric._meta.fields_map, "Metric must have datasource FK"


def test_metric_datasource_fk_to_datasource_table():
    """datasource FK 指向 Datasource 模型（app_system.Datasource）。"""
    fk = Metric._meta.fields_map["datasource"]
    # model_name 引用 app_system.<Model>，与 Datasource 的 app_name 拼接后一致
    assert fk.model_name == "app_system.Datasource"


def test_metric_datasource_fk_on_delete_cascade():
    """datasource FK on_delete 应为 CASCADE。"""
    fk = Metric._meta.fields_map["datasource"]
    # Tortoise 用 on_delete 字符串："CASCADE" / "SET_NULL" 等
    assert str(fk.on_delete).upper() == "CASCADE"


def test_metric_has_owner_id_field():
    """回归：原有字段不能丢。"""
    for name in ("id", "name", "display_name", "sql_template", "unit", "owner_id", "status_type"):
        assert name in Metric._meta.fields_map, f"Missing field {name}"
