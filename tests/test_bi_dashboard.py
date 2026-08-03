"""BiDashboard 模型与服务测试。

覆盖：
- ``BiDashboard`` 模型基础创建（默认 layout、租户隔离字段）
- ``validate_layout_structure`` —— 长度/范围/x+w 边界
- ``validate_layout`` —— chartId 归属校验
- ``refresh_dashboard`` —— 成功/失败不降级/deleted 状态
- ``preview_dashboard`` —— 返回已有快照不重跑
- API 鉴权：未登录访问受保护端点返回 2100
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

from app.business.bi.models import BiChart, BiDashboard
from app.business.bi.schemas_dashboard import (
    BiDashboardCreateSchema,
    BiDashboardUpdateSchema,
    DashboardItemSchema,
    DashboardLayoutSchema,
)
from app.business.bi.services_dashboard import (
    create_dashboard,
    delete_dashboard,
    preview_dashboard,
    refresh_dashboard,
    update_dashboard,
    validate_layout,
    validate_layout_structure,
)
from app.core.code import Code
from app.core.exceptions import BizError
from app.core.sqids import encode_id

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


# ===================== validate_layout_structure =====================


class TestValidateLayoutStructure:
    async def test_empty_layout_passes(self, app):
        """空 layout 通过校验。"""
        validate_layout_structure({"items": []})
        validate_layout_structure({})

    async def test_too_many_items(self, app):
        """超过 BI_DASHBOARD_MAX_ITEMS 抛错。"""
        from app.business.bi.config import BIZ_SETTINGS

        items = [
            {"chartId": str(i), "x": 0, "y": i, "w": 1, "h": 1}
            for i in range(BIZ_SETTINGS.BI_DASHBOARD_MAX_ITEMS + 1)
        ]
        with pytest.raises(BizError):
            validate_layout_structure({"items": items})

    async def test_invalid_width(self, app):
        """w > 12 抛错。"""
        layout = {"items": [{"chartId": "abc", "x": 0, "y": 0, "w": 13, "h": 1}]}
        with pytest.raises(BizError):
            validate_layout_structure(layout)

    async def test_invalid_width_zero(self, app):
        """w < 1 抛错。"""
        layout = {"items": [{"chartId": "abc", "x": 0, "y": 0, "w": 0, "h": 1}]}
        with pytest.raises(BizError):
            validate_layout_structure(layout)

    async def test_invalid_height(self, app):
        """h > 6 抛错。"""
        layout = {"items": [{"chartId": "abc", "x": 0, "y": 0, "w": 1, "h": 7}]}
        with pytest.raises(BizError):
            validate_layout_structure(layout)

    async def test_x_plus_w_exceeds_12(self, app):
        """x + w > 12 抛错。"""
        layout = {"items": [{"chartId": "abc", "x": 10, "y": 0, "w": 6, "h": 1}]}
        with pytest.raises(BizError):
            validate_layout_structure(layout)

    async def test_negative_x(self, app):
        """x < 0 抛错。"""
        layout = {"items": [{"chartId": "abc", "x": -1, "y": 0, "w": 1, "h": 1}]}
        with pytest.raises(BizError):
            validate_layout_structure(layout)

    async def test_missing_chart_id(self, app):
        """chartId 缺失抛错。"""
        layout = {"items": [{"x": 0, "y": 0, "w": 1, "h": 1}]}
        with pytest.raises(BizError):
            validate_layout_structure(layout)

    async def test_valid_structure(self, app):
        """合法结构通过。"""
        layout = {
            "items": [
                {"chartId": "abc", "x": 0, "y": 0, "w": 6, "h": 2},
                {"chartId": "def", "x": 6, "y": 0, "w": 6, "h": 2},
            ]
        }
        items = validate_layout_structure(layout)
        assert len(items) == 2


# ===================== validate_layout (chartId 归属) =====================


class TestValidateLayout:
    async def test_valid_layout_with_real_chart(self, app, bi_datasource):
        """引用真实存在的 BiChart 通过校验。"""
        chart = await BiChart.create(
            name="c1",
            datasource_id=bi_datasource.id,
            chart_type="bar",
            x_col="m",
            y_col="s",
            sql_text="SELECT 1",
            result_snapshot={"columns": ["m"], "rows": [], "rowCount": 0, "elapsedMs": 0},
            snapshot_at=datetime.now(),
            tenant_id=bi_datasource.tenant_id,
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )
        layout = {
            "items": [
                {"chartId": encode_id(chart.id), "x": 0, "y": 0, "w": 6, "h": 2}
            ]
        }
        # 不抛异常即通过
        await validate_layout(layout, tenant_id=bi_datasource.tenant_id)

    async def test_invalid_chart_id(self, app, bi_datasource):
        """引用不存在的 chartId 抛错。"""
        layout = {
            "items": [
                {"chartId": encode_id(999999), "x": 0, "y": 0, "w": 6, "h": 2}
            ]
        }
        with pytest.raises(BizError):
            await validate_layout(layout, tenant_id=bi_datasource.tenant_id)


# ===================== refresh_dashboard =====================


async def _make_chart_and_dashboard(
    bi_datasource, chart_name="测试图表", dashboard_name="d1", sql_text="SELECT 1"
):
    """工具：创建一个 BiChart + 引用它的 BiDashboard。"""
    chart = await BiChart.create(
        name=chart_name,
        datasource_id=bi_datasource.id,
        chart_type="bar",
        x_col="m",
        y_col="s",
        sql_text=sql_text,
        result_snapshot={"columns": ["m"], "rows": [], "rowCount": 0, "elapsedMs": 0},
        snapshot_at=datetime.now(),
        tenant_id=bi_datasource.tenant_id,
        created_by=str(bi_datasource.tenant_id),
        updated_by=str(bi_datasource.tenant_id),
    )
    dashboard = await BiDashboard.create(
        name=dashboard_name,
        tenant_id=bi_datasource.tenant_id,
        layout={
            "items": [
                {"chartId": encode_id(chart.id), "x": 0, "y": 0, "w": 6, "h": 2}
            ]
        },
        created_by=str(bi_datasource.tenant_id),
        updated_by=str(bi_datasource.tenant_id),
    )
    return chart, dashboard


class TestRefreshDashboard:
    async def test_refresh_success(self, app, bi_datasource):
        """所有图表刷新成功。"""
        chart, dashboard = await _make_chart_and_dashboard(bi_datasource)

        async def fake_rerun(chart_obj, **kw):
            return {
                "columns": ["m", "s"],
                "rows": [["1", 100]],
                "rowCount": 1,
                "elapsedMs": 50,
            }

        with patch(
            "app.business.bi.services_dashboard._rerun_chart_sql",
            side_effect=fake_rerun,
        ):
            result = await refresh_dashboard(dashboard.id, bi_datasource.tenant_id)

        assert result["items"][0]["status"] == "success"
        assert result["items"][0]["resultSnapshot"]["rowCount"] == 1
        assert result["items"][0]["chartMeta"]["name"] == "测试图表"
        assert result["items"][0]["snapshotAt"] is not None
        assert result["totalElapsedMs"] >= 0

    async def test_refresh_failed_no_snapshot(self, app, bi_datasource):
        """刷新失败时不返回 resultSnapshot，但仍返回 chartMeta。"""
        chart, dashboard = await _make_chart_and_dashboard(
            bi_datasource, chart_name="失败图表"
        )

        async def failing_rerun(chart_obj, **kw):
            raise Exception("数据源连接超时")

        with patch(
            "app.business.bi.services_dashboard._rerun_chart_sql",
            side_effect=failing_rerun,
        ):
            result = await refresh_dashboard(dashboard.id, bi_datasource.tenant_id)

        assert result["items"][0]["status"] == "failed"
        assert "数据源连接超时" in result["items"][0]["errorMessage"]
        assert "resultSnapshot" not in result["items"][0]
        assert result["items"][0]["chartMeta"]["name"] == "失败图表"

    async def test_refresh_deleted_chart(self, app, bi_datasource):
        """引用的图表已删除，返回 deleted 状态。"""
        dashboard = await BiDashboard.create(
            name="d3",
            tenant_id=bi_datasource.tenant_id,
            layout={
                "items": [
                    {
                        "chartId": encode_id(999999),
                        "x": 0,
                        "y": 0,
                        "w": 6,
                        "h": 2,
                    }
                ]
            },
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )

        result = await refresh_dashboard(dashboard.id, bi_datasource.tenant_id)
        assert result["items"][0]["status"] == "deleted"
        assert result["items"][0]["chartMeta"] is None

    async def test_refresh_dashboard_not_found(self, app, bi_datasource):
        """仪表盘不存在抛 BI_DASHBOARD_NOT_FOUND。"""
        with pytest.raises(BizError) as exc_info:
            await refresh_dashboard(999999, bi_datasource.tenant_id)
        assert str(exc_info.value.code) == Code.BI_DASHBOARD_NOT_FOUND


# ===================== preview_dashboard =====================


class TestPreviewDashboard:
    async def test_preview_returns_snapshot(self, app, bi_datasource):
        """预览返回 BiChart 已有快照，不重跑。"""
        snapshot = {"columns": ["a"], "rows": [[1]], "rowCount": 1, "elapsedMs": 10}
        chart = await BiChart.create(
            name="c1",
            datasource_id=bi_datasource.id,
            chart_type="line",
            x_col="a",
            y_col="b",
            sql_text="SELECT a, b FROM t",
            result_snapshot=snapshot,
            snapshot_at=datetime.now(),
            tenant_id=bi_datasource.tenant_id,
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )
        dashboard = await BiDashboard.create(
            name="d4",
            tenant_id=bi_datasource.tenant_id,
            layout={
                "items": [
                    {"chartId": encode_id(chart.id), "x": 0, "y": 0, "w": 12, "h": 3}
                ]
            },
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )

        result = await preview_dashboard(dashboard.id, bi_datasource.tenant_id)
        assert result["items"][0]["resultSnapshot"] == snapshot
        assert result["items"][0]["chartMeta"]["chartType"] == "line"
        assert result["name"] == "d4"

    async def test_preview_deleted_chart(self, app, bi_datasource):
        """预览时引用的图表已删，返回 deleted 状态。"""
        dashboard = await BiDashboard.create(
            name="d5",
            tenant_id=bi_datasource.tenant_id,
            layout={
                "items": [
                    {
                        "chartId": encode_id(999999),
                        "x": 0,
                        "y": 0,
                        "w": 6,
                        "h": 2,
                    }
                ]
            },
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )
        result = await preview_dashboard(dashboard.id, bi_datasource.tenant_id)
        assert result["items"][0]["status"] == "deleted"
        assert result["items"][0]["chartMeta"] is None


# ===================== CRUD 服务 =====================


class TestDashboardCRUDService:
    async def test_create_and_get(self, app, bi_datasource):
        """create_dashboard + get_dashboard。"""
        chart = await BiChart.create(
            name="c1",
            datasource_id=bi_datasource.id,
            chart_type="bar",
            x_col="m",
            y_col="s",
            sql_text="SELECT 1",
            result_snapshot={"columns": [], "rows": [], "rowCount": 0, "elapsedMs": 0},
            snapshot_at=datetime.now(),
            tenant_id=bi_datasource.tenant_id,
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )
        schema = BiDashboardCreateSchema(
            name="经营日报",
            description="每月更新",
            layout=DashboardLayoutSchema(
                items=[
                    DashboardItemSchema(
                        chartId=encode_id(chart.id), x=0, y=0, w=6, h=2
                    )
                ]
            ),
        )
        dashboard = await create_dashboard(
            schema, tenant_id=bi_datasource.tenant_id, user_id=bi_datasource.tenant_id
        )
        assert dashboard.id > 0
        assert dashboard.name == "经营日报"
        assert len(dashboard.layout["items"]) == 1

        fetched = await refresh_dashboard_get(dashboard.id, bi_datasource.tenant_id)
        assert fetched.id == dashboard.id

    async def test_update_dashboard(self, app, bi_datasource):
        """update_dashboard 修改名称。"""
        chart, dashboard = await _make_chart_and_dashboard(bi_datasource)
        update_schema = BiDashboardUpdateSchema(name="新名称")
        updated = await update_dashboard(
            dashboard.id,
            update_schema,
            tenant_id=bi_datasource.tenant_id,
            user_id=bi_datasource.tenant_id,
        )
        assert updated.name == "新名称"

    async def test_delete_dashboard(self, app, bi_datasource):
        """delete_dashboard 软删。"""
        _, dashboard = await _make_chart_and_dashboard(bi_datasource)
        await delete_dashboard(dashboard.id, bi_datasource.tenant_id)
        # 软删后 get_or_none 返回 None
        from app.business.bi.models import BiDashboard as BD

        assert await BD.get_or_none(
            id=dashboard.id,
            tenant_id=bi_datasource.tenant_id,
            deleted_at__isnull=True,
        ) is None


async def refresh_dashboard_get(dashboard_id, tenant_id):
    """工具：直接用 get_dashboard 取详情（避免与 refresh_dashboard 重名）。"""
    from app.business.bi.services_dashboard import get_dashboard

    return await get_dashboard(dashboard_id, tenant_id)


# ===================== API 鉴权 =====================


from httpx import AsyncClient  # noqa: E402


class TestDashboardAPIAuth:
    async def test_search_requires_auth(self, app, client: AsyncClient):
        """未登录访问 /dashboards/search 返回 2100。"""
        resp = await client.post(
            f"{PREFIX}/dashboards/search", json={"current": 1, "size": 10}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == Code.INVALID_TOKEN

    async def test_create_requires_auth(self, app, client: AsyncClient):
        resp = await client.post(f"{PREFIX}/dashboards", json={"name": "d"})
        assert resp.json()["code"] == Code.INVALID_TOKEN

    async def test_refresh_requires_auth(self, app, client: AsyncClient):
        resp = await client.post(f"{PREFIX}/dashboards/abc/refresh")
        assert resp.json()["code"] == Code.INVALID_TOKEN

    async def test_preview_requires_auth(self, app, client: AsyncClient):
        resp = await client.get(f"{PREFIX}/dashboards/abc/preview")
        assert resp.json()["code"] == Code.INVALID_TOKEN


class TestDashboardAPICRUD:
    """登录态下走通 CRUD + refresh + preview 路径。"""

    async def test_full_lifecycle(self, app, auth_client: AsyncClient, bi_datasource):
        """创建 → 列表 → 详情 → 更新 → 预览 → 刷新 → 删除。"""
        # 1. 创建（空 layout）
        resp = await auth_client.post(
            f"{PREFIX}/dashboards",
            json={"name": "经营日报", "description": "测试", "layout": {"items": []}},
        )
        body = resp.json()
        assert body["code"] == Code.SUCCESS, body
        dashboard_id = body["data"]["createdId"]

        # 2. 列表
        resp = await auth_client.post(
            f"{PREFIX}/dashboards/search", json={"current": 1, "size": 10}
        )
        body = resp.json()
        assert body["code"] == Code.SUCCESS
        assert any(r["id"] == dashboard_id for r in body["data"]["records"])

        # 3. 详情
        resp = await auth_client.get(f"{PREFIX}/dashboards/{dashboard_id}")
        body = resp.json()
        assert body["code"] == Code.SUCCESS
        assert body["data"]["name"] == "经营日报"
        assert body["data"]["layout"] == {"items": []}

        # 4. 更新
        resp = await auth_client.put(
            f"{PREFIX}/dashboards/{dashboard_id}",
            json={"name": "经营周报"},
        )
        body = resp.json()
        assert body["code"] == Code.SUCCESS

        # 5. 预览（空 layout，items 应为 []）
        resp = await auth_client.get(f"{PREFIX}/dashboards/{dashboard_id}/preview")
        body = resp.json()
        assert body["code"] == Code.SUCCESS
        assert body["data"]["items"] == []

        # 6. 刷新（空 layout）
        resp = await auth_client.post(f"{PREFIX}/dashboards/{dashboard_id}/refresh")
        body = resp.json()
        assert body["code"] == Code.SUCCESS
        assert body["data"]["items"] == []

        # 7. 删除
        resp = await auth_client.delete(f"{PREFIX}/dashboards/{dashboard_id}")
        body = resp.json()
        assert body["code"] == Code.SUCCESS

        # 8. 删除后再查详情应失败
        resp = await auth_client.get(f"{PREFIX}/dashboards/{dashboard_id}")
        body = resp.json()
        assert body["code"] == Code.BI_DASHBOARD_NOT_FOUND
