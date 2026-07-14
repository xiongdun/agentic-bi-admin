"""AgenticBI 模块 manifest — 顶层入口。

把 routers / init / permissions / events / data_policies 拼成
``BusinessModule``，由 ``app.core.autodiscover`` 自动发现并挂载。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.business.bi.events import BI_EVENTS
from app.business.bi.init_data import INIT_DATA, init
from app.business.bi.policies import BI_DATA_POLICIES
from app.utils import BusinessModule, BusinessRouter, PermissionSpec

# 顶级 router —— 包含全部 bi 子路由（datasource / metadata / chat / sql-workbench / audit / ...）
# 内部按 prefix 进一步拆。
router = APIRouter()

# —— 数据源管理 ——
from app.business.bi.api.chat import router as chat_router  # noqa: E402
from app.business.bi.api.datasource import router as datasource_router  # noqa: E402
from app.business.bi.api.metadata import router as metadata_router  # noqa: E402
from app.business.bi.api.sql_workbench import router as sql_router  # noqa: E402

router.include_router(datasource_router, prefix="")
router.include_router(metadata_router, prefix="")
router.include_router(sql_router, prefix="")
router.include_router(chat_router, prefix="")

# Phase 2 之后接入的 router（占位声明，确保 imports 缺包时立即失败）:
# from app.business.bi.api.chat import router as chat_router
# from app.business.bi.api.sql_workbench import router as sql_router
# from app.business.bi.api.audit import router as audit_router
# from app.business.bi.api.grant import router as grant_router
# from app.business.bi.api.masking import router as masking_router
# router.include_router(chat_router, prefix="")
# router.include_router(sql_router, prefix="")
# router.include_router(audit_router, prefix="")
# router.include_router(grant_router, prefix="")
# router.include_router(masking_router, prefix="")


module = BusinessModule(
    name="bi",
    title="智能 BI",
    version="0.1.0",
    routers=[BusinessRouter(router=router, auth="permission", tags=["智能 BI"])],
    init=init,
    permissions=PermissionSpec(init_data=INIT_DATA),
    events=BI_EVENTS,
    data_policies=BI_DATA_POLICIES,
)

__all__ = ["module"]
