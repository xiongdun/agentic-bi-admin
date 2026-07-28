"""AgenticBI 模块初始化数据 — 菜单、角色、默认租户、默认数据源。

启动时由 autodiscover 自动发现并执行 ``init()``。
所有操作幂等，重复启动不会重复创建。
"""

from __future__ import annotations

from app.business.bi.models import Datasource, DatasourceType, Tenant
from app.core.config import APP_SETTINGS
from app.core.log import log
from app.system.services.init_helper import _safe_update_or_create, apply_init_data
from app.utils import DataScopeType

# 菜单结构：顶级"智能 BI" + 4 个子工作台 + 按钮权限。
# 子菜单按钮在 Phase 1 仅做占位（路由尚未实装，按钮用于演示 reconcile）。
BI_MENU_CHILDREN = [
    {
        "menu_name": "对话工作台",
        "route_name": "bi_chat",
        "route_path": "/bi/chat",
        "component": "view.bi_chat",
        "icon": "mdi:robot-love",
        "order": 1,
        "buttons": [
            {"button_code": "B_BI_CHAT_NEW", "button_desc": "新建对话"},
            {"button_code": "B_BI_CHAT_SEND", "button_desc": "发送问题"},
            {"button_code": "B_BI_CHAT_EXPORT", "button_desc": "导出对话"},
        ],
    },
    {
        "menu_name": "元数据中心",
        "route_name": "bi_metadata",
        "route_path": "/bi/metadata",
        "component": "view.bi_metadata",
        "icon": "mdi:database-cog",
        "order": 2,
        "buttons": [
            {"button_code": "B_BI_DS_CREATE", "button_desc": "新增数据源"},
            {"button_code": "B_BI_DS_TEST", "button_desc": "测试连接"},
            {"button_code": "B_BI_DS_SYNC", "button_desc": "同步元数据"},
            {"button_code": "B_BI_DS_DELETE", "button_desc": "删除数据源"},
            {"button_code": "B_BI_SYNONYM_EDIT", "button_desc": "编辑业务同义词"},
        ],
    },
    {
        "menu_name": "SQL 工作台",
        "route_name": "bi_sql-workbench",
        "route_path": "/bi/sql-workbench",
        "component": "view.bi_sql-workbench",
        "icon": "mdi:database-search",
        "order": 3,
        "buttons": [
            {"button_code": "B_BI_SQL_RUN", "button_desc": "执行 SQL"},
            {"button_code": "B_BI_SQL_EXPLAIN", "button_desc": "查看执行计划"},
            {"button_code": "B_BI_SQL_HISTORY", "button_desc": "查看历史"},
        ],
    },
    {
        "menu_name": "模型管理",
        "route_name": "bi_models",
        "route_path": "/bi/models",
        "component": "view.bi_models",
        "icon": "mdi:robot-outline",
        "order": 4,
        "buttons": [
            {"button_code": "B_BI_MODEL_PROVIDER_CREATE", "button_desc": "新增提供商"},
            {"button_code": "B_BI_MODEL_PROVIDER_UPDATE", "button_desc": "编辑提供商"},
            {"button_code": "B_BI_MODEL_PROVIDER_DELETE", "button_desc": "删除提供商"},
            {"button_code": "B_BI_MODEL_PROVIDER_TEST", "button_desc": "测试连通"},
            {"button_code": "B_BI_MODEL_CREATE", "button_desc": "新增模型"},
            {"button_code": "B_BI_MODEL_UPDATE", "button_desc": "编辑模型"},
            {"button_code": "B_BI_MODEL_DELETE", "button_desc": "删除模型"},
        ],
    },
    {
        "menu_name": "指标管理",
        "route_name": "bi_metrics",
        "route_path": "/bi/metrics",
        "component": "view.bi_metrics",
        "icon": "mdi:sigma",
        "order": 5,
        "buttons": [
            {"button_code": "B_BI_METRIC_VIEW", "button_desc": "查看指标"},
            {"button_code": "B_BI_METRIC_MANAGE", "button_desc": "管理指标"},
        ],
    },
    {
        "menu_name": "审计面板",
        "route_name": "bi_audit",
        "route_path": "/bi/audit",
        "component": "view.bi_audit",
        "icon": "mdi:shield-search",
        "order": 6,
        "buttons": [
            {"button_code": "B_BI_AUDIT_VIEW", "button_desc": "查看审计"},
            {"button_code": "B_BI_AUDIT_EXPORT", "button_desc": "导出审计"},
        ],
    },
]


