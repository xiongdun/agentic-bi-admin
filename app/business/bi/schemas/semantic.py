"""AgenticBI Pydantic schemas — 语义层（Metric / Dataset / Chart）。"""

from __future__ import annotations

from app.core.base_schema import PageQueryBase, SchemaBase, make_optional

# ---- Metric ----


class MetricCreate(SchemaBase):
    """创建度量。"""

    name: str
    display_name: str
    description: str | None = None
    sql_template: str
    # sqid 字符串,API 层用 ``decode_id`` 还原成 int
    datasource_id: str
    dataset_id: int | None = None
    unit: str | None = None


class MetricUpdate(SchemaBase):
    """更新度量(name / datasource_id 不可改)。"""

    display_name: str | None = None
    description: str | None = None
    sql_template: str | None = None
    unit: str | None = None
    status_type: str | None = None


class MetricOut(SchemaBase):
    """度量响应。"""

    id: str  # sqid
    name: str
    display_name: str
    description: str | None = None
    sql_template: str
    # sqid 字符串,空字符串表示未关联
    datasource_id: str = ""
    unit: str | None = None
    owner_id: int
    status_type: str
    created_at: str = ""
    updated_at: str = ""


class MetricPageQuery(PageQueryBase):
    """指标分页查询。"""

    name: str | None = None
    # sqid 字符串,API 层 decode 成 int
    datasource_id: str | None = None
    status_type: str | None = None


# ---- Dataset ----


class DatasetCreate(SchemaBase):
    """创建数据集。"""

    name: str
    description: str | None = None
    visibility: str = "private"
    table_ids: list[int] = []
    metric_ids: list[int] = []


DatasetUpdate = make_optional(DatasetCreate, "DatasetUpdate")


class DatasetOut(SchemaBase):
    """数据集响应。"""

    id: int
    name: str
    description: str | None = None
    visibility: str
    owner_id: int
    status_type: str
    table_ids: list[int] = []
    metric_ids: list[int] = []


# ---- Chart ----


class ChartCreate(SchemaBase):
    """创建图表。"""

    name: str
    type: str = "bar"
    dataset_id: int | None = None
    x_field: str | None = None
    y_fields: list[str] | None = None
    agg: str = "sum"
    sql_template: str | None = None
    config_json: dict | None = None


ChartUpdate = make_optional(ChartCreate, "ChartUpdate")


class ChartOut(SchemaBase):
    """图表响应。"""

    id: int
    name: str
    type: str
    dataset_id: int | None = None
    x_field: str | None = None
    y_fields: list[str] | None = None
    agg: str
    config_json: dict | None = None
    sql_template: str | None = None
    owner_id: int


__all__ = [
    "MetricCreate",
    "MetricUpdate",
    "MetricOut",
    "MetricPageQuery",
    "DatasetCreate",
    "DatasetUpdate",
    "DatasetOut",
    "ChartCreate",
    "ChartUpdate",
    "ChartOut",
]
