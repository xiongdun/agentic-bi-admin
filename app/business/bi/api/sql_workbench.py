"""BI SQL 工作台路由 — 直连 SQL 执行 + 辅助工具。

按钮码：
- ``B_BI_SQL_RUN`` —— 执行 SQL（也覆盖 explain / preview 等需要执行权限的接口）

接口列表：
- ``POST /sql/run`` —— 执行 SQL（白名单校验 + 自动 LIMIT + 配额）
- ``POST /sql/explain`` —— 解析 SQL 返回 AST 摘要（不执行）
- ``POST /sql/format`` —— 格式化 SQL
- ``POST /sql/history/search`` —— 查询当前用户的 SQL 执行历史
- ``GET /sql/preview/{datasource_id}/{table_name}`` —— 预览表前 100 行
- ``GET /sql/generate-select/{datasource_id}/{table_name}`` —— 生成 SELECT 语句

项目历史教训：
- SQID 参数在 request schema 中定义为 str 类型，API 层解码（``SqlRunSchema.datasource_id``）
- 响应统一用 ``Success`` / ``SuccessExtra``
"""

from __future__ import annotations

from fastapi import APIRouter

from app.business.bi.sandbox.dialect import format_sql, get_dialect_name
from app.business.bi.schemas import (
    BiAuditLogSearch,
    SqlExplainRequest,
    SqlFormatRequest,
    SqlRunSchema,
)
from app.business.bi.services import generate_select, list_sql_history, preview_table, run_sql
from app.core.redis import AioRedis
from app.utils import (
    DependAuth,
    SqidPath,
    Success,
    SuccessExtra,
    get_current_user_id,
    require_buttons,
)

router = APIRouter()


@router.post(
    "/sql/run",
    summary="执行 SQL",
    name="bi.sql.run",
    dependencies=[DependAuth, require_buttons("B_BI_SQL_RUN")],
)
async def run_sql_endpoint(obj_in: SqlRunSchema, redis: AioRedis):
    """执行 SQL（白名单校验 + 自动 LIMIT + 配额限制）。"""
    user = _get_user_or_raise()
    result = await run_sql(user, obj_in, redis=redis)
    return Success(data=result)


@router.post(
    "/sql/explain",
    summary="解析 SQL（不执行）",
    name="bi.sql.explain",
    dependencies=[DependAuth, require_buttons("B_BI_SQL_RUN")],
)
async def explain_sql_endpoint(obj_in: SqlExplainRequest):
    """解析 SQL 返回 AST 摘要（不实际执行）。

    用于前端编辑器展示 SQL 结构 / 检测潜在问题。
    """
    import sqlglot

    dialect = get_dialect_name(obj_in.dialect) if obj_in.dialect else None
    try:
        expressions = sqlglot.parse(obj_in.sql, dialect=dialect)
    except Exception as e:
        return Success(data={"sql": obj_in.sql, "error": str(e), "statements": []})

    statements = []
    for expr in expressions:
        if expr is None:
            continue
        statements.append({
            "type": expr.key,
            "sql": expr.sql(dialect=dialect),
        })
    return Success(data={"sql": obj_in.sql, "statements": statements})


@router.post(
    "/sql/format",
    summary="格式化 SQL",
    name="bi.sql.format",
    dependencies=[DependAuth],
)
async def format_sql_endpoint(obj_in: SqlFormatRequest):
    """格式化 SQL（基于 sqlglot，不执行）。"""
    formatted = format_sql(obj_in.sql)
    return Success(data={"sql": formatted})


@router.post(
    "/sql/history/search",
    summary="查看当前用户的 SQL 执行历史",
    name="bi.sql.history",
    dependencies=[DependAuth, require_buttons("B_BI_SQL_RUN")],
)
async def list_sql_history_endpoint(obj_in: BiAuditLogSearch):
    """从审计日志查当前用户的 SQL 执行历史。"""
    user_id = get_current_user_id()
    total, records = await list_sql_history(user_id, obj_in)
    return SuccessExtra(data={"records": records}, total=total, current=obj_in.current, size=obj_in.size)


@router.get(
    "/sql/preview/{datasource_id}/{table_name}",
    summary="预览表前 100 行",
    name="bi.sql.preview",
    dependencies=[DependAuth, require_buttons("B_BI_SQL_RUN")],
)
async def preview_table_endpoint(datasource_id: SqidPath, table_name: str, redis: AioRedis):
    """预览表前 100 行数据。

    路径参数：
    - ``datasource_id`` —— 数据源 ID（sqid，自动解码）
    - ``table_name`` —— 表名
    """
    result = await preview_table(datasource_id, table_name, redis=redis)
    return Success(data=result)


@router.get(
    "/sql/generate-select/{datasource_id}/{table_name}",
    summary="生成 SELECT 语句",
    name="bi.sql.generate_select",
    dependencies=[DependAuth],
)
async def generate_select_endpoint(datasource_id: SqidPath, table_name: str):
    """根据 BiColumn 元数据生成 SELECT 语句。

    路径参数：
    - ``datasource_id`` —— 数据源 ID（sqid，自动解码）
    - ``table_name`` —— 表名
    """
    sql = await generate_select(datasource_id, table_name)
    return Success(data={"sql": sql})


def _get_user_or_raise():
    """获取当前用户（已通过 DependAuth 校验）。"""
    from app.utils import get_current_user

    user = get_current_user()
    if user is None:
        from app.utils import BizError, Code

        raise BizError(code=Code.INVALID_TOKEN, msg="未登录或登录已过期")
    return user
