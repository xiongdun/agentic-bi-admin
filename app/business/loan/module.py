"""网贷业务模块 manifest。

autodiscover 通过本文件识别模块。
启动时由 leader worker 执行 init_data.init() 写入菜单/角色/按钮码种子。

注意：本模块当前仅注册模型与初始化数据，未注册 API 路由。
后续如需暴露 API，请在 ``api/`` 子目录中创建路由，并在本 manifest 的 ``routers`` 中声明。
"""

from __future__ import annotations

from app.business.loan.init_data import INIT_DATA, init
from app.utils import BusinessModule, PermissionSpec

module = BusinessModule(
    name="loan",
    title="网贷管理",
    version="0.1.0",
    routers=[],
    init=init,
    permissions=PermissionSpec(init_data=INIT_DATA),
)
