# pyright: reportIncompatibleVariableOverride=false
"""AgenticBI 数据模型 — 业务语义子模块。

3 张表：
- Metric：业务度量定义（含 SQL 模板）
- Dataset：用户自建的数据集（M2M Tables / Metrics）
- Chart：用户自建的图表
"""

from __future__ import annotations

from enum import Enum

from tortoise import fields

from app.business.bi.models.metadata import BiTable
from app.core.base_model import AuditMixin, BaseModel, StatusType


class Metric(BaseModel, AuditMixin):
    """业务度量（销售额 = SUM(order.amount WHERE status='paid')）。

    SQL 模板里 ``{table_alias}`` 等占位符在 Agent 拼装时替换。
    """

    id = fields.IntField(primary_key=True, description="度量ID")
    name = fields.CharField(max_length=200, db_index=True, description="业务名（如 销售额）")
    display_name = fields.CharField(max_length=200, description="展示名")
    description = fields.CharField(max_length=500, null=True, blank=True, description="业务描述")
    sql_template = fields.CharField(max_length=2000, description="SQL 模板，如 SUM({order}.amount) WHERE {order}.status='paid'")
    dataset_id: int | None
    dataset: fields.ForeignKeyNullableRelation["Dataset"] = fields.ForeignKeyField(
        "app_system.Dataset",
        null=True,
        blank=True,
        on_delete=fields.SET_NULL,
        related_name="primary_metric_of",
        description="所属数据集（可空）",
    )
    unit = fields.CharField(max_length=50, null=True, blank=True, description="单位（元/件/人）")
    owner_id = fields.IntField(db_index=True, description="业务所有人（系统用户ID）")
    status_type = fields.CharEnumField(enum_type=StatusType, default=StatusType.enable, description="状态")

    class Meta:
        table = "bi_metric"
        table_description = "BI 业务度量"


class DatasetVisibility(str, Enum):
    """数据集可见性。"""

    private = "private"
    team = "team"
    public = "public"


class Dataset(BaseModel, AuditMixin):
    """数据集：用户把若干张物理表 + 度量打包成一个语义单位。

    主要用于 Schema Select Agent 限缩候选表 / 指标集合。
    """

    id = fields.IntField(primary_key=True, description="数据集ID")
    name = fields.CharField(max_length=200, unique=True, description="数据集名")
    description = fields.CharField(max_length=500, null=True, blank=True, description="业务描述")
    owner_id = fields.IntField(db_index=True, description="所有人（系统用户ID）")
    visibility = fields.CharEnumField(enum_type=DatasetVisibility, default=DatasetVisibility.private, description="可见性")
    tables: fields.ManyToManyRelation[BiTable] = fields.ManyToManyField(
        "app_system.BiTable",
        related_name="datasets",
        description="包含的物理表",
    )
    metrics: fields.ManyToManyRelation["Metric"] = fields.ManyToManyField(
        "app_system.Metric",
        related_name="datasets_m2m",
        description="包含的度量（与 dataset_id 字段并存：M2M 是聚合，FK 是首选）",
    )
    status_type = fields.CharEnumField(enum_type=StatusType, default=StatusType.enable, description="状态")

    class Meta:
        table = "bi_dataset"
        table_description = "BI 数据集"


class ChartType(str, Enum):
    """图表类型。"""

    bar = "bar"
    line = "line"
    pie = "pie"
    funnel = "funnel"
    sankey = "sankey"
    radar = "radar"
    heatmap = "heatmap"
    scatter = "scatter"
    area = "area"
    map_ = "map"  # 避关键字


class ChartAgg(str, Enum):
    """聚合方式。"""

    sum_ = "sum"
    avg = "avg"
    cnt = "count"
    max_ = "max"
    min_ = "min"


class Chart(BaseModel, AuditMixin):
    """图表：保存一次查询的 ECharts option。

    ``sql_template`` 留空时由前端每次直接用 dataset_id + x/y 拼装。
    """

    id = fields.IntField(primary_key=True, description="图表ID")
    dataset_id: int | None
    dataset: fields.ForeignKeyNullableRelation[Dataset] = fields.ForeignKeyField(
        "app_system.Dataset",
        null=True,
        blank=True,
        on_delete=fields.SET_NULL,
        related_name="charts",
        description="所属数据集",
    )
    name = fields.CharField(max_length=200, description="图表名")
    type = fields.CharEnumField(enum_type=ChartType, default=ChartType.bar, description="图表类型")
    x_field = fields.CharField(max_length=200, null=True, blank=True, description="X 轴字段")
    y_fields = fields.JSONField(null=True, description="Y 轴字段列表（含聚合方式）")
    agg = fields.CharEnumField(enum_type=ChartAgg, default=ChartAgg.sum_, description="聚合方式")
    config_json = fields.JSONField(null=True, description="ECharts option 完整配置")
    sql_template = fields.CharField(max_length=2000, null=True, blank=True, description="可选的 SQL 模板")
    owner_id = fields.IntField(db_index=True, description="所有人（系统用户ID）")
    status_type = fields.CharEnumField(enum_type=StatusType, default=StatusType.enable, description="状态")

    class Meta:
        table = "bi_chart"
        table_description = "BI 图表"


__all__ = ["Metric", "Dataset", "DatasetVisibility", "ChartType", "ChartAgg", "Chart"]
