"""BiDashboard 业务服务 — 仪表盘 CRUD + 全量刷新 + 预览。

关键设计：
- ``layout`` 存 ``{"items": [{chartId, x, y, w, h}]}``，``chartId`` 为 BiChart 的 SQID 编码字符串
- ``refresh_dashboard`` 并发刷新所有图表（信号量限流），失败不降级，deleted 单独标记
- ``preview_dashboard`` 不重跑 SQL，直接返回 BiChart 已有快照（编辑模式用）
- 行级隔离：所有查询带 ``tenant_id=user_id``
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from app.business.bi.config import BIZ_SETTINGS
from app.business.bi.models import BiChart, BiDashboard
from app.business.bi.services_chart import _rerun_chart_sql
from app.utils import BizError, Code, decode_id, encode_id, log, radar_log

# ==================== layout 校验 ====================


def validate_layout_structure(layout: dict) -> list[dict]:
    """纯结构校验：长度、字段范围、x+w 边界。不查 DB。

    Raises:
        BizError: 结构非法时抛 ``Code.REQUEST_VALIDATION``
    Returns:
        items 列表（空 layout 返回 []）
    """
    items = layout.get("items", []) if isinstance(layout, dict) else []
    if not isinstance(items, list):
        raise BizError(Code.REQUEST_VALIDATION, "layout.items 必须是数组")
    if len(items) > BIZ_SETTINGS.BI_DASHBOARD_MAX_ITEMS:
        raise BizError(
            Code.REQUEST_VALIDATION,
            f"仪表盘图表数超过上限：{len(items)} > {BIZ_SETTINGS.BI_DASHBOARD_MAX_ITEMS}",
        )

    for item in items:
        if not isinstance(item, dict):
            raise BizError(Code.REQUEST_VALIDATION, "layout.items[] 元素必须是对象")
        try:
            x, y, w, h = int(item["x"]), int(item["y"]), int(item["w"]), int(item["h"])
        except (KeyError, TypeError, ValueError) as e:
            raise BizError(Code.REQUEST_VALIDATION, f"layout.items[] 字段非法：{e}") from e
        chart_id = item.get("chartId")
        if not chart_id or not isinstance(chart_id, str):
            raise BizError(Code.REQUEST_VALIDATION, "layout.items[].chartId 必须是字符串")
        if not (1 <= w <= 12):
            raise BizError(Code.REQUEST_VALIDATION, f"宽度非法：w={w}，需 1-12")
        if not (1 <= h <= 6):
            raise BizError(Code.REQUEST_VALIDATION, f"高度非法：h={h}，需 1-6")
        if x < 0 or y < 0:
            raise BizError(Code.REQUEST_VALIDATION, f"位置非法：x={x}, y={y}")
        if x + w > 12:
            raise BizError(Code.REQUEST_VALIDATION, f"超出 12 列：x={x} + w={w} = {x + w}")
    return items


async def validate_layout(layout: dict, tenant_id: int) -> None:
    """完整校验：结构 + chartId 归属当前租户且未软删。"""
    items = validate_layout_structure(layout)
    chart_ids: list[int] = []
    for item in items:
        try:
            chart_ids.append(decode_id(item["chartId"]))
        except (ValueError, TypeError) as e:
            raise BizError(Code.REQUEST_VALIDATION, f"chartId 无法解码：{item['chartId']}") from e

    if not chart_ids:
        return

    valid_count = await BiChart.filter(id__in=chart_ids, tenant_id=tenant_id, deleted_at__isnull=True).count()
    if valid_count != len(set(chart_ids)):
        raise BizError(
            Code.REQUEST_VALIDATION,
            "存在无效图表ID：不属于当前租户或已删除",
        )


# ==================== CRUD ====================


async def create_dashboard(schema, tenant_id: int, user_id: int) -> BiDashboard:
    """创建仪表盘。"""
    layout_dict = _schema_layout_to_dict(schema.layout)
    await validate_layout(layout_dict, tenant_id=tenant_id)

    dashboard = await BiDashboard.create(
        name=schema.name,
        description=schema.description,
        layout=layout_dict,
        tenant_id=tenant_id,
        created_by=str(user_id),
        updated_by=str(user_id),
    )
    radar_log("bi.dashboard.create", data={"dashboard_id": dashboard.id})
    log.info("bi.dashboard.create id={} user_id={}", dashboard.id, user_id)
    return dashboard


async def get_dashboard(dashboard_id: int, tenant_id: int) -> BiDashboard:
    """获取仪表盘详情（不存在抛 BizError）。"""
    dashboard = await BiDashboard.get_or_none(id=dashboard_id, tenant_id=tenant_id, deleted_at__isnull=True)
    if not dashboard:
        raise BizError(Code.BI_DASHBOARD_NOT_FOUND, "仪表盘不存在")
    return dashboard


async def update_dashboard(dashboard_id: int, schema, tenant_id: int, user_id: int) -> BiDashboard:
    """更新仪表盘（仅更新 schema 中显式传入的字段）。"""
    dashboard = await get_dashboard(dashboard_id, tenant_id)
    data = schema.model_dump(exclude_unset=True, exclude_none=True)

    if "name" in data:
        dashboard.name = data["name"]
    if "description" in data:
        dashboard.description = data["description"]
    if "layout" in data:
        layout_dict = _schema_layout_to_dict(schema.layout)
        await validate_layout(layout_dict, tenant_id=tenant_id)
        dashboard.layout = layout_dict

    dashboard.updated_by = str(user_id)
    await dashboard.save()
    radar_log("bi.dashboard.update", data={"dashboard_id": dashboard.id})
    log.info("bi.dashboard.update id={}", dashboard.id)
    return dashboard


async def delete_dashboard(dashboard_id: int, tenant_id: int) -> None:
    """软删仪表盘。"""
    dashboard = await get_dashboard(dashboard_id, tenant_id)
    await dashboard.delete()  # SoftDeleteManager 会设置 deleted_at
    radar_log("bi.dashboard.delete", data={"dashboard_id": dashboard_id})
    log.info("bi.dashboard.delete id={}", dashboard_id)


# ==================== 刷新与预览 ====================


def _chart_meta(chart: BiChart) -> dict:
    """提取图表元信息（名称/类型/轴字段）。"""
    return {
        "name": chart.name,
        "chartType": chart.chart_type,
        "xCol": chart.x_col,
        "yCol": chart.y_col,
    }


async def refresh_dashboard(dashboard_id: int, tenant_id: int) -> dict:
    """全量刷新仪表盘所有图表数据。

    - 并发上限 ``BI_DASHBOARD_REFRESH_CONCURRENCY``
    - 单图表超时 ``BI_DASHBOARD_REFRESH_TIMEOUT``
    - 失败不降级，返回 ``status=failed`` + ``errorMessage``
    - 引用的 BiChart 已软删时返回 ``status=deleted`` + ``chartMeta=None``
    """
    dashboard = await get_dashboard(dashboard_id, tenant_id)
    items: list[dict] = dashboard.layout.get("items", []) if dashboard.layout else []

    chart_ids = [decode_id(i["chartId"]) for i in items]
    charts = await BiChart.filter(id__in=chart_ids, tenant_id=tenant_id, deleted_at__isnull=True)
    chart_map = {c.id: c for c in charts}

    semaphore = asyncio.Semaphore(BIZ_SETTINGS.BI_DASHBOARD_REFRESH_CONCURRENCY)

    async def refresh_one(item: dict) -> dict:
        async with semaphore:
            chart_id = decode_id(item["chartId"])
            chart = chart_map.get(chart_id)
            if not chart:
                return {"chartId": item["chartId"], "status": "deleted", "chartMeta": None}
            try:
                snapshot = await asyncio.wait_for(
                    _rerun_chart_sql(chart),
                    timeout=BIZ_SETTINGS.BI_DASHBOARD_REFRESH_TIMEOUT,
                )
                return {
                    "chartId": item["chartId"],
                    "status": "success",
                    "resultSnapshot": snapshot,
                    "chartMeta": _chart_meta(chart),
                    "snapshotAt": datetime.now().isoformat(),
                }
            except Exception as e:
                return {
                    "chartId": item["chartId"],
                    "status": "failed",
                    "errorMessage": str(e),
                    "chartMeta": _chart_meta(chart),
                }

    start = datetime.now()
    results = await asyncio.gather(*[refresh_one(i) for i in items])
    total_elapsed_ms = int((datetime.now() - start).total_seconds() * 1000)
    radar_log(
        "bi.dashboard.refresh",
        data={"dashboard_id": dashboard_id, "item_count": len(items)},
    )
    log.info(
        "bi.dashboard.refresh id={} items={} elapsed_ms={}",
        dashboard_id,
        len(items),
        total_elapsed_ms,
    )
    return {"items": results, "totalElapsedMs": total_elapsed_ms}


async def preview_dashboard(dashboard_id: int, tenant_id: int) -> dict:
    """预览仪表盘（不刷新，用 BiChart 已有快照，编辑模式用）。"""
    dashboard = await get_dashboard(dashboard_id, tenant_id)
    items: list[dict] = dashboard.layout.get("items", []) if dashboard.layout else []

    chart_ids = [decode_id(i["chartId"]) for i in items]
    charts = await BiChart.filter(id__in=chart_ids, tenant_id=tenant_id, deleted_at__isnull=True)
    chart_map = {c.id: c for c in charts}

    preview_items: list[dict] = []
    for item in items:
        chart = chart_map.get(decode_id(item["chartId"]))
        if not chart:
            preview_items.append({"chartId": item["chartId"], "status": "deleted", "chartMeta": None})
        else:
            preview_items.append({
                "chartId": item["chartId"],
                "chartMeta": _chart_meta(chart),
                "resultSnapshot": chart.result_snapshot,
            })

    return {
        "id": encode_id(dashboard.id),
        "name": dashboard.name,
        "description": dashboard.description,
        "layout": dashboard.layout,
        "items": preview_items,
    }


# ==================== 工具函数 ====================


def _schema_layout_to_dict(layout: Any) -> dict:
    """把 schema 的 layout（DashboardLayoutSchema 或 dict）转为可存入 JSONField 的 dict。"""
    if hasattr(layout, "model_dump"):
        return layout.model_dump(mode="json")
    if isinstance(layout, dict):
        return layout
    return {"items": []}
