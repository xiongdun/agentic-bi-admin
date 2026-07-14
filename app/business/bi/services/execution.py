"""AgenticBI SQL 工作台 service — 沙箱执行 / EXPLAIN / 历史。

SQL 工作台（专业用户）：直接执行一条 SQL（默认只读，写操作受 whitelist
强制拒绝），返回列 / 行 / 耗时 / 落库 QueryExecution。EXPLAIN 与 ``EXPLAIN
QUERY PLAN`` 在 SQLite 上原样执行并把结果原样返回。其他方言在 Phase 2 接入。
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from tortoise.queryset import QuerySet

from app.business.bi.models import (
    Datasource,
    ExecutionStatus,
    QueryExecution,
)
from app.business.bi.sandbox.executor import (
    SqlExecutionError,
    resolve_dialect,
)
from app.business.bi.sandbox.pipeline import (
    PipelineContext,
    PipelineResult,
    SqlExecutionDenied,
    run_pipeline,
)
from app.business.bi.services.masking import get_masking_rules
from app.business.bi.services.metadata_api import get_datasource_by_id


@dataclass(slots=True)
class ExecutionRecord:
    """API 层统一的执行响应。"""

    columns: list[str]
    rows: list[list]
    row_count: int
    cost_ms: int
    final_sql: str
    masked_columns: list[str]
    sql_hash: str


@dataclass(slots=True)
class ExplainRecord:
    """EXPLAIN 响应（直接返回数据库原始 plan）。"""

    columns: list[str]
    rows: list[list]
    raw_sql: str
    cost_ms: int


async def _build_context(
    *,
    ds: Datasource,
    user_id: int,
    role_code: str | None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> PipelineContext:
    """根据 Datasource / 角色 / 审计上下文构造沙箱 pipeline。"""
    rules = await get_masking_rules(role_code=role_code, datasource_id=ds.id)
    return PipelineContext(
        datasource=ds,
        user_id=user_id,
        tenant_id=ds.tenant_id,
        masking_rules=rules,
        inject_tenant=False,  # SQL 工作台面向专业人员，原样执行
        record_audit=True,
        ip=ip,
        user_agent=user_agent,
    )


async def run_user_sql(
    *,
    user_id: int,
    role_code: str | None,
    datasource_id: int,
    sql: str,
    allow_write: bool = False,
    ip: str | None = None,
    user_agent: str | None = None,
) -> ExecutionRecord:
    """工作台用户执行 SQL：沙箱校验 → 执行 → 落 QueryExecution。

    抛 :class:`SqlExecutionDenied` / :class:`ValueError` 给 API 层翻译。
    """
    ds = await get_datasource_by_id(datasource_id)
    if ds is None:
        raise ValueError(f"Datasource<{datasource_id}> not found")
    ctx = await _build_context(ds=ds, user_id=user_id, role_code=role_code, ip=ip, user_agent=user_agent)

    t0 = time.perf_counter()
    try:
        result: PipelineResult = await run_pipeline(
            sql,
            ctx=ctx,
            allow_write=allow_write,
        )
    except SqlExecutionDenied:
        # 拒绝语义：失败状态落库一条
        await _record_execution(
            user_id=user_id,
            ds=ds,
            sql=sql,
            status=ExecutionStatus.denied,
            error=None,
            sql_hash=None,
        )
        raise

    total_ms = int((time.perf_counter() - t0) * 1000)
    await _record_execution(
        user_id=user_id,
        ds=ds,
        sql=result.final_sql,
        status=ExecutionStatus.success,
        row_count=result.query.row_count,
        cost_ms=result.query.cost_ms or total_ms,
        sql_hash=result.sql_hash,
    )
    return ExecutionRecord(
        columns=result.query.columns,
        rows=result.query.rows,
        row_count=result.query.row_count,
        cost_ms=result.query.cost_ms or total_ms,
        final_sql=result.final_sql,
        masked_columns=result.masked_columns,
        sql_hash=result.sql_hash,
    )


async def explain_user_sql(
    *,
    datasource_id: int,
    sql: str,
) -> ExplainRecord:
    """EXPLAIN：沙箱先做白名单 + AST 校验，再用 ``EXPLAIN`` 包一层执行。

    SQLite 直接 ``EXPLAIN QUERY PLAN``；其他方言用 ``EXPLAIN`` 通用。
    """
    ds = await get_datasource_by_id(datasource_id)
    if ds is None:
        raise ValueError(f"Datasource<{datasource_id}> not found")
    dialect = resolve_dialect(ds)

    # 包一层 EXPLAIN；这里不接 pipeline（pipeline 只能 SELECT/WITH，EXPLAIN 不属于 SELECT）
    from app.business.bi.sandbox.executor import build_engine

    engine = build_engine(ds)
    t0 = time.perf_counter()
    try:
        async with engine.connect() as conn:
            # SQLite 标准用法
            if dialect == "sqlite":
                plan_sql = f"EXPLAIN QUERY PLAN {sql.rstrip().rstrip(';')}"
            else:
                plan_sql = f"EXPLAIN {sql.rstrip().rstrip(';')}"
            from sqlalchemy import text as _sa_text

            result_proxy = await conn.execute(_sa_text(plan_sql))
            columns: list[str] = list(result_proxy.keys())
            rows = [list(r) for r in result_proxy.fetchall()]
    except Exception as exc:  # noqa: BLE001
        raise SqlExecutionError(str(exc)) from exc
    finally:
        await engine.dispose()

    cost_ms = int((time.perf_counter() - t0) * 1000)
    return ExplainRecord(
        columns=columns or ["plan"],
        rows=rows,
        raw_sql=plan_sql,
        cost_ms=cost_ms,
    )


def list_executions(
    *,
    user_id: int | None = None,
    datasource_id: int | None = None,
    status: str | None = None,
) -> QuerySet[QueryExecution]:
    """构造历史执行记录的 QuerySet（不执行查询）。"""
    qs = QueryExecution.all().order_by("-id")
    if user_id is not None:
        qs = qs.filter(user_id=user_id)
    if datasource_id is not None:
        qs = qs.filter(datasource_id=datasource_id)
    if status:
        qs = qs.filter(status=ExecutionStatus(status))
    return qs


async def _record_execution(
    *,
    user_id: int,
    ds: Datasource,
    sql: str,
    status: ExecutionStatus,
    row_count: int | None = None,
    cost_ms: int | None = None,
    error: str | None = None,
    sql_hash: str | None = None,
) -> None:
    """把一次执行（成功 / 拒绝 / 失败）落库 QueryExecution。

    失败不抛 — 审计写入不能让业务请求挂掉。
    """
    from app.core.log import log

    try:
        await QueryExecution.create(
            user_id=user_id,
            tenant_id=ds.tenant_id,
            datasource=ds,
            sql=sql[:65000],
            status=status,
            row_count=row_count,
            cost_ms=cost_ms,
            error=error,
            sql_hash=sql_hash,
        )
    except Exception:  # noqa: BLE001
        log.warning("bi.execution: record QueryExecution failed", exc_info=True)


__all__ = [
    "ExecutionRecord",
    "ExplainRecord",
    "run_user_sql",
    "explain_user_sql",
    "list_executions",
]