# 角色：B_BI_ADMIN（BI 管理员，看全部）+ R_BI_ANALYST（数据分析师，仅对话/工作台）
BI_ADMIN_ROLE = {
    "role_name": "BI 管理员",
    "role_code": "R_BI_ADMIN",
    "role_desc": "BI 管理员：可管理数据源、同义词、模型、查看审计",
    "data_scope": DataScopeType.all,
    "menus": ["home", "bi", "bi_chat", "bi_metadata", "bi_sql-workbench", "bi_models", "bi_metrics", "bi_audit"],
    "buttons": [
        "B_BI_CHAT_NEW",
        "B_BI_CHAT_SEND",
        "B_BI_CHAT_EXPORT",
        "B_BI_DS_CREATE",
        "B_BI_DS_TEST",
        "B_BI_DS_SYNC",
        "B_BI_DS_DELETE",
        "B_BI_SYNONYM_EDIT",
        "B_BI_SQL_RUN",
        "B_BI_SQL_EXPLAIN",
        "B_BI_SQL_HISTORY",
        "B_BI_MODEL_PROVIDER_CREATE",
        "B_BI_MODEL_PROVIDER_UPDATE",
        "B_BI_MODEL_PROVIDER_DELETE",
        "B_BI_MODEL_PROVIDER_TEST",
        "B_BI_MODEL_CREATE",
        "B_BI_MODEL_UPDATE",
        "B_BI_MODEL_DELETE",
        "B_BI_METRIC_VIEW",
        "B_BI_METRIC_MANAGE",
        "B_BI_AUDIT_VIEW",
        "B_BI_AUDIT_EXPORT",
    ],
    "apis": [],
}

BI_AUDITOR_ROLE = {
    "role_name": "BI 审计员",
    "role_code": "R_BI_AUDITOR",
    "role_desc": "BI 审计员：只读访问审计面板，可导出审计",
    "data_scope": DataScopeType.all,
    "menus": ["home", "bi", "bi_audit", "bi_metrics"],
    "buttons": [
        "B_BI_AUDIT_VIEW",
        "B_BI_AUDIT_EXPORT",
        "B_BI_METRIC_VIEW",
    ],
    "apis": [],
}

BI_ANALYST_ROLE = {
    "role_name": "数据分析师",
    "role_code": "R_BI_ANALYST",
    "role_desc": "数据分析师：可使用对话工作台与 SQL 工作台，不能改元数据",
    "data_scope": DataScopeType.all,
    "menus": ["home", "bi", "bi_chat", "bi_sql-workbench", "bi_metrics"],
    "buttons": [
        "B_BI_CHAT_NEW",
        "B_BI_CHAT_SEND",
        "B_BI_SQL_RUN",
        "B_BI_SQL_EXPLAIN",
        "B_BI_SQL_HISTORY",
        "B_BI_METRIC_VIEW",
    ],
    "apis": [],
}

BI_BUSINESS_ROLE = {
    "role_name": "业务用户",
    "role_code": "R_BI_BUSINESS",
    "role_desc": "业务用户：仅能使用对话工作台用自然语言取数",
    "data_scope": DataScopeType.all,
    "menus": ["home", "bi", "bi_chat", "bi_metrics"],
    "buttons": [
        "B_BI_CHAT_NEW",
        "B_BI_CHAT_SEND",
        "B_BI_METRIC_VIEW",
    ],
    "apis": [],
}


INIT_DATA = {
    "menus": [
        {
            "menu_name": "智能 BI",
            "route_name": "bi",
            "route_path": "/bi",
            "icon": "mdi:chart-line",
            "order": 30,
            "children": BI_MENU_CHILDREN,
            # 启用 reconcile：启动时按声明重建 bi 子树，移除手工加的孤儿。
            "reconcile": {"menus": True, "buttons": True},
        },
    ],
    "roles": [BI_ADMIN_ROLE, BI_AUDITOR_ROLE, BI_ANALYST_ROLE, BI_BUSINESS_ROLE],
    "users": [],
    "dictionaries": [],
}


