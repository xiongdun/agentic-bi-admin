"""BI 模块初始化数据 — 菜单、角色、按钮码种子。

启动时由 autodiscover 自动发现并执行 init()。
所有操作幂等，重复启动不会重复创建。
"""

from __future__ import annotations

from app.system.services import apply_init_data
from app.utils import DataScopeType, StatusType

# BI 子菜单与按钮码声明。reconcile={"menus": True, "buttons": True} 启用后，
# 本子树成为 IaC 单一数据源，Web UI 手工加的同子树菜单/按钮会在下次重启被清理。
BI_MENU_CHILDREN = [
    {
        "menu_name": "智能对话",
        "route_name": "bi_chat",
        "route_path": "/bi/chat",
        "component": "view.bi_chat",
        "icon": "mdi:chat-outline",
        "order": 1,
        "buttons": [
            {"button_code": "B_BI_CHAT_NEW", "button_desc": "新建对话"},
            {"button_code": "B_BI_CHAT_DELETE", "button_desc": "删除对话"},
        ],
    },
    {
        "menu_name": "元数据管理",
        "route_name": "bi_metadata",
        "route_path": "/bi/metadata",
        "component": "view.bi_metadata",
        "icon": "mdi:database-search-outline",
        "order": 2,
        "buttons": [
            {"button_code": "B_BI_DS_CREATE", "button_desc": "创建数据源"},
            {"button_code": "B_BI_DS_EDIT", "button_desc": "编辑数据源"},
            {"button_code": "B_BI_DS_DELETE", "button_desc": "删除数据源"},
            {"button_code": "B_BI_DS_TEST", "button_desc": "测试数据源连接"},
            {"button_code": "B_BI_DS_SYNC", "button_desc": "同步元数据"},
        ],
    },
    {
        "menu_name": "数据源详情",
        "route_name": "bi_metadata-detail",
        "route_path": "/bi/metadata-detail/:id",
        "component": "view.bi_metadata-detail",
        "icon": "mdi:database-eye-outline",
        "order": 99,
        "hide_in_menu": True,
        "active_menu": "bi_metadata",
    },
    {
        "menu_name": "SQL 工作台",
        "route_name": "bi_sql-workbench",
        "route_path": "/bi/sql-workbench",
        "component": "view.bi_sql-workbench",
        "icon": "mdi:console",
        "order": 3,
        "buttons": [
            {"button_code": "B_BI_SQL_RUN", "button_desc": "执行 SQL"},
        ],
    },
    {
        "menu_name": "指标管理",
        "route_name": "bi_metrics",
        "route_path": "/bi/metrics",
        "component": "view.bi_metrics",
        "icon": "mdi:chart-bar",
        "order": 4,
        "buttons": [
            {"button_code": "B_BI_METRIC_VIEW", "button_desc": "查看指标"},
            {"button_code": "B_BI_METRIC_CREATE", "button_desc": "创建指标"},
            {"button_code": "B_BI_METRIC_EDIT", "button_desc": "编辑指标"},
            {"button_code": "B_BI_METRIC_DELETE", "button_desc": "删除指标"},
            {"button_code": "B_BI_METRIC_TEST", "button_desc": "测试指标"},
        ],
    },
    {
        "menu_name": "LLM 配置",
        "route_name": "bi_models",
        "route_path": "/bi/models",
        "component": "view.bi_models",
        "icon": "mdi:robot",
        "order": 5,
        "buttons": [
            {"button_code": "B_BI_MODEL_PROVIDER_VIEW", "button_desc": "查看 LLM Provider"},
            {"button_code": "B_BI_MODEL_PROVIDER_CREATE", "button_desc": "创建 LLM Provider"},
            {"button_code": "B_BI_MODEL_PROVIDER_EDIT", "button_desc": "编辑 LLM Provider"},
            {"button_code": "B_BI_MODEL_PROVIDER_DELETE", "button_desc": "删除 LLM Provider"},
            {"button_code": "B_BI_MODEL_PROVIDER_TEST", "button_desc": "测试 LLM Provider"},
        ],
    },
    {
        "menu_name": "审计日志",
        "route_name": "bi_audit",
        "route_path": "/bi/audit",
        "component": "view.bi_audit",
        "icon": "mdi:shield-check",
        "order": 6,
        "buttons": [
            {"button_code": "B_BI_AUDIT_VIEW", "button_desc": "查看审计日志"},
            {"button_code": "B_BI_AUDIT_EXPORT", "button_desc": "导出审计日志"},
        ],
    },
    {
        "menu_name": "图表库",
        "route_name": "bi_charts",
        "route_path": "/bi/charts",
        "component": "view.bi_charts",
        "icon": "mdi:chart-box-outline",
        "order": 7,
        "buttons": [
            {"button_code": "B_BI_CHART_VIEW", "button_desc": "查看图表"},
            {"button_code": "B_BI_CHART_CREATE", "button_desc": "保存图表"},
            {"button_code": "B_BI_CHART_EDIT", "button_desc": "编辑图表"},
            {"button_code": "B_BI_CHART_DELETE", "button_desc": "删除图表"},
            {"button_code": "B_BI_CHART_REFRESH", "button_desc": "刷新图表数据"},
            {"button_code": "B_BI_CHART_SHARE", "button_desc": "外部分享"},
        ],
    },
    {
        "menu_name": "图表详情",
        "route_name": "bi_chart-detail",
        "route_path": "/bi/chart-detail/:id",
        "component": "view.bi_chart-detail",
        "icon": "mdi:chart-line",
        "order": 99,
        "hide_in_menu": True,
        "active_menu": "bi_charts",
    },
]

