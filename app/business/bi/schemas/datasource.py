"""AgenticBI Pydantic schemas — 数据源 / 元数据子模块。"""

from __future__ import annotations

from app.core.base_schema import PageQueryBase, SchemaBase, make_optional
from app.core.types import SqidId, SqidPath

# ---- Datasource ----


class DatasourceCreate(SchemaBase):
    """创建数据源请求。"""

    name: str
    type: str  # DatasourceType value
    database: str
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    is_default: bool = False
    remark: str | None = None


DatasourceUpdate = make_optional(DatasourceCreate, "DatasourceUpdate")


class DatasourceOut(SchemaBase):
    """数据源响应。"""

    id: int
    name: str
    type: str
    host: str | None = None
    port: int | None = None
    database: str
    username: str | None = None
    is_default: bool
    last_synced_at: str | None = None
    status_type: str
    remark: str | None = None
    tenant_id: int


class DatasourceSearch(PageQueryBase):
    """数据源搜索。"""

    name: str | None = None
    type: str | None = None


class DatasourceTestResponse(SchemaBase):
    """测试连接响应。"""

    ok: bool
    error: str | None = None


class DatasourceSyncResponse(SchemaBase):
    """同步响应。"""

    tables: int
    columns: int
    errors: list[str]


# ---- Table / Column ----


class BiColumnOut(SchemaBase):
    """列响应。"""

    id: int
    name: str
    data_type: str
    nullable: bool
    description: str | None = None
    is_dimension: bool
    is_metric: bool
    sample_values: list[str] | None = None
    ordinal: int


class BiTableOut(SchemaBase):
    """表响应。"""

    id: int
    name: str
    schema_name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    version: int
    last_synced_at: str | None = None
    column_count: int = 0
    columns: list[BiColumnOut] | None = None


class BiTableSearch(PageQueryBase):
    """表搜索。"""

    datasource_id: int | None = None
    name: str | None = None


__all__ = [
    "DatasourceCreate",
    "DatasourceUpdate",
    "DatasourceOut",
    "DatasourceSearch",
    "DatasourceTestResponse",
    "DatasourceSyncResponse",
    "BiColumnOut",
    "BiTableOut",
    "BiTableSearch",
    "SqidId",
    "SqidPath",
]
