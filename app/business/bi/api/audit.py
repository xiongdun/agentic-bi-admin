"""BI 审计日志路由 — 搜索 / 统计 / 导出 / 详情。

按钮码：
- ``B_BI_AUDIT_VIEW`` —— 查看（搜索 / 统计 / 详情）
- ``B_BI_AUDIT_EXPORT`` —— 导出 CSV

审计日志由各业务操作（数据源测试 / 同步 / SQL 执行 / 对话发送 / 指标测试 /
Provider 测试）写入，本路由仅提供查询能力，不开放写接口。

支持按日志类型 / 操作人 / 时间范围 / 资源类型筛选，返回统计卡片
（总数 / 成功 / 失败 / 按事件类型 / 按操作 / 按用户分组）。
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.business.bi.controllers import bi_audit_log_controller
from app.business.bi.schemas import (
    BiAuditLogSearch,
    BiAuditStatisticsRequest,
)
from app.business.bi.services import (
    export_audit_logs,
    get_audit_stats,
    search_audit_logs,
)
from app.utils import (
    DependAuth,
    SqidPath,
    Success,
    SuccessExtra,
    require_buttons,
)

router = APIRouter()


@router.post(
    "/audit/search",
    summary="搜索审计日志",
    name="bi.audit.search",
    dependencies=[DependAuth, require_buttons("B_BI_AUDIT_VIEW")],
)
async def search_audit_logs_endpoint(obj_in: BiAuditLogSearch):
    """审计日志分页搜索（支持按日志类型 / 操作人 / 时间范围筛选）。"""
    total, records = await search_audit_logs(obj_in)
    return SuccessExtra(data={"records": records}, total=total, current=obj_in.current, size=obj_in.size)


@router.get(
    "/audit/{audit_id}",
    summary="查看审计日志详情",
    name="bi.audit.get",
    dependencies=[DependAuth, require_buttons("B_BI_AUDIT_VIEW")],
)
async def get_audit_log_endpoint(audit_id: SqidPath):
    """查看审计日志详情（含 TraceID / IP / 资源信息 / JSON 详情 / 错误信息）。"""
    log = await bi_audit_log_controller.get(id=audit_id)
    return Success(data=await log.to_dict())


@router.post(
    "/audit/stats",
    summary="审计日志统计",
    name="bi.audit.stats",
    dependencies=[DependAuth, require_buttons("B_BI_AUDIT_VIEW")],
)
async def get_audit_stats_endpoint(obj_in: BiAuditStatisticsRequest):
    """返回统计卡片数据（总数 / 成功 / 失败 / 按事件类型 / 按操作 / 按用户分组）。

    可选传入时间范围筛选；不传则统计全量。
    """
    # BiAuditStatisticsRequest 仅含 start_date / end_date，转成 BiAuditLogSearch 复用 build_audit_search_query
    if obj_in.start_date or obj_in.end_date:
        search_in = BiAuditLogSearch(
            created_at_start=obj_in.start_date,
            created_at_end=obj_in.end_date,
        )  # type: ignore[callIssue]
        stats = await get_audit_stats(search_in)
    else:
        stats = await get_audit_stats()
    return Success(data=stats)


@router.post(
    "/audit/export",
    summary="导出审计日志 CSV",
    name="bi.audit.export",
    dependencies=[DependAuth, require_buttons("B_BI_AUDIT_EXPORT")],
    response_class=PlainTextResponse,
)
async def export_audit_logs_endpoint(obj_in: BiAuditLogSearch):
    """导出审计日志为 CSV（带 UTF-8 BOM，方便 Excel 直接打开）。

    最多导出 10000 条，避免内存爆炸。
    """
    csv_content = await export_audit_logs(obj_in)
    return PlainTextResponse(content=csv_content, media_type="text/csv; charset=utf-8")
