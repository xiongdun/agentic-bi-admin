"""BI 模块 API 聚合层 — 聚合 7 个子路由。

子路由清单：
- ``datasource`` —— 数据源管理（CRUD + /test + /sync）
- ``metadata`` —— 元数据查询（表 / 列只读 CRUD + 表详情）
- ``chat`` —— 智能对话（会话 CRUD + SSE /send）
- ``sql_workbench`` —— SQL 工作台（run / explain / format / history / preview / generate-select）
- ``metric`` —— 指标管理（CRUD + /test）
- ``llm`` —— LLM Provider/Model 管理（CRUD + Provider /test）
- ``audit`` —— 审计日志（search / stats / export / get）

module.py 挂载到 ``/api/v1/business/bi``，``auth="permission"`` 统一应用
``DependPermission``，各子路由再按需追加 ``require_buttons(...)`` 做按钮级权限。

路由 key（``APIRoute.name``）统一 ``bi.<resource>.<action>`` 三段式，供
``refresh_api_list()`` 同步元数据 + ``ensure_role`` 的 ``apis`` 字段引用。
"""

from fastapi import APIRouter

from app.business.bi.api.audit import router as audit_router
from app.business.bi.api.chat import router as chat_router
from app.business.bi.api.datasource import router as datasource_router
from app.business.bi.api.llm import router as llm_router
from app.business.bi.api.metadata import router as metadata_router
from app.business.bi.api.metric import router as metric_router
from app.business.bi.api.sql_workbench import router as sql_workbench_router

router = APIRouter()
router.include_router(datasource_router)
router.include_router(metadata_router)
router.include_router(chat_router)
router.include_router(sql_workbench_router)
router.include_router(metric_router)
router.include_router(llm_router, prefix="/llm")
router.include_router(audit_router)
