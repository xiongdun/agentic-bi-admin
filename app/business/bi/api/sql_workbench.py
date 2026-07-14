"""AgenticBI SQL 工作台 API — 执行 / EXPLAIN / 历史。

路由挂在业务模块下，路径前缀 ``/sql``（与 ``/datasources`` 平行）。
所有写接口通过 ``require_buttons`` 做权限校验。
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.business.bi.models import ExecutionStatus
from app.business.bi.sandbox.pipeline import SqlExecutionDenied
from app.business.bi.schemas.chat import (
    SqlExecuteRequest,
    SqlExecuteResponse,
    SqlExplainRequest,
)
from app.business.bi.services import execution as exec_service
from app.core.base_schema import Success, SuccessExtra
from app.core.ctx import CTX_ROLE_CODES, CTX_USER_ID
from app.core.dependency import require_buttons
from app.core.exceptions import BizError
from app.core.sqids import decode_id, encode_id

router = APIRouter(prefix="/sql")


@router.post(
    "/execute",
    name="bi.sql.execute",
    summary="SQL 工作台执行（沙箱）",
    dependencies=[require_buttons("B_BI_SQL_RUN")],
)
async def execute_sql(obj_in: SqlExecuteRequest, request: Request):
    """专业用户在 SQL 工作台直接执行一条 SQL（默认只读）。"""
    user_id = _current_user_id_or_fail()
    ds_id = _decode_ds_id(obj_in.datasource_id)
    try:
        record = await exec_service.run_user_sql(
            user_id=user_id,
            role_code=_first_role_code(),
            datasource_id=ds_id,
            sql=obj_in.sql,
            allow_write=obj_in.allow_write,
            ip=_client_ip(request),
            user_agent=_client_ua(request),
        )
    except SqlExecutionDenied as exc:
        # BizError 子类会经全局 handler 翻译成 Fail；这里再强调一下 status_code
        raise exc
    except ValueError as exc:
        raise BizError(msg=str(exc), code=400) from None
    return Success(
        data=SqlExecuteResponse(
            columns=record.columns,
            rows=record.rows,
            row_count=record.row_count,
            cost_ms=record.cost_ms,
            final_sql=record.final_sql,
            masked_columns=record.masked_columns,
            sql_hash=record.sql_hash,
        ).model_dump()
    )


@router.post(
    "/explain",
    name="bi.sql.explain",
    summary="EXPLAIN 查询计划",
    dependencies=[require_buttons("B_BI_SQL_EXPLAIN")],
)
async def explain_sql(obj_in: SqlExplainRequest):
    """对 SQL 工作台里的 SQL 做 EXPLAIN，返回数据库原 plan。"""
    ds_id = _decode_ds_id(obj_in.datasource_id)
    try:
        record = await exec_service.explain_user_sql(
            datasource_id=ds_id,
            sql=obj_in.sql,
        )
    except ValueError as exc:
        raise BizError(msg=str(exc), code=400) from None
    return Success(
        msg="explain 成功",
        data={
            "columns": record.columns,
            "rows": record.rows,
            "rawSql": record.raw_sql,
            "costMs": record.cost_ms,
        },
    )


@router.post(
    "/history",
    name="bi.sql.history",
    summary="查询执行历史",
    dependencies=[require_buttons("B_BI_SQL_HISTORY")],
)
async def list_execution_history(request: Request):
    """工作台执行历史（按当前用户过滤；超级管理员可指定 user_id）。"""
    body = await _read_json(request)
    user_id = body.get("user_id") or _current_user_id_or_fail()
    ds_sqid = body.get("datasource_id")
    datasource_id = decode_id(ds_sqid) if ds_sqid else None
    status = body.get("status")
    current = int(body.get("current", 1))
    size = int(body.get("size", 20))

    qs = exec_service.list_executions(
        user_id=user_id,
        datasource_id=datasource_id,
        status=status,
    )
    total = await qs.count()
    records = await qs.offset((current - 1) * size).limit(size)
    items = [
        {
            "id": encode_id(r.id),
            "datasourceId": encode_id(r.datasource_id),
            "sql": r.sql,
            "status": r.status.value,
            "rowCount": r.row_count,
            "costMs": r.cost_ms,
            "error": r.error,
            "createdAt": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]
    return SuccessExtra(
        data={"records": items},
        total=total,
        current=current,
        size=size,
    )


# ---- helpers ----


def _current_user_id_or_fail() -> int:
    user_id = CTX_USER_ID.get()
    if user_id is None:
        raise BizError(msg="无法识别当前用户", code=401)
    return user_id


def _decode_ds_id(sqid: str) -> int:
    """前端 sqid → int 主键。失败返回 0 触发后续 404。"""
    try:
        return decode_id(sqid)
    except ValueError:
        raise BizError(msg=f"无效的 datasource_id: {sqid}", code=400) from None


def _first_role_code() -> str | None:
    roles = CTX_ROLE_CODES.get()
    return roles[0] if roles else None


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _client_ua(request: Request) -> str | None:
    return request.headers.get("user-agent")


async def _read_json(request: Request) -> dict:
    """读 body（避免 Pydantic 校验把 missing field 当 422）。"""
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    return body or {}


__all__ = ["router", "ExecutionStatus"]
