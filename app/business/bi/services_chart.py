"""BiChart 业务服务 — 保存、刷新、分享。

与主 services.py 分离，避免单文件过大。复用 sandbox 模块保证 SQL 安全。
"""

from __future__ import annotations

from datetime import datetime

from app.utils import BizError, Code, decode_id, encode_id, log, radar_log

from .config import BIZ_SETTINGS
from .models import BiChart, BiDatasource
from .sandbox.executor import execute_sql, test_connection
from .sandbox.tenant import inject_tenant_filter
from .sandbox.whitelist import validate_sql


async def create_chart(schema, tenant_id: int, user_id: int) -> BiChart:
    """保存图表。

    1. 校验数据源存在且属于当前租户
    2. 校验 SQL 走白名单
    3. 截断结果快照到 BI_CHART_SNAPSHOT_MAX_ROWS 行
    4. 写入 BiChart
    """
    datasource_id = decode_id(schema.datasource_id)
    datasource = await BiDatasource.get_or_none(id=datasource_id, tenant_id=tenant_id, deleted_at__isnull=True)
    if not datasource:
        raise BizError(Code.NOT_FOUND, "数据源不存在")

    # 校验 SQL（防止保存恶意 SQL）
    validate_sql(schema.sql_text, datasource.db_type)

    # 截断结果快照
    snapshot = _truncate_snapshot(schema.result_snapshot, BIZ_SETTINGS.BI_CHART_SNAPSHOT_MAX_ROWS)

    chart = await BiChart.create(
        name=schema.name,
        description=schema.description,
        datasource_id=datasource_id,
        chart_type=schema.chart_type,
        x_col=schema.x_col,
        y_col=schema.y_col,
        sql_text=schema.sql_text,
        result_snapshot=snapshot,
        tags=schema.tags,
        snapshot_at=schema.snapshot_at,
        tenant_id=tenant_id,
        created_by=str(user_id),
        updated_by=str(user_id),
    )
    radar_log("bi.chart.create", data={"chart_id": chart.id, "name": chart.name})
    log.info("bi.chart.create chart_id={} name={}", chart.id, chart.name)
    return chart


async def refresh_chart(chart_id: int, tenant_id: int, user_id: int) -> BiChart:
    """重跑 SQL 刷新结果快照。

    数据源不可用时抛 BizError，前端降级显示快照。
    """
    chart = await BiChart.get_or_none(id=chart_id, tenant_id=tenant_id, deleted_at__isnull=True)
    if not chart:
        raise BizError(Code.BI_CHART_NOT_FOUND, "图表不存在")

    datasource = await chart.datasource
    ok, err, _ = await test_connection(datasource)
    if not ok:
        raise BizError(Code.BI_DATASOURCE_UNAVAILABLE, f"数据源不可用：{err}")

    # 完整校验链：白名单（含自动 LIMIT）→ 行级注入 → 执行
    validation = validate_sql(chart.sql_text, datasource.db_type)
    sql = inject_tenant_filter(validation.sql, tenant_id=tenant_id, dialect=datasource.db_type)
    result = await execute_sql(sql=sql, datasource=datasource, user_id=user_id)

    # 覆盖快照
    snapshot = _truncate_snapshot(
        {
            "columns": result.columns,
            "rows": result.rows,
            "rowCount": result.row_count,
            "elapsedMs": result.elapsed_ms,
        },
        BIZ_SETTINGS.BI_CHART_SNAPSHOT_MAX_ROWS,
    )
    chart.result_snapshot = snapshot
    chart.snapshot_at = datetime.now()
    await chart.save(update_fields=["result_snapshot", "snapshot_at", "updated_at"])
    radar_log("bi.chart.refresh", data={"chart_id": chart.id})
    log.info("bi.chart.refresh chart_id={}", chart.id)
    return chart


async def enable_share(chart_id: int, tenant_id: int) -> str:
    """开启分享，返回 share_token（sqid 编码）。"""
    chart = await BiChart.get_or_none(id=chart_id, tenant_id=tenant_id, deleted_at__isnull=True)
    if not chart:
        raise BizError(Code.BI_CHART_NOT_FOUND, "图表不存在")

    if not chart.share_token:
        chart.share_token = encode_id(chart.id)
    chart.is_public = True
    await chart.save(update_fields=["share_token", "is_public", "updated_at"])
    radar_log("bi.chart.share.enable", data={"chart_id": chart.id})
    return chart.share_token


async def disable_share(chart_id: int, tenant_id: int) -> None:
    """关闭分享，清除 share_token。"""
    chart = await BiChart.get_or_none(id=chart_id, tenant_id=tenant_id, deleted_at__isnull=True)
    if not chart:
        raise BizError(Code.BI_CHART_NOT_FOUND, "图表不存在")

    chart.is_public = False
    chart.share_token = None
    await chart.save(update_fields=["share_token", "is_public", "updated_at"])
    radar_log("bi.chart.share.disable", data={"chart_id": chart.id})


async def get_shared_chart_by_token(token: str) -> BiChart:
    """免登录查看分享图表（不返回 sql_text，由 schema 层过滤）。"""
    chart = await BiChart.get_or_none(share_token=token, is_public=True, deleted_at__isnull=True)
    if not chart:
        raise BizError(Code.NOT_FOUND, "分享链接无效或已失效")
    return chart


async def get_all_tags(tenant_id: int) -> list[str]:
    """获取当前租户下所有图表的标签（用于前端自动补全）。"""
    charts = await BiChart.filter(tenant_id=tenant_id, deleted_at__isnull=True).values_list("tags", flat=True)
    tag_set: set[str] = set()
    for tags_str in charts:
        if tags_str and isinstance(tags_str, str):
            for tag in tags_str.split(","):
                tag = tag.strip()
                if tag:
                    tag_set.add(tag)
    return sorted(tag_set)


def _truncate_snapshot(snapshot: dict, max_rows: int) -> dict:
    """截断结果快照到 max_rows 行，标记 isTruncated。"""
    rows = snapshot.get("rows", [])
    if len(rows) > max_rows:
        return {
            **snapshot,
            "rows": rows[:max_rows],
            "rowCount": max_rows,
            "isTruncated": True,
        }
    return snapshot
