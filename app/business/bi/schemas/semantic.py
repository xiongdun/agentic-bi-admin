"""AgenticBI Pydantic schemas — 语义层（Metric / Dataset / Chart）。"""

from __future__ import annotations

from app.core.base_schema import SchemaBase, make_optional

# ---- Metric ----


class MetricCreate(SchemaBase):
    """创建度量。"""

    name: str
    display_name: str
    description: str | None = None
    sql_template: str
    dataset_id: int | None = None
    unit: str | None = None


MetricUpdate = make_optional(MetricCreate, "MetricUpdate")


class MetricOut(SchemaBase):
    """度量响应。"""

    id: int
    name: str
    display_name: str
    description: str | None = None
    sql_template: str
    dataset_id: int | None = None
    unit: str | None = None
    owner_id: int
    status_type: str


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
    "DatasetCreate",
    "DatasetUpdate",
    "DatasetOut",
    "ChartCreate",
    "ChartUpdate",
    "ChartOut",
]
