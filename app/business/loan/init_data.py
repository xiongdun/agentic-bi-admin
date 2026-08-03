"""网贷业务模块初始化数据 — 菜单、角色种子。

启动时由 autodiscover 自动发现并执行 init()。
所有操作幂等，重复启动不会重复创建。
"""

from __future__ import annotations

from app.system.services import apply_init_data
from app.utils import DataScopeType

# 网贷子菜单与按钮码声明。reconcile={"menus": True, "buttons": True} 启用后，
# 本子树成为 IaC 单一数据源，Web UI 手工加的同子树菜单/按钮会在下次重启被清理。
LOAN_MENU_CHILDREN = [
    {
        "menu_name": "客户管理",
        "route_name": "loan_customer",
        "route_path": "/loan/customer",
        "component": "view.loan_customer",
        "icon": "mdi:account-group-outline",
        "order": 1,
        "buttons": [
            {"button_code": "B_LOAN_CUSTOMER_VIEW", "button_desc": "查看客户"},
            {"button_code": "B_LOAN_CUSTOMER_CREATE", "button_desc": "创建客户"},
            {"button_code": "B_LOAN_CUSTOMER_EDIT", "button_desc": "编辑客户"},
            {"button_code": "B_LOAN_CUSTOMER_DELETE", "button_desc": "删除客户"},
        ],
    },
    {
        "menu_name": "产品管理",
        "route_name": "loan_product",
        "route_path": "/loan/product",
        "component": "view.loan_product",
        "icon": "mdi:package-variant-closed",
        "order": 2,
        "buttons": [
            {"button_code": "B_LOAN_PRODUCT_VIEW", "button_desc": "查看产品"},
            {"button_code": "B_LOAN_PRODUCT_CREATE", "button_desc": "创建产品"},
            {"button_code": "B_LOAN_PRODUCT_EDIT", "button_desc": "编辑产品"},
            {"button_code": "B_LOAN_PRODUCT_DELETE", "button_desc": "删除产品"},
        ],
    },
    {
        "menu_name": "申请管理",
        "route_name": "loan_application",
        "route_path": "/loan/application",
        "component": "view.loan_application",
        "icon": "mdi:file-document-outline",
        "order": 3,
        "buttons": [
            {"button_code": "B_LOAN_APPLICATION_VIEW", "button_desc": "查看申请"},
            {"button_code": "B_LOAN_APPLICATION_APPROVE", "button_desc": "审批申请"},
            {"button_code": "B_LOAN_APPLICATION_REJECT", "button_desc": "拒绝申请"},
        ],
    },
    {
        "menu_name": "合同管理",
        "route_name": "loan_contract",
        "route_path": "/loan/contract",
        "component": "view.loan_contract",
        "icon": "mdi:file-sign",
        "order": 4,
        "buttons": [
            {"button_code": "B_LOAN_CONTRACT_VIEW", "button_desc": "查看合同"},
        ],
    },
    {
        "menu_name": "还款管理",
        "route_name": "loan_repayment",
        "route_path": "/loan/repayment",
        "component": "view.loan_repayment",
        "icon": "mdi:currency-cny",
        "order": 5,
        "buttons": [
            {"button_code": "B_LOAN_REPAYMENT_VIEW", "button_desc": "查看还款"},
            {"button_code": "B_LOAN_REPAYMENT_RECORD", "button_desc": "登记还款"},
        ],
    },
    {
        "menu_name": "风控管理",
        "route_name": "loan_risk",
        "route_path": "/loan/risk",
        "component": "view.loan_risk",
        "icon": "mdi:shield-alert-outline",
        "order": 6,
        "buttons": [
            {"button_code": "B_LOAN_RISK_VIEW", "button_desc": "查看风控评估"},
        ],
    },
    {
        "menu_name": "催收管理",
        "route_name": "loan_collection",
        "route_path": "/loan/collection",
        "component": "view.loan_collection",
        "icon": "mdi:phone-alert",
        "order": 7,
        "buttons": [
            {"button_code": "B_LOAN_COLLECTION_VIEW", "button_desc": "查看催收记录"},
            {"button_code": "B_LOAN_COLLECTION_RECORD", "button_desc": "登记催收"},
        ],
    },
    {
        "menu_name": "资金方管理",
        "route_name": "loan_funder",
        "route_path": "/loan/funder",
        "component": "view.loan_funder",
        "icon": "mdi:bank-outline",
        "order": 8,
        "buttons": [
            {"button_code": "B_LOAN_FUNDER_VIEW", "button_desc": "查看资金方"},
            {"button_code": "B_LOAN_FUNDER_CREATE", "button_desc": "创建资金方"},
            {"button_code": "B_LOAN_FUNDER_EDIT", "button_desc": "编辑资金方"},
            {"button_code": "B_LOAN_FUNDER_DELETE", "button_desc": "删除资金方"},
        ],
    },
]

