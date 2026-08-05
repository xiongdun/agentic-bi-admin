"""BiExport API 路由 — 报表导出（CSV / Excel）。

按钮码：
- ``B_BI_CHART_EXPORT`` —— 图表导出（chart_csv / charts_excel）
- ``B_BI_DASHBOARD_EXPORT`` —— 仪表盘导出（dashboard_excel）

行级隔离：``tenant_id`` = 当前用户，越权返回 4140/4141。
响应均为文件流（text/csv 或 xlsx），带 Content-Disposition 附件名。
数据源一律用 BiChart.result_snapshot（≤ BI_EXPORT_MAX_ROWS 行），不重跑 SQL。
"""

from __future__ import annotations

import urllib.parse

from fastapi import APIRouter
from fastapi.responses import Response

from app.business.bi.models import BiChart, BiDashboard
from app.business.bi.services_export import (
    build_chart_csv,
    build_charts_excel,
    build_dashboard_excel,
)
from app.core.exceptions import BizError
from app.utils import (
    Code,
    DependAuth,
    SqidPath,
    decode_id,
    get_current_user_id,
    require_buttons,
)

router = APIRouter(prefix="/export", tags=["BI报表导出"])

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _attachment(filename: str) -> str:
    """构造 Content-Disposition（RFC 5987 编码中文名）。"""
    quoted = urllib.parse.quote(filename)
    return f"attachment; filename*=UTF-8''{quoted}"


async def _get_owned_chart(chart_id: int, user_id: int) -> BiChart:
    """查询当前用户拥有的图表，越权/不存在抛 4140。"""
    chart = await BiChart.get_or_none(id=chart_id, tenant_id=user_id, deleted_at__isnull=True)
    if not chart:
        raise BizError(Code.BI_EXPORT_CHART_NOT_FOUND, "图表不存在或无权导出")
    return chart


@router.get(
    "/charts/{chart_id}/csv",
    summary="导出图表 CSV",
    name="bi.export.chart_csv",
    dependencies=[DependAuth, require_buttons("B_BI_CHART_EXPORT")],
)
async def export_chart_csv_endpoint(chart_id: SqidPath):
    """单图表 CSV（基于结果快照）。"""
    user_id = get_current_user_id()
    chart = await _get_owned_chart(chart_id, user_id)
    if not chart.result_snapshot or not chart.result_snapshot.get("rows"):
        raise BizError(Code.BI_EXPORT_NO_SNAPSHOT, "图表无结果快照")
    raw = build_chart_csv(chart)
    return Response(
        content=raw,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": _attachment(f"{chart.name}.csv")},
    )


@router.post(
    "/charts/excel",
    summary="批量导出图表 Excel",
    name="bi.export.charts_excel",
    dependencies=[DependAuth, require_buttons("B_BI_CHART_EXPORT")],
)
async def export_charts_excel_endpoint(obj_in: dict):
    """批量图表 Excel：body ``{chartIds: [sqid, ...]}``，每图表一个 Sheet。"""
    user_id = get_current_user_id()
    raw_ids = obj_in.get("chartIds") or []
    ids = [decode_id(s) for s in raw_ids if isinstance(s, str)]
    if not ids:
        raise BizError(Code.BI_EXPORT_CHART_NOT_FOUND, "chartIds 不能为空")
    charts = []
    for cid in ids:
        charts.append(await _get_owned_chart(cid, user_id))
    raw = build_charts_excel(charts)
    return Response(
        content=raw,
        media_type=XLSX_MEDIA,
        headers={"Content-Disposition": _attachment(f"charts-{len(charts)}.xlsx")},
    )


@router.post(
    "/dashboards/{dashboard_id}/excel",
    summary="导出仪表盘 Excel",
    name="bi.export.dashboard_excel",
    dependencies=[DependAuth, require_buttons("B_BI_DASHBOARD_EXPORT")],
)
async def export_dashboard_excel_endpoint(dashboard_id: SqidPath):
    """仪表盘 Excel：概览 Sheet + 每图表一个 Sheet（只含布局引用的图表）。

    ``layout.items[].chartId`` 是 sqid 字符串（前端存储），需 decode 后查询；
    decode 失败的条目跳过（脏数据容错）。
    """
    user_id = get_current_user_id()
    dashboard = await BiDashboard.get_or_none(id=dashboard_id, tenant_id=user_id, deleted_at__isnull=True)
    if not dashboard:
        raise BizError(Code.BI_EXPORT_DASHBOARD_NOT_FOUND, "仪表盘不存在或无权导出")

    # 收集布局引用的图表（去重 + 归属校验）
    chart_ids = list({item.get("chartId") for item in (dashboard.layout or {}).get("items", [])})
    charts = []
    for cid in chart_ids:
        try:
            cid_int = decode_id(cid)
        except (ValueError, TypeError):
            continue
        chart = await BiChart.get_or_none(id=cid_int, tenant_id=user_id, deleted_at__isnull=True)
        if chart:
            charts.append(chart)

    raw = build_dashboard_excel(dashboard, charts)
    return Response(
        content=raw,
        media_type=XLSX_MEDIA,
        headers={"Content-Disposition": _attachment(f"{dashboard.name}.xlsx")},
    )
