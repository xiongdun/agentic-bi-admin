"""BI 审计 schema — 搜索/响应/统计/趋势/热力图。"""

from __future__ import annotations

from datetime import datetime

from app.core.base_schema import PageQueryBase, SchemaBase


class AuditSearch(PageQueryBase):
    """审计搜索条件。"""

    user_id: int | None = None
    datasource_id: int | None = None
    action: str | None = None
    status: str | None = None  # success / failed
    start_time: datetime | None = None
    end_time: datetime | None = None
    keyword: str | None = None  # 搜 sql_hash / ip


class AuditLogOut(SchemaBase):
    """审计日志响应（列表/统计项）。"""

    id: str
    user_id: int
    tenant_id: int
    action: str
    datasource_id: str | None = None
    datasource_name: str | None = None
    sql_hash: str | None = None
    row_count: int | None = None
    cost_ms: int | None = None
    ip: str | None = None
    user_agent: str | None = None
    detail: dict | None = None
    status: str | None = None
    created_at: str | None = None


class AuditDetailOut(SchemaBase):
    """审计详情（带原始 SQL）。"""

    log: AuditLogOut
    sql_text: str | None = None


class AuditStatsOut(SchemaBase):
    """审计 KPI 统计。"""

    total: int
    success: int
    failed: int
    total_export_rows: int
    active_users: int
    avg_cost_ms: float


class DailyTrendItem(SchemaBase):
    """按天趋势点。"""

    date: str
    count: int
    success: int
    failed: int


class HeatmapPoint(SchemaBase):
    """时段热力图点（7 天 × 24 小时 = 168 格）。"""

    day_of_week: int  # 0=周日 .. 6=周六
    hour: int
    count: int


class AuditStatsQuery(SchemaBase):
    """统计查询条件。"""

    start_time: datetime | None = None
    end_time: datetime | None = None


class TrendQuery(SchemaBase):
    """趋势查询条件。"""

    days: int = 30
    action: str | None = None


class HeatmapQuery(SchemaBase):
    """热力图查询条件。"""

    days: int = 30


class AuditExportQuery(SchemaBase):
    """CSV 导出查询条件。"""

    user_id: int | None = None
    datasource_id: int | None = None
    action: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