# BI 全量按钮码聚合，便于角色授权引用。
BI_ALL_BUTTONS = [
    "B_BI_CHAT_NEW",
    "B_BI_CHAT_DELETE",
    "B_BI_DS_CREATE",
    "B_BI_DS_EDIT",
    "B_BI_DS_DELETE",
    "B_BI_DS_TEST",
    "B_BI_DS_SYNC",
    "B_BI_SQL_RUN",
    "B_BI_METRIC_VIEW",
    "B_BI_METRIC_CREATE",
    "B_BI_METRIC_EDIT",
    "B_BI_METRIC_DELETE",
    "B_BI_METRIC_TEST",
    "B_BI_MODEL_PROVIDER_VIEW",
    "B_BI_MODEL_PROVIDER_CREATE",
    "B_BI_MODEL_PROVIDER_EDIT",
    "B_BI_MODEL_PROVIDER_DELETE",
    "B_BI_MODEL_PROVIDER_TEST",
    "B_BI_AUDIT_VIEW",
    "B_BI_AUDIT_EXPORT",
    "B_BI_CHART_VIEW",
    "B_BI_CHART_CREATE",
    "B_BI_CHART_EDIT",
    "B_BI_CHART_DELETE",
    "B_BI_CHART_REFRESH",
    "B_BI_CHART_SHARE",
]

# BI 全量菜单 route_name（含顶级与子菜单）。
BI_ALL_MENUS = [
    "home",
    "bi",
    "bi_chat",
    "bi_metadata",
    "bi_metadata-detail",
    "bi_sql-workbench",
    "bi_metrics",
    "bi_models",
    "bi_audit",
    "bi_charts",
    "bi_chart-detail",
]

# 数据分析师可见菜单与按钮码子集。
BI_ANALYST_MENUS = [
    "home",
    "bi",
    "bi_chat",
    "bi_sql-workbench",
    "bi_metrics",
    "bi_charts",
    "bi_chart-detail",
]
BI_ANALYST_BUTTONS = [
    "B_BI_CHAT_NEW",
    "B_BI_CHAT_DELETE",
    "B_BI_SQL_RUN",
    "B_BI_METRIC_VIEW",
    "B_BI_CHART_VIEW",
    "B_BI_CHART_CREATE",
    "B_BI_CHART_EDIT",
    "B_BI_CHART_DELETE",
    "B_BI_CHART_REFRESH",
    "B_BI_CHART_SHARE",
]

# apis 字段：BI API 路由的 route_key（``APIRoute.name``）列表。
# ``ensure_role`` 通过 ``_route_key_index()`` 解析 route_key → (method, path)，
# 解析失败会 log.warning，因此本列表必须与 ``api/*.py`` 中 ``name=...`` 一致。
#
# BI 管理员：全部 BI 路由
BI_ADMIN_APIS: list[str] = [
    # datasource（CRUD + test + sync）
    "bi.datasources.list",
    "bi.datasources.get",
    "bi.datasources.create",
    "bi.datasources.update",
    "bi.datasources.delete",
    "bi.datasources.batch_delete",
    "bi.datasources.test",
    "bi.datasources.sync",
    # metadata（tables + columns 只读 + 表详情）
    "bi.tables.list",
    "bi.tables.get",
    "bi.tables.detail",
    "bi.columns.list",
    "bi.columns.get",
    # chat（会话 CRUD + SSE /send）
    "bi.chat.create",
    "bi.chat.list",
    "bi.chat.delete",
    "bi.chat.messages",
    "bi.chat.send",
    # sql_workbench
    "bi.sql.run",
    "bi.sql.explain",
    "bi.sql.format",
    "bi.sql.history",
    "bi.sql.preview",
    "bi.sql.generate_select",
    # metric（CRUD + test）
    "bi.metrics.list",
    "bi.metrics.get",
    "bi.metrics.create",
    "bi.metrics.update",
    "bi.metrics.delete",
    "bi.metrics.batch_delete",
    "bi.metrics.test",
    # llm（Provider + Model CRUD + Provider test）
    "bi.providers.list",
    "bi.providers.get",
    "bi.providers.create",
    "bi.providers.update",
    "bi.providers.delete",
    "bi.providers.batch_delete",
    "bi.providers.test",
    "bi.models.list",
    "bi.models.get",
    "bi.models.create",
    "bi.models.update",
    "bi.models.delete",
    "bi.models.batch_delete",
    # audit（search + stats + export + get）
    "bi.audit.search",
    "bi.audit.get",
    "bi.audit.stats",
    "bi.audit.export",
    # chart（CRUD + refresh + share + 免登录查看）
    "bi.charts.create",
    "bi.charts.list",
    "bi.charts.tags",
    "bi.charts.get",
    "bi.charts.update",
    "bi.charts.delete",
    "bi.charts.batch_delete",
    "bi.charts.refresh",
    "bi.charts.share_enable",
    "bi.charts.share_disable",
    "bi.charts.shared",
]

