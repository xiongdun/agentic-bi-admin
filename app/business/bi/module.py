"""BI 智能数据分析模块 manifest。

autodiscover 通过本文件识别模块：注册路由前缀 /api/v1/business/bi/，
启动时由 leader worker 执行 init_data.init() 写入菜单/角色/按钮码种子。
"""

from __future__ import annotations

from app.business.bi.api import public_router, router
from app.business.bi.events import BI_EVENTS
from app.business.bi.init_data import INIT_DATA, init
from app.business.bi.policies import BI_DATA_POLICIES
from app.business.bi.services_async_query import cleanup_expired_tasks
from app.utils import BusinessModule, BusinessRouter, PeriodicTask, PermissionSpec

# BI 模块宽松限流配额：SSE 对话与 SQL 执行路径需要更高上限。
# autodiscover 会自动合并到 fastapi-guard 配置。
ENDPOINT_RATE_LIMITS = {
    "/api/v1/business/bi/chat/send": (30, 60),
    "/api/v1/business/bi/sql/run": (60, 60),
}


# 每日清理过期异步查询任务（> BI_ASYNC_QUERY_TTL_DAYS 天）：
# 软删 DB + 物理删 CSV + 清 Redis 状态
async def _run_cleanup() -> None:
    await cleanup_expired_tasks()


_cleanup_task = PeriodicTask(
    name="bi.async_query.cleanup",
    handler=_run_cleanup,
    interval_seconds=24 * 3600,
    leader_only=True,
)

module = BusinessModule(
    name="bi",
    title="智能 BI",
    version="0.1.0",
    routers=[
        BusinessRouter(router=router, auth="permission", tags=["智能 BI"]),
        # 公开路由：免登录查看分享图表（/charts/shared/{token}）
        BusinessRouter(router=public_router, auth="public", tags=["智能 BI"]),
    ],
    init=init,
    permissions=PermissionSpec(init_data=INIT_DATA),
    events=BI_EVENTS,
    data_policies=BI_DATA_POLICIES,
    tasks=[_cleanup_task],
)