# 网贷全量按钮码聚合，便于角色授权引用。
LOAN_ALL_BUTTONS = [
    "B_LOAN_CUSTOMER_VIEW",
    "B_LOAN_CUSTOMER_CREATE",
    "B_LOAN_CUSTOMER_EDIT",
    "B_LOAN_CUSTOMER_DELETE",
    "B_LOAN_PRODUCT_VIEW",
    "B_LOAN_PRODUCT_CREATE",
    "B_LOAN_PRODUCT_EDIT",
    "B_LOAN_PRODUCT_DELETE",
    "B_LOAN_APPLICATION_VIEW",
    "B_LOAN_APPLICATION_APPROVE",
    "B_LOAN_APPLICATION_REJECT",
    "B_LOAN_CONTRACT_VIEW",
    "B_LOAN_REPAYMENT_VIEW",
    "B_LOAN_REPAYMENT_RECORD",
    "B_LOAN_RISK_VIEW",
    "B_LOAN_COLLECTION_VIEW",
    "B_LOAN_COLLECTION_RECORD",
    "B_LOAN_FUNDER_VIEW",
    "B_LOAN_FUNDER_CREATE",
    "B_LOAN_FUNDER_EDIT",
    "B_LOAN_FUNDER_DELETE",
]

# 网贷全量菜单 route_name（含顶级与子菜单）。
LOAN_ALL_MENUS = [
    "home",
    "loan",
    "loan_customer",
    "loan_product",
    "loan_application",
    "loan_contract",
    "loan_repayment",
    "loan_risk",
    "loan_collection",
    "loan_funder",
]

LOAN_ROLE_SEEDS = [
    {
        "role_name": "网贷管理员",
        "role_code": "R_LOAN_ADMIN",
        "role_desc": "网贷管理员，负责客户、产品、申请、合同、还款、风控、催收、资金方的全量维护",
        "data_scope": DataScopeType.all,
        "menus": LOAN_ALL_MENUS,
        "buttons": LOAN_ALL_BUTTONS,
        "apis": [],
    },
    {
        "role_name": "网贷业务员",
        "role_code": "R_LOAN_OFFICER",
        "role_desc": "网贷业务员，可管理客户、申请、合同、还款登记",
        "data_scope": DataScopeType.scope,
        "menus": [
            "home",
            "loan",
            "loan_customer",
            "loan_application",
            "loan_contract",
            "loan_repayment",
        ],
        "buttons": [
            "B_LOAN_CUSTOMER_VIEW",
            "B_LOAN_CUSTOMER_CREATE",
            "B_LOAN_CUSTOMER_EDIT",
            "B_LOAN_APPLICATION_VIEW",
            "B_LOAN_APPLICATION_APPROVE",
            "B_LOAN_CONTRACT_VIEW",
            "B_LOAN_REPAYMENT_VIEW",
            "B_LOAN_REPAYMENT_RECORD",
        ],
        "apis": [],
    },
]

INIT_DATA = {
    "menus": [
        {
            "menu_name": "网贷管理",
            "route_name": "loan",
            "route_path": "/loan",
            "icon": "mdi:hand-coin-outline",
            "order": 40,
            "children": LOAN_MENU_CHILDREN,
            "reconcile": {"menus": True, "buttons": True},
        },
    ],
    "roles": LOAN_ROLE_SEEDS,
    "users": [],
    "dictionaries": [],
}


async def init() -> None:
    """网贷模块初始化：写入菜单/角色/按钮码种子。"""
    await apply_init_data(INIT_DATA)