# 默认租户 + 默认 SQLite 数据源（指向项目根的 demo.db）
DEFAULT_TENANT_CODE = "default"
DEFAULT_DATASOURCE_NAME = "默认演示数据源"

# demo.db 相对项目根的路径
DEFAULT_SQLITE_PATH = "bi_demo.db"


async def _ensure_default_tenant() -> Tenant:
    """确保默认租户存在（首次启动写入，重复启动幂等更新）。"""
    tenant, _ = await _safe_update_or_create(
        Tenant,
        {"code": DEFAULT_TENANT_CODE},
        {
            "name": "默认租户",
            "description": "AgenticBI 默认租户（演示用）",
            "is_active": True,
        },
    )
    return tenant


async def _ensure_default_datasource(tenant_id: int) -> Datasource:
    """确保默认数据源存在。

    SQLite 类型无需 host/port/username/password；extra 留空。
    """
    ds, _ = await _safe_update_or_create(
        Datasource,
        {"name": DEFAULT_DATASOURCE_NAME},
        {
            "type": DatasourceType.sqlite,
            "database": DEFAULT_SQLITE_PATH,
            "tenant_id": tenant_id,
            "is_default": True,
            "remark": "默认 SQLite 演示数据源（bi_demo.db）。 demo 库为空时可由 demo_data.py 灌入电商示例数据。",
        },
    )
    return ds


async def _bind_tenant_default_datasource(tenant: Tenant, datasource: Datasource) -> None:
    """回填 tenant.default_datasource_id。"""
    if tenant.default_datasource_id != datasource.id:
        tenant.default_datasource_id = datasource.id
        await tenant.save(update_fields=["default_datasource_id"])


# 预置 5 个电商 metric — 启动幂等灌入,保证业务用户首次进入就能用
DEFAULT_METRICS: list[dict] = [
    {
        "name": "销售额",
        "display_name": "销售额",
        "description": "已支付订单的总金额（人民币）",
        "sql_template": "SUM({order}.amount) WHERE {order}.status='paid'",
        "unit": "元",
    },
    {
        "name": "订单数",
        "display_name": "订单数",
        "description": "已支付订单总数",
        "sql_template": "COUNT({order}.id) WHERE {order}.status='paid'",
        "unit": "单",
    },
    {
        "name": "退款额",
        "display_name": "退款额",
        "description": "已审核通过的退款总金额",
        "sql_template": "SUM({return}.refunded_amount) WHERE {return}.status='approved'",
        "unit": "元",
    },
    {
        "name": "客单价",
        "display_name": "客单价",
        "description": "平均每单金额（销售额 ÷ 订单数）",
        "sql_template": "CAST(SUM(CASE WHEN {order}.status='paid' THEN {order}.amount ELSE 0 END) AS REAL) / NULLIF(COUNT(CASE WHEN {order}.status='paid' THEN 1 END), 0)",
        "unit": "元/单",
    },
    {
        "name": "月活客户",
        "display_name": "月活客户",
        "description": "当月有过成交的客户数",
        "sql_template": "COUNT(DISTINCT {order}.customer_id) WHERE {order}.status='paid'",
        "unit": "人",
    },
]


async def _ensure_default_metrics(datasource_id: int) -> list:
    """确保默认 5 个 metric 存在（幂等,upsert by (name, datasource_id)）。"""
    from app.business.bi.models.semantic import Metric
    from app.core.base_model import StatusType

    out: list = []
    for m in DEFAULT_METRICS:
        obj, _ = await _safe_update_or_create(
            Metric,
            {"name": m["name"], "datasource_id": datasource_id},
            {
                **m,
                "datasource_id": datasource_id,
                "owner_id": 1,
                "status_type": StatusType.enable,
            },
        )
        out.append(obj)
    return out


async def _warn_if_no_llm() -> None:
    """启动时校验 LLM provider 是否可用；缺失则强 warn（chat 会返 4001）。"""
    try:
        from app.business.bi.llm import get_router

        if not get_router().has_real_provider():
            log.warning("=" * 60)
            log.warning("BI 模块：未配置 LLM Provider")
            log.warning("对话工作台将返回 4001 错误")
            log.warning("请访问 /bi/models 添加至少 1 个启用的 Provider")
            log.warning("=" * 60)
    except Exception:  # noqa: BLE001
        # router 探活失败不应阻塞启动
        pass


