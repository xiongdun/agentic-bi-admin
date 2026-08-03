"""BiDashboard 模型与服务测试。

覆盖：
- ``BiDashboard`` 模型基础创建（默认 layout、租户隔离字段）
- ``validate_layout`` —— 长度/范围/x+w 边界
- ``refresh_dashboard`` —— 成功/失败不降级/deleted 状态
- ``preview_dashboard`` —— 返回已有快照不重跑
- API 鉴权：未登录访问受保护端点返回 2100
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.business.bi.models import BiDashboard

pytestmark = pytest.mark.asyncio(loop_scope="session")

PREFIX = "/api/v1/business/bi"


# ===================== Model =====================


class TestBiDashboardModel:
    async def test_create_dashboard_default_layout(self, app, bi_datasource):
        """创建仪表盘，默认 layout 为 {items: []}。"""
        dashboard = await BiDashboard.create(
            name="经营日报",
            description="每月更新",
            tenant_id=bi_datasource.tenant_id,
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )
        await dashboard.refresh_from_db()
        assert dashboard.id > 0
        assert dashboard.layout == {"items": []}
        assert dashboard.tenant_id == bi_datasource.tenant_id
        assert dashboard.name == "经营日报"
