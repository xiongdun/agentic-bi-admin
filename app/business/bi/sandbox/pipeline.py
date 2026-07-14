"""SQL 沙箱 — 4 道闸 pipeline。

按顺序执行：
1. AST 白名单（write 拒绝）
2. 列脱敏（按角色规则）
3. 租户行级注入
4. 限流 + 执行 + 配额

每步失败抛 ``BizError`` 系列的 ``QuartzExecutionDenied`` 或 ``QuotaExceeded``。
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import cast

from app.business.bi.models import Datasource, MaskType
from app.business.bi.sandbox.executor import QueryResult, SqlExecutionError, execute, resolve_dialect
from app.business.bi.sandbox.masking import apply_masking
from app.business.bi.sandbox.quota import Quota, RateLimiter, enforce_row_limit, enforce_timeout
from app.business.bi.sandbox.tenant import inject_tenant_filter
from app.business.bi.sandbox.whitelist import validate_tree
from app.core.exceptions import BizError
from app.utils import DialectName, safe_parse


class SqlExecutionDenied(BizError):
    """沙箱拒绝（白名单 / 租户 / 脱敏等） — 业务码 1001。"""

    def __init__(self, message: str, *, kind: str) -> None:
        super().__init__(code=1001, msg=message)
        self.data = {"kind": kind}
        self.kind = kind


@dataclass(slots=True)
class PipelineContext:
    """pipeline 输入。"""

    datasource: Datasource
    user_id: int
    tenant_id: int
    quota: Quota = field(default_factory=Quota)
    masking_rules: dict[str, MaskType] = field(default_factory=dict)
    inject_tenant: bool = True
    # 元数据同步：执行时是否自动写 AuditLog
    record_audit: bool = True
    ip: str | None = None
    user_agent: str | None = None


@dataclass(slots=True)
class PipelineResult:
    """pipeline 输出。"""

    final_sql: str
    query: QueryResult
    sql_hash: str
    masked_columns: list[str] = field(default_factory=list)


def _sql_hash(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()[:32]


def _check_allow_write(allow_write: bool) -> None:
    """仅占位：Phase 1 永远只读，由 whitelist 强制。"""
    if allow_write:
        # 预留钩子，Phase 2 接入授权
        return


async def run_pipeline(
    sql: str,
    *,
    ctx: PipelineContext,
    allow_write: bool = False,
) -> PipelineResult:
    """执行完整 pipeline。"""
    _check_allow_write(allow_write)
    dialect = resolve_dialect(ctx.datasource)

    # 0. 限流（每用户每分钟）
    limiter = RateLimiter()
    await limiter.check(user_id=ctx.user_id, per_minute=ctx.quota.rate_limit_per_minute)

    # 1. AST 白名单
    tree = safe_parse(sql, cast(DialectName, dialect))
    if tree is None:
        raise SqlExecutionDenied("SQL 解析失败，请检查语法。", kind="parse_failed")
    ok, reason = validate_tree(tree, dialect=dialect)
    if not ok:
        raise SqlExecutionDenied(f"沙箱拒绝：{reason or 'unknown'}", kind="whitelist")

    # 2. 列脱敏
    masked_columns: list[str] = []
    if ctx.masking_rules:
        sql, err = apply_masking(sql, dialect=dialect, masking_rules=ctx.masking_rules)
        if err:
            raise SqlExecutionDenied(f"列脱敏失败：{err}", kind="masking")
        masked_columns = sorted(ctx.masking_rules.keys())

    # 3. 租户行级注入
    if ctx.inject_tenant:
        sql, err = inject_tenant_filter(sql, tenant_id=ctx.tenant_id, dialect=dialect)
        if err:
            raise SqlExecutionDenied(f"租户过滤注入失败：{err}", kind="tenant")

    # 4. 执行 + 配额
    start = time.perf_counter()
    try:
        result = await execute(ctx.datasource, sql)
    except SqlExecutionError as exc:
        await _write_audit_log(ctx, sql=sql, status="failed", error=str(exc), sql_hash=_sql_hash(sql))
        raise SqlExecutionDenied(f"SQL 执行失败：{exc}", kind="execution") from exc
    await enforce_row_limit(result.row_count, ctx.quota)
    await enforce_timeout(start, ctx.quota)

    if ctx.record_audit:
        await _write_audit_log(
            ctx,
            sql=sql,
            status="success",
            error=None,
            sql_hash=_sql_hash(sql),
            row_count=result.row_count,
            cost_ms=result.cost_ms,
        )

    return PipelineResult(
        final_sql=sql,
        query=result,
        sql_hash=_sql_hash(sql),
        masked_columns=masked_columns,
    )


async def _write_audit_log(
    ctx: PipelineContext,
    *,
    sql: str,
    status: str,
    error: str | None,
    sql_hash: str,
    row_count: int | None = None,
    cost_ms: int | None = None,
) -> None:
    """落审计日志（失败不抛 — 不能让审计写入把业务请求拖垮）。"""
    try:
        from app.business.bi.models import AuditLog  # 局部 import 避免循环

        await AuditLog.create(
            user_id=ctx.user_id,
            tenant_id=ctx.tenant_id,
            action="query",
            datasource_id=ctx.datasource.id,
            datasource=ctx.datasource,
            sql_hash=sql_hash,
            row_count=row_count,
            cost_ms=cost_ms,
            ip=ctx.ip,
            user_agent=ctx.user_agent,
            detail={"status": status, "error": error, "sql_preview": sql[:2000]},
        )
    except Exception:  # noqa: BLE001
        from app.core.log import log

        log.warning("bi.pipeline: audit log write failed", exc_info=True)


__all__ = [
    "PipelineContext",
    "PipelineResult",
    "SqlExecutionDenied",
    "run_pipeline",
]
