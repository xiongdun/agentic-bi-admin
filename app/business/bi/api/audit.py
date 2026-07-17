"""AgenticBI 审计 API — 分页查询 / 详情 / 统计 / 趋势 / 热力图 / CSV 导出。

所有接口通过 ``require_buttons`` 做权限校验。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.business.bi.services import audit as audit_service
from app.core.base_schema import Success
from app.core.dependency import require_buttons
from app.core.sqids import decode_id

router = APIRouter(prefix="/audit")


@router.get("/logs", name="bi.audit.search", summary="分页查询审计", dependencies=[require_buttons("B_BI_AUDIT_VIEW")])
async def list_logs(
    current: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    user_id: int | None = Query(None),
    datasource_id: int | None = Query(None),
    action: str | None = Query(None),
    status: str | None = Query(None),
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    keyword: str | None = Query(None),
):
    items, total = await audit_service.search_audit_logs(
        current=current,
        size=size,
        user_id=user_id,
        datasource_id=datasource_id,
        action=action,
        status=status,
        start_time=start_time,
        end_time=end_time,
        keyword=keyword,
    )
    return Success(
        data={"records": items},
        total=total,
        current=current,
        size=size,
    )


@router.get("/logs/{item_id}", name="bi.audit.detail", summary="审计详情", dependencies=[require_buttons("B_BI_AUDIT_VIEW")])
async def get_log(item_id: str):
    audit_pk = decode_id(item_id)
    detail = await audit_service.get_audit_detail(audit_pk)
    if detail is None:
        return Success(data=None)
    return Success(data=detail)


@router.get("/stats", name="bi.audit.stats", summary="审计 KPI 统计", dependencies=[require_buttons("B_BI_AUDIT_VIEW")])
async def get_stats(start_time: datetime | None = Query(None), end_time: datetime | None = Query(None)):
    stats = await audit_service.get_audit_stats(start_time=start_time, end_time=end_time)
    return Success(data=stats)


@router.get("/trend", name="bi.audit.trend", summary="按天趋势", dependencies=[require_buttons("B_BI_AUDIT_VIEW")])
async def get_trend(days: int = Query(30, ge=1, le=365), action: str | None = Query(None)):
    items = await audit_service.get_daily_trend(days=days, action=action)
    return Success(data=items)


@router.get("/heatmap", name="bi.audit.heatmap", summary="时段热力图", dependencies=[require_buttons("B_BI_AUDIT_VIEW")])
async def get_heatmap(days: int = Query(30, ge=1, le=365)):
    items = await audit_service.get_hourly_heatmap(days=days)
    return Success(data=items)


@router.get("/export", name="bi.audit.export", summary="CSV 导出", dependencies=[require_buttons("B_BI_AUDIT_EXPORT")])
async def export_csv(
    user_id: int | None = Query(None),
    datasource_id: int | None = Query(None),
    action: str | None = Query(None),
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
):
    csv_str = await audit_service.export_audit_csv(
        user_id=user_id,
        datasource_id=datasource_id,
        action=action,
        start_time=start_time,
        end_time=end_time,
    )
    filename = f"bi_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([csv_str]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