# 数据分析师：仅对话 / SQL 工作台 / 指标查看相关路由
BI_ANALYST_APIS: list[str] = [
    # chat（会话 CRUD + SSE /send）
    "bi.chat.create",
    "bi.chat.list",
    "bi.chat.delete",
    "bi.chat.messages",
    "bi.chat.send",
    # sql_workbench
    "bi.sql.run",
    "bi.sql.explain",
    "bi.sql.format",
    "bi.sql.history",
    "bi.sql.preview",
    "bi.sql.generate_select",
    # metric（只读 + test）
    "bi.metrics.list",
    "bi.metrics.get",
    "bi.metrics.test",
    # metadata（只读 — 选表/列做 SQL 工作台辅助）
    "bi.tables.list",
    "bi.tables.get",
    "bi.tables.detail",
    "bi.columns.list",
    "bi.columns.get",
    # chart（CRUD + refresh + share + 免登录查看 — 数据分析师可保存/管理自己的图表）
    "bi.charts.create",
    "bi.charts.list",
    "bi.charts.tags",
    "bi.charts.get",
    "bi.charts.update",
    "bi.charts.delete",
    "bi.charts.batch_delete",
    "bi.charts.refresh",
    "bi.charts.share_enable",
    "bi.charts.share_disable",
    "bi.charts.shared",
]

BI_ROLE_SEEDS = [
    {
        "role_name": "BI管理员",
        "role_code": "R_BI_ADMIN",
        "role_desc": "BI 管理员，负责数据源、元数据、指标、LLM 配置与审计的全量维护",
        "data_scope": DataScopeType.all,
        "menus": BI_ALL_MENUS,
        "buttons": BI_ALL_BUTTONS,
        "apis": BI_ADMIN_APIS,
    },
    {
        "role_name": "数据分析师",
        "role_code": "R_BI_ANALYST",
        "role_desc": "数据分析师，可使用智能对话、SQL 工作台与查看指标",
        "data_scope": DataScopeType.scope,
        "menus": BI_ANALYST_MENUS,
        "buttons": BI_ANALYST_BUTTONS,
        "apis": BI_ANALYST_APIS,
    },
]

INIT_DATA = {
    "menus": [
        {
            "menu_name": "智能 BI",
            "route_name": "bi",
            "route_path": "/bi",
            "icon": "mdi:chart-line",
            "order": 30,
            "children": BI_MENU_CHILDREN,
            "reconcile": {"menus": True, "buttons": True},
        },
    ],
    "roles": BI_ROLE_SEEDS,
    "users": [],
    "dictionaries": [],
}


async def init() -> None:
    """BI 模块初始化：写入菜单/角色/按钮码种子。

    项目历史教训：``init()`` 必须包含 ``await apply_init_data(INIT_DATA)``，
    否则重启时菜单不会更新。``init()`` 还必须调用
    ``_ensure_default_datasource_metadata()``，若 BiTable 为空且存在默认数据源，
    自动触发元数据同步，避免 LLM 无真实表名可引用。
    """
    await apply_init_data(INIT_DATA)
    # 项目历史教训：自动同步默认数据源元数据
    await _ensure_default_datasource_metadata()


async def _ensure_default_datasource_metadata() -> None:
    """若 BiTable 为空且存在默认数据源，自动触发元数据同步。"""
    from app.business.bi.metadata.sync import _ensure_default_datasource_metadata as _sync
    from app.business.bi.models import BiDatasource

    # 查找第一个启用的数据源作为默认
    datasource = await BiDatasource.filter(status_type=StatusType.enable).first()
    if datasource:
        await _sync(datasource)
