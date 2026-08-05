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
            {"button_code": "B_BI_CHART_EXPORT", "button_desc": "导出图表"},
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
    {
        "menu_name": "查询任务",
        "route_name": "bi_async-query-tasks",
        "route_path": "/bi/async-query-tasks",
        "component": "view.bi_async-query-tasks",
        "icon": "mdi:cloud-download-outline",
        "order": 8,
        "buttons": [
            {"button_code": "B_BI_SQL_ASYNC_RUN", "button_desc": "提交异步查询"},
            {"button_code": "B_BI_SQL_TASK_VIEW", "button_desc": "查看任务"},
            {"button_code": "B_BI_SQL_TASK_CANCEL", "button_desc": "取消任务"},
            {"button_code": "B_BI_SQL_TASK_DELETE", "button_desc": "删除任务"},
            {"button_code": "B_BI_SQL_TASK_DOWNLOAD", "button_desc": "下载结果"},
        ],
    },
    {
        "menu_name": "任务详情",
        "route_name": "bi_async-query-detail",
        "route_path": "/bi/async-query-detail/:id",
        "component": "view.bi_async-query-detail",
        "icon": "mdi:chart-line",
        "order": 99,
        "hide_in_menu": True,
        "active_menu": "bi_async-query-tasks",
    },
    {
        "menu_name": "仪表盘",
        "route_name": "bi_dashboards",
        "route_path": "/bi/dashboards",
        "component": "view.bi_dashboards",
        "icon": "mdi:view-dashboard-outline",
        "order": 9,
        "buttons": [
            {"button_code": "B_BI_DASHBOARD_CREATE", "button_desc": "创建仪表盘"},
            {"button_code": "B_BI_DASHBOARD_VIEW", "button_desc": "查看仪表盘"},
            {"button_code": "B_BI_DASHBOARD_EDIT", "button_desc": "编辑仪表盘"},
            {"button_code": "B_BI_DASHBOARD_DELETE", "button_desc": "删除仪表盘"},
            {"button_code": "B_BI_DASHBOARD_EXPORT", "button_desc": "导出仪表盘"},
        ],
    },
    {
        "menu_name": "仪表盘详情",
        "route_name": "bi_dashboard-detail",
        "route_path": "/bi/dashboard-detail/:id",
        "component": "view.bi_dashboard-detail",
        "icon": "mdi:view-dashboard",
        "order": 99,
        "hide_in_menu": True,
        "active_menu": "bi_dashboards",
    },
    {
        "menu_name": "脱敏规则",
        "route_name": "bi_masking",
        "route_path": "/bi/masking",
        "component": "view.bi_masking",
        "icon": "mdi:shield-half-full",
        "order": 10,
        "buttons": [
            {"button_code": "B_BI_MASKING_VIEW", "button_desc": "查看脱敏规则"},
            {"button_code": "B_BI_MASKING_CREATE", "button_desc": "创建脱敏规则"},
            {"button_code": "B_BI_MASKING_EDIT", "button_desc": "编辑脱敏规则"},
            {"button_code": "B_BI_MASKING_DELETE", "button_desc": "删除脱敏规则"},
        ],
    },
    {
        "menu_name": "配额配置",
        "route_name": "bi_quota",
        "route_path": "/bi/quota",
        "component": "view.bi_quota",
        "icon": "mdi:speedometer",
        "order": 11,
        "buttons": [
            {"button_code": "B_BI_QUOTA_VIEW", "button_desc": "查看配额配置"},
            {"button_code": "B_BI_QUOTA_CREATE", "button_desc": "创建配额配置"},
            {"button_code": "B_BI_QUOTA_EDIT", "button_desc": "编辑配额配置"},
            {"button_code": "B_BI_QUOTA_DELETE", "button_desc": "删除配额配置"},
        ],
    },
    {
        "menu_name": "仪表盘订阅",
        "route_name": "bi_subscriptions",
        "route_path": "/bi/subscriptions",
        "component": "view.bi_subscriptions",
        "icon": "mdi:calendar-clock",
        "order": 12,
        "buttons": [
            {"button_code": "B_BI_SUBSCRIPTION_VIEW", "button_desc": "查看订阅"},
            {"button_code": "B_BI_SUBSCRIPTION_CREATE", "button_desc": "创建订阅"},
            {"button_code": "B_BI_SUBSCRIPTION_EDIT", "button_desc": "编辑订阅"},
            {"button_code": "B_BI_SUBSCRIPTION_DELETE", "button_desc": "删除订阅"},
        ],
    },
    {
        "menu_name": "订阅消息",
        "route_name": "bi_notify-records",
        "route_path": "/bi/notify-records",
        "component": "view.bi_notify-records",
        "icon": "mdi:bell-outline",
        "order": 13,
        "buttons": [
            {"button_code": "B_BI_NOTIFY_VIEW", "button_desc": "查看消息"},
        ],
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
    "B_BI_CHART_EXPORT",
    "B_BI_SQL_ASYNC_RUN",
    "B_BI_SQL_TASK_VIEW",
    "B_BI_SQL_TASK_CANCEL",
    "B_BI_SQL_TASK_DELETE",
    "B_BI_SQL_TASK_DOWNLOAD",
    "B_BI_DASHBOARD_CREATE",
    "B_BI_DASHBOARD_VIEW",
    "B_BI_DASHBOARD_EDIT",
    "B_BI_DASHBOARD_DELETE",
    "B_BI_DASHBOARD_EXPORT",
    # masking / quota
    "B_BI_MASKING_VIEW",
    "B_BI_MASKING_CREATE",
    "B_BI_MASKING_EDIT",
    "B_BI_MASKING_DELETE",
    "B_BI_QUOTA_VIEW",
    "B_BI_QUOTA_CREATE",
    "B_BI_QUOTA_EDIT",
    "B_BI_QUOTA_DELETE",
    # subscription / notify
    "B_BI_SUBSCRIPTION_VIEW",
    "B_BI_SUBSCRIPTION_CREATE",
    "B_BI_SUBSCRIPTION_EDIT",
    "B_BI_SUBSCRIPTION_DELETE",
    "B_BI_NOTIFY_VIEW",
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
    "bi_async-query-tasks",
    "bi_async-query-detail",
    "bi_dashboards",
    "bi_dashboard-detail",
    "bi_masking",
    "bi_quota",
    "bi_subscriptions",
    "bi_notify-records",
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
    "bi_async-query-tasks",
    "bi_async-query-detail",
    "bi_dashboards",
    "bi_dashboard-detail",
    "bi_subscriptions",
    "bi_notify-records",
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
    "B_BI_CHART_EXPORT",
    "B_BI_SQL_ASYNC_RUN",
    "B_BI_SQL_TASK_VIEW",
    "B_BI_SQL_TASK_CANCEL",
    "B_BI_SQL_TASK_DELETE",
    "B_BI_SQL_TASK_DOWNLOAD",
    "B_BI_DASHBOARD_CREATE",
    "B_BI_DASHBOARD_VIEW",
    "B_BI_DASHBOARD_EDIT",
    "B_BI_DASHBOARD_DELETE",
    "B_BI_DASHBOARD_EXPORT",
    # subscription / notify — 数据分析师可管理自己的订阅与查看消息
    "B_BI_SUBSCRIPTION_VIEW",
    "B_BI_SUBSCRIPTION_CREATE",
    "B_BI_SUBSCRIPTION_EDIT",
    "B_BI_SUBSCRIPTION_DELETE",
    "B_BI_NOTIFY_VIEW",
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
    # async_query（提交 + 列表 + 详情 + 结果 + 取消 + 删除 + 下载）
    "bi.tasks.run",
    "bi.tasks.list",
    "bi.tasks.get",
    "bi.tasks.result",
    "bi.tasks.cancel",
    "bi.tasks.delete",
    "bi.tasks.download",
    # dashboard（CRUD + refresh + preview）
    "bi.dashboards.create",
    "bi.dashboards.list",
    "bi.dashboards.get",
    "bi.dashboards.update",
    "bi.dashboards.delete",
    "bi.dashboards.refresh",
    "bi.dashboards.preview",
    # masking（CRUD）
    "bi.masking.list",
    "bi.masking.get",
    "bi.masking.create",
    "bi.masking.update",
    "bi.masking.delete",
    "bi.masking.batch_delete",
    # quota（CRUD）
    "bi.quota.list",
    "bi.quota.get",
    "bi.quota.create",
    "bi.quota.update",
    "bi.quota.delete",
    "bi.quota.batch_delete",
    # subscription（CRUD + 行级隔离）
    "bi.subscription.list",
    "bi.subscription.get",
    "bi.subscription.create",
    "bi.subscription.update",
    "bi.subscription.delete",
    "bi.subscription.batch_delete",
    # notify（只读 + 标记已读 + 未读数）
    "bi.notify.list",
    "bi.notify.unread_count",
    "bi.notify.mark_read",
    # export（报表导出）
    "bi.export.chart_csv",
    "bi.export.charts_excel",
    "bi.export.dashboard_excel",
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
    # async_query（提交 + 列表 + 详情 + 结果 + 取消 + 删除 + 下载 — 数据分析师可提交和管理自己的异步任务）
    "bi.tasks.run",
    "bi.tasks.list",
    "bi.tasks.get",
    "bi.tasks.result",
    "bi.tasks.cancel",
    "bi.tasks.delete",
    "bi.tasks.download",
    # dashboard（CRUD + refresh + preview — 数据分析师可创建/管理自己的仪表盘）
    "bi.dashboards.create",
    "bi.dashboards.list",
    "bi.dashboards.get",
    "bi.dashboards.update",
    "bi.dashboards.delete",
    "bi.dashboards.refresh",
    "bi.dashboards.preview",
    # subscription（CRUD + 行级隔离 — 数据分析师可管理自己的订阅）
    "bi.subscription.list",
    "bi.subscription.get",
    "bi.subscription.create",
    "bi.subscription.update",
    "bi.subscription.delete",
    "bi.subscription.batch_delete",
    # notify（只读 + 标记已读 + 未读数 — 数据分析师可查看自己的消息）
    "bi.notify.list",
    "bi.notify.unread_count",
    "bi.notify.mark_read",
    # export（报表导出 — 数据分析师可导出自己的图表/仪表盘）
    "bi.export.chart_csv",
    "bi.export.charts_excel",
    "bi.export.dashboard_excel",
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
