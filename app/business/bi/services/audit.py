"""BI 审计 service — 统一写入入口 + 分页查询 + 统计 + CSV 导出 + 清理。

设计要点：
- ``record_audit()`` 是所有 BI 域操作的审计写入入口；失败只 warn 不抛
- 有 ``sql_text`` 时同时写 ``BiAuditSql`` 并关联
- ``user_id`` / ``tenant_id`` 缺省时从 CTX 取（单租户演示环境 tenant 跟随 user）
- 查询支持按 user / datasource / action / status / 时间范围 / keyword 过滤
- 统计聚合用单次 GROUP BY，避免 N+1
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

from tortoise.queryset import QuerySet

from app.business.bi.models import AuditLog, BiAuditSql, Datasource
from app.core.ctx import CTX_USER_ID
from app.core.log import log
from app.core.sqids import encode_id

# ---------- helpers ----------


def _now_naive() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


def _audit_to_dict(a: AuditLog, *, datasource_name: str | None = None) -> dict:
    detail = a.detail or {}
    # 兼容历史数据：status 可能不在 detail 里
    status = detail.get("status") if isinstance(detail, dict) else None
    return {
        "id": encode_id(a.id),
        "userId": a.user_id,
        "tenantId": a.tenant_id,
        "action": a.action,
        "datasourceId": encode_id(a.datasource_id) if a.datasource_id else None,
        "datasourceName": datasource_name,
        "sqlHash": a.sql_hash,
        "rowCount": a.row_count,
        "costMs": a.cost_ms,
        "ip": a.ip,
        "userAgent": a.user_agent,
        "detail": detail,
        "status": status,
        "createdAt": a.created_at.isoformat() if a.created_at else None,
    }


# ---------- write ----------


async def record_audit(
    *,
    action: str,
    user_id: int | None = None,
    tenant_id: int | None = None,
    datasource_id: int | None = None,
    datasource: Datasource | None = None,
    sql_text: str | None = None,
    sql_hash: str | None = None,
    row_count: int | None = None,
    cost_ms: int | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    detail: dict | None = None,
) -> None:
    """统一的审计写入入口。失败只 warn 不抛。

    - 有 ``sql_text`` 时同时写 ``BiAuditSql`` 并关联
    - ``user_id`` 缺省时从 CTX 取；``tenant_id`` 缺省时跟随 ``user_id``（单租户演示）
    """
    try:
        if user_id is None:
            user_id = CTX_USER_ID.get()
        if user_id is None:
            user_id = 0  # 系统操作
        if tenant_id is None:
            tenant_id = user_id  # 单租户演示环境

        a = await AuditLog.create(
            user_id=user_id,
            tenant_id=tenant_id,
            action=action,
            datasource_id=datasource.id if datasource else datasource_id,
            datasource=datasource,
            sql_hash=sql_hash,
            row_count=row_count,
            cost_ms=cost_ms,
            ip=ip,
            user_agent=user_agent,
            detail=detail,
        )
        if sql_text:
            await BiAuditSql.create(
                audit_log_id=a.id,
                sql_text=sql_text,
                sql_hash=sql_hash or "",
            )
    except Exception:  # noqa: BLE001
        log.warning("bi.audit: record_audit failed", exc_info=True)


# ---------- read ----------


def _apply_filters(
    qs: QuerySet[AuditLog],
    *,
    user_id: int | None = None,
    datasource_id: int | None = None,
    action: str | None = None,
    status: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> QuerySet[AuditLog]:
    if user_id is not None:
        qs = qs.filter(user_id=user_id)
    if datasource_id is not None:
        qs = qs.filter(datasource_id=datasource_id)
    if action:
        qs = qs.filter(action=action)
    if status:
        # status 存在 detail JSON 里，用 JSON 过滤（SQLite 不原生支持，用icontains 兜底）
        qs = qs.filter(detail__icontains=status)
    if start_time:
        qs = qs.filter(created_at__gte=start_time)
    if end_time:
        qs = qs.filter(created_at__lte=end_time)
    return qs


async def search_audit_logs(
    *,
    current: int = 1,
    size: int = 20,
    user_id: int | None = None,
    datasource_id: int | None = None,
    action: str | None = None,
    status: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    keyword: str | None = None,
) -> tuple[list[dict], int]:
    """分页查询审计日志。"""
    qs = _apply_filters(
        AuditLog.all(),
        user_id=user_id,
        datasource_id=datasource_id,
        action=action,
        status=status,
        start_time=start_time,
        end_time=end_time,
    )
    if keyword:
        # sql_hash / ip OR 模糊匹配：基于已过滤 qs 取两个子查询 ID 集合
        hash_ids = qs.filter(sql_hash__icontains=keyword).values_list("id", flat=True)
        ip_ids = qs.filter(ip__icontains=keyword).values_list("id", flat=True)
        merged = set(await hash_ids) | set(await ip_ids)
        qs = AuditLog.filter(id__in=list(merged) if merged else [])
    total = await qs.count()
    items: list[AuditLog] = await qs.order_by("-created_at").offset((current - 1) * size).limit(size)
    # 批量取 datasource name（避免 N+1）
    ds_ids = {a.datasource_id for a in items if a.datasource_id is not None}
    ds_names: dict[int, str] = {}
    if ds_ids:
        for ds in await Datasource.filter(id__in=list(ds_ids)):
            assert ds.id is not None  # noqa: S101 - 主键非空
            ds_names[ds.id] = ds.name
    out: list[dict] = []
    for a in items:
        ds_name = ds_names.get(a.datasource_id) if a.datasource_id is not None else None
        out.append(_audit_to_dict(a, datasource_name=ds_name))
    return out, total


async def get_audit_detail(audit_id: int) -> dict | None:
    """返回审计记录 + 关联的原始 SQL（如有）。"""
    a = await AuditLog.filter(id=audit_id).first()
    if a is None:
        return None
    sql_text = None
    sql_obj = await BiAuditSql.filter(audit_log_id=audit_id).first()
    if sql_obj:
        sql_text = sql_obj.sql_text
    ds_name = None
    if a.datasource_id:
        ds = await Datasource.filter(id=a.datasource_id).first()
        if ds:
            ds_name = ds.name
    result = _audit_to_dict(a, datasource_name=ds_name)
    result["sqlText"] = sql_text
    return result


# ---------- stats ----------


async def get_audit_stats(
    *,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> dict:
    """KPI：total / success / failed / total_export_rows / active_users / avg_cost_ms"""
    qs = _apply_filters(AuditLog.all(), start_time=start_time, end_time=end_time)
    total = await qs.count()
    # success / failed：detail 里有 status 字段
    success = await qs.filter(detail__icontains="success").count()
    failed = await qs.filter(detail__icontains="failed").count()
    # export 行数：action=export 的 rowCount 求和
    export_qs = qs.filter(action="export")
    export_items = await export_qs.exclude(row_count=None).values("row_count")
    total_export_rows = sum(r["row_count"] for r in export_items if r["row_count"])
    active_users = await qs.distinct().values_list("user_id", flat=True)
    cost_items = await qs.filter(cost_ms__isnull=False).values_list("cost_ms", flat=True)
    cost_list: list[int] = [int(c[0]) if isinstance(c, tuple) else int(c) for c in cost_items if c is not None]
    avg_cost = sum(cost_list) / len(cost_list) if cost_list else 0
    return {
        "total": total,
        "success": success,
        "failed": failed,
        "totalExportRows": total_export_rows,
        "activeUsers": len(set(active_users)),
        "avgCostMs": round(avg_cost, 2) if avg_cost else 0,
    }


# ---------- trend ----------


async def get_daily_trend(
    *,
    days: int = 30,
    action: str | None = None,
) -> list[dict]:
    """按天趋势：返回 [{date, count, success, failed}, ...]"""
    end = _now_naive()
    start = end - timedelta(days=days)
    qs = AuditLog.filter(created_at__gte=start, created_at__lte=end)
    if action:
        qs = qs.filter(action=action)
    # SQLite / PostgreSQL / MySQL 通用：Python 端聚合（量级 30 天 × N ops 不大）
    items = await qs.order_by("created_at").values("created_at", "action", "detail")
    buckets: dict[str, dict[str, int]] = {}
    for it in items:
        created = it["created_at"]
        if created is None:
            continue
        day_key = created.strftime("%Y-%m-%d") if hasattr(created, "strftime") else str(created)[:10]
        b = buckets.setdefault(day_key, {"count": 0, "success": 0, "failed": 0})
        b["count"] += 1
        detail = it.get("detail") or {}
        st = detail.get("status") if isinstance(detail, dict) else None
        if st == "success":
            b["success"] += 1
        elif st == "failed":
            b["failed"] += 1
    # 补齐空天
    out: list[dict] = []
    cur = start.date()
    end_d = end.date()
    while cur <= end_d:
        key = cur.isoformat()
        b = buckets.get(key, {"count": 0, "success": 0, "failed": 0})
        out.append({"date": key, "count": b["count"], "success": b["success"], "failed": b["failed"]})
        cur += timedelta(days=1)
    return out


async def get_hourly_heatmap(
    *,
    days: int = 30,
) -> list[dict]:
    """时段热力图：返回 [{dayOfWeek, hour, count}, ...] 共 168 格"""
    end = _now_naive()
    start = end - timedelta(days=days)
    qs = AuditLog.filter(created_at__gte=start, created_at__lte=end)
    items = await qs.values("created_at")
    grid: dict[tuple[int, int], int] = {}
    for it in items:
        created = it["created_at"]
        if created is None:
            continue
        # weekday(): Monday=0 .. Sunday=6 → 转为 Sunday=0 .. Saturday=6
        dow = (created.weekday() + 1) % 7
        hour = created.hour
        grid[(dow, hour)] = grid.get((dow, hour), 0) + 1
    out: list[dict] = []
    for dow in range(7):
        for hour in range(24):
            out.append({"dayOfWeek": dow, "hour": hour, "count": grid.get((dow, hour), 0)})
    return out


# ---------- export ----------


async def export_audit_csv(
    *,
    user_id: int | None = None,
    datasource_id: int | None = None,
    action: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> str:
    """生成 CSV 字符串。列：时间/用户/Action/数据源/SQL摘要/行数/耗时/状态/IP"""
    qs = _apply_filters(
        AuditLog.all(),
        user_id=user_id,
        datasource_id=datasource_id,
        action=action,
        start_time=start_time,
        end_time=end_time,
    )
    items = (
        await qs
        .order_by("-created_at")
        .limit(10000)
        .values(
            "created_at",
            "user_id",
            "action",
            "datasource_id",
            "sql_hash",
            "row_count",
            "cost_ms",
            "ip",
            "detail",
        )
    )
    # 批量取 datasource name
    ds_ids = {i["datasource_id"] for i in items if i.get("datasource_id")}
    ds_names: dict[int, str] = {}
    if ds_ids:
        for ds in await Datasource.filter(id__in=list(ds_ids)):
            ds_names[ds.id] = ds.name

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "时间",
        "用户ID",
        "操作类型",
        "数据源",
        "SQL哈希",
        "行数",
        "耗时(ms)",
        "状态",
        "IP",
    ])
    for it in items:
        detail = it["detail"] or {}
        status = detail.get("status") if isinstance(detail, dict) else ""
        ds_name = ds_names.get(it["datasource_id"], "")
        created = it["created_at"]
        writer.writerow([
            created.isoformat() if created else "",
            it["user_id"],
            it["action"],
            ds_name,
            it["sql_hash"] or "",
            it["row_count"] or "",
            it["cost_ms"] or "",
            status or "",
            it["ip"] or "",
        ])
    return buf.getvalue()


# ---------- cleanup ----------


async def cleanup_old_audit_logs(retention_days: int = 90) -> int:
    """删除超过保留期的审计日志（级联 bi_audit_sql）。返回删除条数。"""
    cutoff = _now_naive() - timedelta(days=retention_days)
    # 先删 bi_audit_sql（通过子查询）
    old_log_ids = await AuditLog.filter(created_at__lt=cutoff).values_list("id", flat=True)
    if not old_log_ids:
        return 0
    await BiAuditSql.filter(audit_log_id__in=list(old_log_ids)).delete()
    count = await AuditLog.filter(created_at__lt=cutoff).delete()
    log.info("bi.audit: cleaned up %s old audit logs (retention=%s days)", count, retention_days)
    return count