async def _ensure_default_datasource_metadata(datasource: Datasource) -> None:
    """启动时确保默认数据源的 BiTable/BiColumn 元数据已同步。

    BiTable 为空(从未 sync 过)时跑一次 ``sync_datasource``;非空则跳过,
    避免覆盖用户在 UI 里手工编辑过的列描述 / 标签。

    不同步会导致 ``_build_schema_text`` 返回 ``(empty schema...)``,
    LLM 拿不到真实表名,会把 metric.sql_template 里的 ``{order}`` 占位符
    当字面量复制进 SQL → sqlglot 解析失败 → executor 跳过 → 无数据无解释。
    """
    try:
        from app.business.bi.metadata.sync import sync_datasource
        from app.business.bi.models import BiTable

        existing = await BiTable.filter(datasource_id=datasource.id).count()
        if existing > 0:
            log.info(f"BI init: datasource '{datasource.name}' already has {existing} tables, skip metadata sync")
            return
        result = await sync_datasource(datasource)
        log.info(f"BI init: synced metadata for datasource '{datasource.name}': {result.tables} tables, {result.columns} columns" + (f", errors={result.errors}" if result.errors else ""))
    except Exception as exc:  # noqa: BLE001
        log.warning(f"BI init: failed to sync default datasource metadata: {exc}")


async def init() -> None:
    """bi 模块初始化入口：菜单/角色 + 默认租户 + 默认数据源 + LLM router 刷新。"""
    # 一次性迁移：旧版 route_name 用了 bi_sqlworkbench（无连字符），
    # 与前端 elegant-router 生成的 bi_sql-workbench 不一致，导致 i18n 回退显示原始 key。
    # 在 apply_init_data 之前把旧 route_name 改正，避免 route_path 唯一约束冲突。
    from app.system.models import Menu

    _legacy = await Menu.filter(route_name="bi_sqlworkbench").first()
    if _legacy:
        _legacy.route_name = "bi_sql-workbench"
        await _legacy.save(update_fields=["route_name"])
        log.warning("Migrated legacy menu route_name 'bi_sqlworkbench' -> 'bi_sql-workbench'")
    # 先 apply 菜单与角色（幂等，含 reconcile 子树清理）
    await apply_init_data(INIT_DATA)
    tenant = await _ensure_default_tenant()
    datasource = await _ensure_default_datasource(tenant.id)
    await _bind_tenant_default_datasource(tenant, datasource)
    # 预置默认 metric（必须在数据源存在之后；幂等）
    try:
        seeded = await _ensure_default_metrics(datasource.id)
        log.info(f"BI init: seeded {len(seeded)} default metrics for datasource {datasource.name}")
    except Exception as exc:  # noqa: BLE001
        log.warning(f"BI init: failed to seed default metrics: {exc}")
    # 启动时从 DB 重建 LLM router（DB 优先，env 兜底）
    try:
        from app.business.bi.llm import refresh_router

        await refresh_router()
    except Exception:  # noqa: BLE001
        # router 刷新失败不应阻塞模块启动
        pass
    # 启动时校验 LLM provider 配置；缺失则强 warn（chat 会返 4001）
    await _warn_if_no_llm()
    # 启动时同步默认数据源元数据：BiTable 为空则自动 sync 一次,
    # 否则 LLM 拿到 "(empty schema)" 会把 metric 模板里的 {order} 占位符
    # 当字面量复制进 SQL,导致 sqlglot 解析失败 → executor 跳过 → 无数据无解释
    await _ensure_default_datasource_metadata(datasource)
    # 启动时跑一次审计清理（避免历史数据无限增长）
    try:
        from app.business.bi.services.audit import cleanup_old_audit_logs

        retention = int(getattr(APP_SETTINGS, "BI_AUDIT_RETENTION_DAYS", 90))
        await cleanup_old_audit_logs(retention_days=retention)
    except Exception:  # noqa: BLE001
        pass
