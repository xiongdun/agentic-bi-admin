"""BI 模块 service — 跨模型编排、缓存、外部 IO。

涵盖：
- 数据源 test / sync
- 对话 send（SSE 流式）
- SQL run / preview / generate_select
- 指标 test
- LLM Provider test
- 审计日志 search / stats / export
- 数据源 / Provider 的密码 / API Key 加解密钩子
- BiChatSession / BiChatMessage 持久化辅助
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import AsyncGenerator

from tortoise.expressions import Q

from app.business.bi.agent.runner import run_chat_turn
from app.business.bi.agent.state import AgentState
from app.business.bi.controllers import (
    bi_audit_log_controller,
    bi_chat_message_controller,
    bi_chat_session_controller,
    bi_column_controller,
    bi_datasource_controller,
    bi_llm_provider_controller,
    bi_metric_controller,
    bi_table_controller,
)
from app.business.bi.llm.router import BiLLMRouter
from app.business.bi.models import (
    BiAuditLog,
    BiChatMessage,
    BiChatSession,
    BiColumn,
    BiDatasource,
    BiLLMProvider,
    BiMetric,
)
from app.business.bi.sandbox.dialect import get_dialect_name
from app.business.bi.sandbox.executor import (
    ExecutionResult,
    dispose_engine,
    execute_sql,
    test_connection,
)
from app.business.bi.sandbox.tenant import inject_tenant_filter, should_inject_tenant
from app.business.bi.sandbox.whitelist import validate_sql
from app.business.bi.schemas import (
    BiAuditLogSearch,
    BiAuditStatistics,
    BiColumnSearch,
    BiTableSearch,
    ChatSendSchema,
    SqlRunSchema,
)
from app.business.bi.security.crypto import encrypt, mask
from app.utils import (
    BizError,
    decode_id,
    encode_id,
    get_current_user,
    get_current_user_id,
    radar_log,
)

# BI 业务错误码段：4000-4499
_BI_DS_ERR = 4001  # 数据源连接失败
_BI_DS_NOT_FOUND = 4002  # 数据源不存在
_BI_METRIC_ERR = 4101  # 指标执行失败
_BI_SQL_ERR = 4104  # SQL 执行失败
_BI_SESSION_ERR = 4150  # 会话操作失败（标题校验等）
_BI_LLM_ERR = 4200  # LLM Provider 不可用
_BI_AUDIT_ERR = 4300  # 审计日志导出失败


# ============================================================
# 数据源：加解密钩子（由 CRUDRouter override 调用）
# ============================================================


def _encrypt_datasource_password(obj_in: dict) -> dict:
    """加密数据源密码（创建/更新时调用）。

    若 obj_in 含 ``password`` 明文，加密后写回；否则不动。
    """
    if "password" in obj_in and obj_in["password"]:
        obj_in["password"] = encrypt(str(obj_in["password"]))
    return obj_in


async def datasource_record(ds: BiDatasource) -> dict:
    """序列化数据源记录，密码字段返回脱敏占位符。"""
    record = await ds.to_dict()
    record["password"] = mask("")
    return record


async def create_datasource(obj_in: dict) -> BiDatasource:
    """创建数据源 — 加密密码。"""
    data = dict(obj_in)
    _encrypt_datasource_password(data)
    ds = await bi_datasource_controller.create(obj_in=data)
    radar_log("创建数据源", data={"datasourceId": ds.id, "name": ds.name})
    return ds


async def update_datasource(ds_id: int, obj_in: dict) -> BiDatasource:
    """更新数据源 — 按需加密密码（不传则保留原密文）。"""
    data = dict(obj_in)
    if "password" in data:
        if data["password"]:
            data["password"] = encrypt(str(data["password"]))
        else:
            # 空字符串 / None：不更新密码
            data.pop("password", None)
    ds = await bi_datasource_controller.update(id=ds_id, obj_in=data)
    # 数据源更新后清理引擎缓存（连接参数可能已变）
    await dispose_engine(ds_id)
    radar_log("更新数据源", data={"datasourceId": ds_id})
    return ds


# ============================================================
# LLM Provider：加解密钩子
# ============================================================


def _encrypt_provider_api_key(obj_in: dict) -> dict:
    """加密 LLM Provider API Key（创建/更新时调用）。"""
    if "api_key" in obj_in and obj_in["api_key"]:
        obj_in["api_key"] = encrypt(str(obj_in["api_key"]))
    return obj_in


async def llm_provider_record(provider: BiLLMProvider) -> dict:
    """序列化 Provider 记录，API Key 返回脱敏占位符。"""
    record = await provider.to_dict()
    record["apiKey"] = mask("")
    return record


async def create_llm_provider(obj_in: dict) -> BiLLMProvider:
    """创建 Provider — 加密 API Key。"""
    data = dict(obj_in)
    _encrypt_provider_api_key(data)
    provider = await bi_llm_provider_controller.create(obj_in=data)
    radar_log("创建 LLM Provider", data={"providerId": provider.id, "name": provider.name})
    return provider


async def update_llm_provider(provider_id: int, obj_in: dict) -> BiLLMProvider:
    """更新 Provider — 按需加密 API Key。"""
    data = dict(obj_in)
    if "api_key" in data:
        if data["api_key"]:
            data["api_key"] = encrypt(str(data["api_key"]))
        else:
            data.pop("api_key", None)
    provider = await bi_llm_provider_controller.update(id=provider_id, obj_in=data)
    radar_log("更新 LLM Provider", data={"providerId": provider_id})
    return provider


# ============================================================
# 数据源测试 / 同步
# ============================================================


async def test_datasource(datasource_id: int) -> dict:
    """测试数据源连接。

    Returns:
        ``BiDatasourceTestResult`` 兼容 dict
    """
    ds = await bi_datasource_controller.get_or_none(id=datasource_id)
    if ds is None:
        raise BizError(_BI_DS_NOT_FOUND, f"数据源不存在: {datasource_id}")

    success, message, elapsed_ms = await test_connection(ds)

    # 写审计日志
    await BiAuditLog.create(
        event_type="SYSTEM_OPERATION",
        action="测试数据源连接",
        user_id=get_current_user_id() or 0,
        resource_type="datasource",
        resource_id=str(datasource_id),
        status="success" if success else "failed",
        error_message=None if success else message,
        execution_time_ms=elapsed_ms,
    )

    radar_log(
        "测试数据源连接",
        data={"datasourceId": datasource_id, "success": success, "elapsedMs": elapsed_ms},
    )

    return {
        "success": success,
        "message": message,
        "elapsed_ms": elapsed_ms,
    }


async def sync_datasource_metadata(datasource_id: int) -> dict:
    """同步数据源元数据。

    Returns:
        ``BiDatasourceSyncResult`` 兼容 dict
    """
    from app.business.bi.metadata.sync import sync_datasource

    ds = await bi_datasource_controller.get_or_none(id=datasource_id)
    if ds is None:
        raise BizError(_BI_DS_NOT_FOUND, f"数据源不存在: {datasource_id}")

    # 数据源更新后清理引擎缓存（保证读到最新配置）
    await dispose_engine(datasource_id)

    result = await sync_datasource(ds)

    # 写审计日志
    await BiAuditLog.create(
        event_type="SYSTEM_OPERATION",
        action="同步数据源元数据",
        user_id=get_current_user_id() or 0,
        resource_type="datasource",
        resource_id=str(datasource_id),
        status="success",
        execution_time_ms=result.elapsed_ms,
        detail={
            "tables_synced": result.tables_synced,
            "columns_synced": result.columns_synced,
            "indexes_synced": result.indexes_synced,
            "foreign_keys_synced": result.foreign_keys_synced,
            "errors": result.errors,
        },
    )

    radar_log(
        "同步数据源元数据",
        data={
            "datasourceId": datasource_id,
            "tablesSynced": result.tables_synced,
            "columnsSynced": result.columns_synced,
            "elapsedMs": result.elapsed_ms,
        },
    )

    return {
        "datasource_id": encode_id(datasource_id),
        "tables_synced": result.tables_synced,
        "columns_synced": result.columns_synced,
        "indexes_synced": result.indexes_synced,
        "foreign_keys_synced": result.foreign_keys_synced,
        "elapsed_ms": result.elapsed_ms,
        "errors": result.errors,
    }


# ============================================================
# 对话：发送消息（SSE 流式）
# ============================================================


async def _resolve_datasource(datasource_id: str | None) -> BiDatasource | None:
    """解析对话上下文中的数据源。None → 默认（首个启用）。"""
    if datasource_id:
        ds_id = decode_id(datasource_id)
        return await bi_datasource_controller.get_or_none(id=ds_id)
    # 默认取首个启用数据源
    from app.utils import StatusType

    return await bi_datasource_controller.get_or_none(status_type=StatusType.enable)


async def _get_user_data_scope() -> tuple[str, int | None]:
    """获取当前用户的 data_scope 与 scope_id（行级权限）。

    返回 (data_scope, scope_id)；data_scope=="all" 时 scope_id 为 None。
    """
    from app.utils import get_current_data_scope

    try:
        data_scope = await get_current_data_scope(None)
    except Exception:
        data_scope = "all"

    user = get_current_user()
    scope_id = None
    if data_scope != "all" and user is not None:
        # 行级 scope_id 来自用户上下文；HR 用 dept_id，BI 用 tenant_id（语义一致）
        scope_id = getattr(user, "id", None)
    return data_scope, scope_id


async def send_chat_message(user, schema: ChatSendSchema) -> AsyncGenerator[dict, None]:
    """发送对话消息，返回 SSE 事件流。

    流程：
    1. 解析 / 创建 BiChatSession
    2. 持久化用户消息（role=user）
    3. 构建 AgentState，调用 run_chat_turn 流式产出事件
    4. 由 runner 负责持久化 assistant 消息（成功 / 失败均持久化）

    Args:
        user: 当前用户（DependAuth 注入）
        schema: ChatSendSchema

    Yields:
        SSE 事件 dict（type=step / final / error）
    """
    user_id = int(user.id)

    # 1. 解析会话
    if schema.session_id:
        session_id_int = decode_id(schema.session_id)
        session = await bi_chat_session_controller.get_or_none(id=session_id_int, user_id=user_id)
        if session is None:
            yield {
                "type": "error",
                "node": "session",
                "error": f"会话不存在或无权访问: {schema.session_id}",
            }
            return
    else:
        # 创建新会话
        title = schema.question[:50] + ("..." if len(schema.question) > 50 else "")
        session = await BiChatSession.create(
            title=title,
            user_id=user_id,
            tenant_id=0,
        )
        session_id_int = session.id

    # 2. 持久化用户消息
    user_msg = await BiChatMessage.create(
        session_id=session_id_int,
        role="user",
        content=schema.question,
        status="success",
    )

    # 更新会话最后消息时间
    await BiChatSession.filter(id=session_id_int).update(last_message_at=datetime.now())

    # 3. 解析数据源（None 用默认）
    datasource = await _resolve_datasource(schema.datasource_id)
    datasource_id_int = datasource.id if datasource else None

    # 4. 解析用户 data_scope
    data_scope, scope_id = await _get_user_data_scope()

    # 5. 构建 AgentState 并流式执行
    state: AgentState = {
        "question": schema.question,
        "session_id": session_id_int,
        "user_id": user_id,
        "user_msg_id": user_msg.id,
        "data_scope": data_scope,
        "scope_id": scope_id,
        "datasource_id": datasource_id_int,
        "validate_error": None,  # SQL 自纠错重试状态
        "retry_count": 0,
    }

    # 写审计日志（发送对话）
    await BiAuditLog.create(
        event_type="USER_BEHAVIOR",
        action="发送对话消息",
        user_id=user_id,
        resource_type="chat_session",
        resource_id=str(session_id_int),
        status="success",
        detail={"question": schema.question[:200], "datasource_id": datasource_id_int},
    )

    # 6. 流式产出事件（runner 负责持久化 assistant 消息）
    async for event in run_chat_turn(state):
        yield event


# ============================================================
# SQL 工作台
# ============================================================


async def run_sql(user, schema: SqlRunSchema, redis=None) -> dict:
    """执行 SQL（已通过白名单校验 + 自动 LIMIT + 行级注入）。

    Args:
        redis: Redis 客户端（用于熔断计数 + 软超时转异步）

    Returns:
        SqlRunResult 兼容 dict —— 成功时含 ``columns``/``rows``/``rowCount``/``elapsedMs``；
        软超时转异步时含 ``transferred=True`` 与 ``taskId``。
    """
    user_id = int(user.id)
    ds_id = decode_id(schema.datasource_id)
    ds = await bi_datasource_controller.get_or_none(id=ds_id)
    if ds is None:
        raise BizError(_BI_DS_NOT_FOUND, f"数据源不存在: {schema.datasource_id}")

    # 方言：用数据源 db_type 推导
    dialect = get_dialect_name(ds.db_type)

    # 白名单校验 + 自动 LIMIT
    validation = validate_sql(schema.sql, dialect=dialect)
    safe_sql = validation.sql

    # 行级 tenant 注入（与 NL2SQL 路径一致，spec 要求 SQL 工作台直连也走行级注入）
    data_scope, scope_id = await _get_user_data_scope()
    if should_inject_tenant(data_scope) and scope_id is not None:
        safe_sql = inject_tenant_filter(safe_sql, scope_id, dialect=dialect)

    # 软超时：超过 BI_SYNC_SOFT_TIMEOUT 则转异步任务（仅当 redis 可用 + 异步查询开启）
    from app.business.bi.config import BIZ_SETTINGS

    if redis is not None and BIZ_SETTINGS.BI_ASYNC_QUERY_ENABLED:
        import asyncio as _asyncio

        try:
            result: ExecutionResult = await _asyncio.wait_for(
                execute_sql(safe_sql, ds, user_id=user_id, redis=redis),
                timeout=BIZ_SETTINGS.BI_SYNC_SOFT_TIMEOUT,
            )
        except _asyncio.TimeoutError:
            # 转异步任务（submit 内部会重新走完整校验链 + 行级注入）
            from app.business.bi.schemas import BiAsyncRunSchema
            from app.business.bi.services_async_query import submit as _submit_async

            async_schema = BiAsyncRunSchema(
                sql=schema.sql,
                datasource_id=schema.datasource_id,
                name=f"软超时转异步-{datetime.now().strftime('%H%M%S')}",
            )
            task = await _submit_async(async_schema, user_id=user_id, redis=redis, source="auto_transfer")
            radar_log(
                "SQL 软超时转异步",
                data={"userId": user_id, "taskId": task.id, "datasourceId": ds_id},
            )
            return {
                "transferred": True,
                "taskId": encode_id(task.id),
                "message": "查询超时，已转为异步任务",
                "datasource_id": schema.datasource_id,
                "sql_text": schema.sql,
            }
    else:
        result = await execute_sql(safe_sql, ds, user_id=user_id, redis=redis)

    # 写审计日志（仅同步成功路径）
    await BiAuditLog.create(
        event_type="QUERY_OPERATION",
        action="执行 SQL",
        user_id=user_id,
        resource_type="datasource",
        resource_id=str(ds_id),
        status="success",
        execution_time_ms=result.elapsed_ms,
        detail={
            "sql": safe_sql,
            "row_count": result.row_count,
            "columns": result.columns,
        },
    )

    radar_log(
        "执行 SQL",
        data={
            "userId": user_id,
            "datasourceId": ds_id,
            "rowCount": result.row_count,
            "elapsedMs": result.elapsed_ms,
        },
    )

    return {
        "sql": safe_sql,
        "columns": result.columns,
        "rows": result.rows,
        "rowCount": result.row_count,
        "elapsedMs": result.elapsed_ms,
    }


async def preview_table(datasource_id: int, table_name: str, redis=None) -> dict:
    """预览表前 100 行。"""
    ds = await bi_datasource_controller.get_or_none(id=datasource_id)
    if ds is None:
        raise BizError(_BI_DS_NOT_FOUND, f"数据源不存在: {datasource_id}")

    # 用白名单包装，避免表名注入
    safe_table = table_name.replace("`", "").replace("'", "").replace('"', "")
    sql = f"SELECT * FROM {safe_table} LIMIT 100"

    # 直接走 execute_sql（preview 默认已含 LIMIT 100，跳过白名单二次添加）
    user_id = get_current_user_id() or 0
    result = await execute_sql(sql, ds, user_id=user_id, max_rows=100, redis=redis)

    return {
        "sql": sql,
        "columns": result.columns,
        "rows": result.rows,
        "rowCount": result.row_count,
        "elapsedMs": result.elapsed_ms,
    }


async def generate_select(datasource_id: int, table_name: str) -> str:
    """根据 BiColumn 元数据生成 SELECT 语句。

    若元数据不存在，回退到 ``SELECT *``。
    """
    safe_table = table_name.replace("`", "").replace("'", "").replace('"', "")

    # 查 BiTable + BiColumn 元数据
    bi_table = await bi_table_controller.get_or_none(datasource_id=datasource_id, name=table_name)
    if bi_table is None:
        return f"SELECT * FROM {safe_table} LIMIT 100;"

    columns = await BiColumn.filter(table_id=bi_table.id).order_by("id").values("name", "comment", "is_primary")
    if not columns:
        return f"SELECT * FROM {safe_table} LIMIT 100;"

    col_lines = []
    for col in columns:
        col_name = col["name"]
        comment = f"  -- {col['comment']}" if col.get("comment") else ""
        col_lines.append(f"    {col_name}{comment}")

    cols_sql = ",\n".join(col_lines)
    return f"SELECT\n{cols_sql}\nFROM {safe_table}\nLIMIT 100;"


# ============================================================
# 指标测试
# ============================================================


async def test_metric(metric_id: int) -> dict:
    """加载指标 SQL 模板 + 在绑定的数据源上执行。"""
    metric: BiMetric | None = await bi_metric_controller.get_or_none(id=metric_id)
    if metric is None:
        raise BizError(_BI_METRIC_ERR, f"指标不存在: {metric_id}")

    ds = await bi_datasource_controller.get_or_none(id=metric.datasource_id)
    if ds is None:
        raise BizError(_BI_DS_NOT_FOUND, f"指标绑定的数据源不存在: {metric.datasource_id}")

    sql = metric.sql_template
    dialect = get_dialect_name(ds.db_type)

    # 走白名单校验 + 自动 LIMIT
    try:
        validation = validate_sql(sql, dialect=dialect)
        safe_sql = validation.sql
    except BizError as e:
        # 指标 SQL 模板可能含 {xxx} 占位符未替换，校验失败时直接返回错误
        return {
            "success": False,
            "sql": sql,
            "rowCount": 0,
            "elapsedMs": 0,
            "error": str(e),
        }

    user_id = get_current_user_id() or 0

    # 写审计日志
    await BiAuditLog.create(
        event_type="QUERY_OPERATION",
        action="测试指标",
        user_id=user_id,
        resource_type="metric",
        resource_id=str(metric_id),
        status="success",
        detail={"sql": safe_sql},
    )

    try:
        result = await execute_sql(safe_sql, ds, user_id=user_id)
        return {
            "success": True,
            "sql": safe_sql,
            "rowCount": result.row_count,
            "elapsedMs": result.elapsed_ms,
            "error": None,
        }
    except BizError as e:
        return {
            "success": False,
            "sql": safe_sql,
            "rowCount": 0,
            "elapsedMs": 0,
            "error": str(e),
        }


# ============================================================
# LLM Provider 测试
# ============================================================


async def test_llm_provider(provider_id: int) -> dict:
    """测试 LLM Provider 连接（与正式路径共用 _resolve_provider）。"""
    try:
        provider = await BiLLMRouter.get_provider_by_id(provider_id)
    except BizError as e:
        # 写审计日志
        await BiAuditLog.create(
            event_type="SYSTEM_OPERATION",
            action="测试 LLM Provider",
            user_id=get_current_user_id() or 0,
            resource_type="llm_provider",
            resource_id=str(provider_id),
            status="failed",
            error_message=str(e),
        )
        raise

    success, message, elapsed_ms, token_usage = await provider.test_connection()
    model_name = provider.model_config.get("name") if hasattr(provider, "model_config") else None

    # 写审计日志
    await BiAuditLog.create(
        event_type="SYSTEM_OPERATION",
        action="测试 LLM Provider",
        user_id=get_current_user_id() or 0,
        resource_type="llm_provider",
        resource_id=str(provider_id),
        status="success" if success else "failed",
        error_message=None if success else message,
        execution_time_ms=elapsed_ms,
        detail={"model_name": model_name, "token_usage": token_usage},
    )

    return {
        "success": success,
        "message": message,
        "model_name": model_name,
        "elapsed_ms": elapsed_ms,
    }


# ============================================================
# 审计日志搜索 / 统计 / 导出
# ============================================================


def build_audit_search_query(search_in: BiAuditLogSearch) -> Q:
    """构建审计日志搜索 Q 对象。"""
    q = bi_audit_log_controller.build_search(
        search_in,
        contains_fields=["action"],
        icontains_fields=["username"],
        exact_fields=["event_type", "status", "resource_type"],
        range_fields=["created_at"],
    )
    # user_id 是 sqid 字符串，需解码后精确匹配
    if search_in.user_id:
        try:
            q &= Q(user_id=decode_id(search_in.user_id))
        except (ValueError, TypeError):
            pass
    return q


async def search_audit_logs(search_in: BiAuditLogSearch) -> tuple[int, list[dict]]:
    """审计日志分页搜索。"""
    q = build_audit_search_query(search_in)
    total, logs = await bi_audit_log_controller.list(
        page=search_in.current,
        page_size=search_in.size,
        search=q,
        order=["-id"],
    )
    records = [await log.to_dict() for log in logs]
    return total, records


async def get_audit_stats(search_in: BiAuditLogSearch | None = None) -> dict:
    """审计日志统计卡片数据。"""
    base_q = build_audit_search_query(search_in) if search_in else Q()

    total = await BiAuditLog.filter(base_q).count()
    success_count = await BiAuditLog.filter(base_q & Q(status="success")).count()
    failed_count = await BiAuditLog.filter(base_q & Q(status="failed")).count()

    # 按事件类型分组
    by_event_type: dict[str, int] = {}
    rows = await BiAuditLog.filter(base_q).group_by("event_type").values("event_type")
    for row in rows:
        et = row["event_type"]
        by_event_type[et] = await BiAuditLog.filter(base_q & Q(event_type=et)).count()

    # 按操作分组（top 10）
    by_action: dict[str, int] = {}
    action_rows = await BiAuditLog.filter(base_q).group_by("action").values("action")
    for row in action_rows[:10]:
        a = row["action"]
        by_action[a] = await BiAuditLog.filter(base_q & Q(action=a)).count()

    # 按用户分组（top 10）
    by_user: dict[str, int] = {}
    user_rows = await BiAuditLog.filter(base_q).group_by("username").values("username")
    for row in user_rows[:10]:
        u = row["username"] or "unknown"
        by_user[u] = await BiAuditLog.filter(base_q & Q(username=row["username"])).count()

    return {
        "total": total,
        "success_count": success_count,
        "failed_count": failed_count,
        "by_event_type": by_event_type,
        "by_action": by_action,
        "by_user": by_user,
    }


async def export_audit_logs(search_in: BiAuditLogSearch) -> str:
    """审计日志 CSV 导出（带 BOM 头，方便 Excel 直接打开）。

    Returns:
        CSV 字符串（含 UTF-8 BOM）
    """
    q = build_audit_search_query(search_in)
    # 最多导出 10000 条，避免内存爆炸
    logs = await BiAuditLog.filter(q).order_by("-id").limit(10000)

    output = io.StringIO()
    output.write("\ufeff")  # UTF-8 BOM
    writer = csv.writer(output)
    writer.writerow([
        "ID",
        "TraceID",
        "事件类型",
        "操作",
        "用户ID",
        "用户名",
        "IP",
        "资源类型",
        "资源ID",
        "状态",
        "错误信息",
        "耗时(ms)",
        "创建时间",
    ])

    for log in logs:
        writer.writerow([
            log.id,
            log.trace_id or "",
            log.event_type,
            log.action,
            log.user_id or "",
            log.username or "",
            log.ip_address or "",
            log.resource_type or "",
            log.resource_id or "",
            log.status,
            log.error_message or "",
            log.execution_time_ms,
            log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else "",
        ])

    # 写审计日志（导出动作本身）
    await BiAuditLog.create(
        event_type="PERMISSION_CHANGE",
        action="导出审计日志",
        user_id=get_current_user_id() or 0,
        resource_type="audit_log",
        status="success",
        detail={"count": len(logs)},
    )

    return output.getvalue()


# ============================================================
# 对话会话 / 消息持久化辅助
# ============================================================


async def list_user_sessions(user_id: int, search_in) -> tuple[int, list[dict]]:
    """列出当前用户的会话（按最后消息时间倒序）。"""
    q = bi_chat_session_controller.build_search(
        search_in,
        contains_fields=["title"],
    )
    q &= Q(user_id=user_id)
    total, sessions = await bi_chat_session_controller.list(
        page=search_in.current,
        page_size=search_in.size,
        search=q,
        order=["-last_message_at", "-id"],
    )
    records = [await s.to_dict() for s in sessions]
    return total, records


async def list_session_messages(session_id: int, search_in) -> tuple[int, list[dict]]:
    """列出指定会话的消息（按时间正序）。"""
    q = bi_chat_message_controller.build_search(
        search_in,
        exact_fields=["role", "status"],
    )
    # search_in.session_id 是 sqid 字符串；如果传入则解码
    if search_in.session_id:
        try:
            decoded = decode_id(search_in.session_id)
            q &= Q(session_id=decoded)
            target_session_id = decoded
        except (ValueError, TypeError):
            target_session_id = session_id
    else:
        target_session_id = session_id
    q &= Q(session_id=target_session_id)

    total, messages = await bi_chat_message_controller.list(
        page=search_in.current,
        page_size=search_in.size,
        search=q,
        order=["id"],
    )
    records = [await m.to_dict() for m in messages]
    return total, records


async def delete_chat_session(session_id: int, user_id: int) -> int:
    """删除会话（级联删除消息）。"""
    session = await bi_chat_session_controller.get_or_none(id=session_id, user_id=user_id)
    if session is None:
        raise BizError(_BI_DS_NOT_FOUND, f"会话不存在或无权访问: {session_id}")

    # 删除会话消息
    await BiChatMessage.filter(session_id=session_id).delete()
    # 删除会话
    await bi_chat_session_controller.remove(id=session_id)

    radar_log("删除对话会话", data={"session_id": session_id, "user_id": user_id})
    return session_id


async def update_chat_session(session_id: int, user_id: int, obj_in) -> int:
    """更新会话标题。仅会话创建人可修改。"""
    session = await bi_chat_session_controller.get_or_none(id=session_id, user_id=user_id)
    if session is None:
        raise BizError(_BI_DS_NOT_FOUND, f"会话不存在或无权访问: {session_id}")

    title = (getattr(obj_in, "title", None) or "").strip()
    if not title:
        raise BizError(_BI_SESSION_ERR, "会话标题不能为空")
    if len(title) > 200:
        raise BizError(_BI_SESSION_ERR, "会话标题不能超过 200 字符")

    await bi_chat_session_controller.update(id=session_id, obj_in={"title": title})
    radar_log("更新对话会话标题", data={"session_id": session_id, "user_id": user_id})
    return session_id


# ============================================================
# SQL 历史（从 audit_log 查）
# ============================================================


async def list_sql_history(user_id: int, search_in) -> tuple[int, list[dict]]:
    """从审计日志查当前用户的 SQL 执行历史。"""
    q = Q(user_id=user_id, event_type="QUERY_OPERATION", action="执行 SQL")

    total, logs = await bi_audit_log_controller.list(
        page=search_in.current,
        page_size=search_in.size,
        search=q,
        order=["-id"],
    )
    records = []
    for log in logs:
        detail = log.detail or {}
        records.append({
            "id": encode_id(log.id),
            "sql": detail.get("sql", ""),
            "row_count": detail.get("row_count", 0),
            "datasource_id": log.resource_id,
            "status": log.status,
            "execution_time_ms": log.execution_time_ms,
            "created_at": log.created_at,
        })
    return total, records


# ============================================================
# 元数据查询（tables / columns / 表详情）
# ============================================================


async def list_tables(search_in: BiTableSearch) -> tuple[int, list[dict]]:
    """列出表元数据（支持按 datasource_id / name 过滤）。

    ``datasource_id`` 在 schema 中为 sqid 字符串，需解码后精确匹配。
    """
    q = bi_table_controller.build_search(
        search_in,
        contains_fields=["name"],
    )
    if search_in.datasource_id:
        try:
            q &= Q(datasource_id=decode_id(search_in.datasource_id))
        except (ValueError, TypeError):
            pass
    total, tables = await bi_table_controller.list(
        page=search_in.current,
        page_size=search_in.size,
        search=q,
        order=["-id"],
    )
    records = [await t.to_dict() for t in tables]
    return total, records


async def list_columns(search_in: BiColumnSearch) -> tuple[int, list[dict]]:
    """列出列元数据（支持按 table_id / name 过滤）。

    ``table_id`` 在 schema 中为 sqid 字符串，需解码后精确匹配。
    """
    q = bi_column_controller.build_search(
        search_in,
        contains_fields=["name"],
    )
    if search_in.table_id:
        try:
            q &= Q(table_id=decode_id(search_in.table_id))
        except (ValueError, TypeError):
            pass
    total, columns = await bi_column_controller.list(
        page=search_in.current,
        page_size=search_in.size,
        search=q,
        order=["id"],
    )
    records = [await c.to_dict() for c in columns]
    return total, records


async def get_table_detail(table_id: int) -> dict:
    """获取表详情（含列 / 索引 / 外键聚合）。"""
    from app.business.bi.models import BiColumn, BiForeignKey, BiIndex

    table = await bi_table_controller.get(id=table_id)
    record = await table.to_dict()

    columns = await BiColumn.filter(table_id=table_id).order_by("id")
    indexes = await BiIndex.filter(table_id=table_id).order_by("id")
    foreign_keys = await BiForeignKey.filter(table_id=table_id).order_by("id")

    record["columns"] = [await c.to_dict() for c in columns]
    record["indexes"] = [await i.to_dict() for i in indexes]
    record["foreign_keys"] = [await f.to_dict() for f in foreign_keys]
    return record


__all__ = [
    "BiAuditLogSearch",
    "BiAuditStatistics",
    "ChatSendSchema",
    "SqlRunSchema",
    "create_datasource",
    "create_llm_provider",
    "datasource_record",
    "delete_chat_session",
    "export_audit_logs",
    "generate_select",
    "get_audit_stats",
    "get_table_detail",
    "llm_provider_record",
    "list_columns",
    "list_session_messages",
    "list_sql_history",
    "list_tables",
    "list_user_sessions",
    "preview_table",
    "run_sql",
    "search_audit_logs",
    "send_chat_message",
    "sync_datasource_metadata",
    "test_datasource",
    "test_llm_provider",
    "test_metric",
    "update_datasource",
    "update_llm_provider",
]
