"""BiChart 业务服务与 API 测试。

覆盖：
- ``services_chart.create_chart`` —— 数据源归属校验 / SQL 白名单 / 结果截断
- ``services_chart.enable_share`` / ``disable_share`` / ``get_shared_chart_by_token``
- ``services_chart.get_all_tags`` —— 多租户隔离 / 去重
- ``services_chart.refresh_chart`` —— 数据源不可用降级（mock ``test_connection``）
- ``_truncate_snapshot`` —— 行数截断边界
- API 鉴权：未登录访问受保护端点 / 公开分享端点

设计约束：
- 服务层测试直接调用 ``services_chart`` 函数，不走 HTTP，避免 sandbox 真连数据库
- ``refresh_chart`` 涉及真实 SQL 执行，用 monkeypatch 替换 ``test_connection`` / ``execute_sql``
- BiChart.tenant_id 在 BI 模块里语义为 ``user.id``（行级 scope_id 就是 user.id），与
  现有 chat session 一致
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.business.bi.services_chart import (
    _truncate_snapshot,
    create_chart,
    disable_share,
    enable_share,
    get_all_tags,
    get_shared_chart_by_token,
    refresh_chart,
)
from app.core.code import Code
from app.core.exceptions import BizError
from app.core.sqids import encode_id

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(autouse=True)
async def _setup_runtime_redis(app):
    """注入 runtime redis（refresh_chart 经 apply_masking 需要 get_runtime_redis）。"""
    from app.business.bi.async_query import state

    state.set_runtime_redis(app.state.redis)
    yield


PREFIX = "/api/v1/business/bi"


# ===================== Helpers =====================


def _create_schema(datasource_id: str, **overrides):
    """构造 BiChartCreateSchema-like 对象（避免直接 import schema 类耦合细节）。"""
    from app.business.bi.schemas import BiChartCreateSchema

    payload = {
        "name": "测试图表",
        "description": "由测试用例生成",
        "datasource_id": datasource_id,
        "chart_type": "bar",
        "x_col": "month",
        "y_col": "sales",
        "sql_text": "SELECT month, sales FROM orders LIMIT 100",
        "result_snapshot": {
            "columns": ["month", "sales"],
            "rows": [
                {"month": "2026-01", "sales": 100},
                {"month": "2026-02", "sales": 200},
            ],
            "rowCount": 2,
            "elapsedMs": 12,
        },
        "tags": "销售,月报",
        "snapshot_at": datetime.now(UTC),
    }
    payload.update(overrides)
    return BiChartCreateSchema(**payload)


# ===================== create_chart =====================


class TestCreateChart:
    async def test_create_chart_success(self, bi_datasource):
        user_id = bi_datasource.tenant_id
        schema = _create_schema(datasource_id=encode_id(bi_datasource.id))
        chart = await create_chart(schema, tenant_id=user_id, user_id=user_id)

        assert chart.id > 0
        assert chart.name == "测试图表"
        assert chart.datasource_id == bi_datasource.id
        assert chart.tenant_id == user_id
        assert chart.created_by == str(user_id)
        assert chart.is_public is False
        assert chart.share_token is None

    async def test_create_chart_datasource_not_found(self, bi_datasource):
        user_id = bi_datasource.tenant_id
        # 用一个不存在的 sqid（decode_id 失败会抛 ValueError，但传入一个合法但不存在的 sqid）
        schema = _create_schema(datasource_id=encode_id(999_999_999))

        with pytest.raises(BizError) as exc:
            await create_chart(schema, tenant_id=user_id, user_id=user_id)
        assert exc.value.code == Code.NOT_FOUND

    async def test_create_chart_datasource_tenant_mismatch(self, bi_datasource):
        """数据源属于其他租户时拒绝创建（行级隔离）。"""
        schema = _create_schema(datasource_id=encode_id(bi_datasource.id))

        with pytest.raises(BizError) as exc:
            await create_chart(schema, tenant_id=bi_datasource.tenant_id + 1, user_id=bi_datasource.tenant_id + 1)
        assert exc.value.code == Code.NOT_FOUND

    async def test_create_chart_invalid_sql_rejected(self, bi_datasource):
        """写操作 SQL 被白名单拒绝，保存失败。"""
        user_id = bi_datasource.tenant_id
        schema = _create_schema(
            datasource_id=encode_id(bi_datasource.id),
            sql_text="DELETE FROM orders WHERE 1=1",
        )

        with pytest.raises(BizError) as exc:
            await create_chart(schema, tenant_id=user_id, user_id=user_id)
        # 白名单错误码 4101（whitelist 模块用 int，Code 类用 str，统一转 str 比较）
        assert str(exc.value.code) == "4101"

    async def test_create_chart_truncates_large_snapshot(self, bi_datasource, monkeypatch):
        """结果快照超过 BI_CHART_SNAPSHOT_MAX_ROWS 时被截断并标记 isTruncated。"""
        from app.business.bi import services_chart

        # 把阈值改小，便于测试
        monkeypatch.setattr(services_chart.BIZ_SETTINGS, "BI_CHART_SNAPSHOT_MAX_ROWS", 3)

        big_rows = [{"month": f"2026-{i:02d}", "sales": i} for i in range(1, 11)]
        schema = _create_schema(
            datasource_id=encode_id(bi_datasource.id),
            result_snapshot={
                "columns": ["month", "sales"],
                "rows": big_rows,
                "rowCount": len(big_rows),
                "elapsedMs": 5,
            },
        )

        chart = await create_chart(schema, tenant_id=bi_datasource.tenant_id, user_id=bi_datasource.tenant_id)
        snapshot = chart.result_snapshot
        assert snapshot["isTruncated"] is True
        assert len(snapshot["rows"]) == 3
        assert snapshot["rowCount"] == 3


# ===================== Share Management =====================


class TestShareManagement:
    async def test_enable_share_returns_token(self, bi_datasource):
        user_id = bi_datasource.tenant_id
        chart = await create_chart(
            _create_schema(datasource_id=encode_id(bi_datasource.id)),
            tenant_id=user_id,
            user_id=user_id,
        )

        token = await enable_share(chart.id, tenant_id=user_id)
        assert token is not None
        assert token == encode_id(chart.id)

        # DB 状态：is_public=True, share_token 已写入
        await chart.refresh_from_db()
        assert chart.is_public is True
        assert chart.share_token == token

    async def test_enable_share_idempotent(self, bi_datasource):
        """重复开启分享不应更换 token。"""
        user_id = bi_datasource.tenant_id
        chart = await create_chart(
            _create_schema(datasource_id=encode_id(bi_datasource.id)),
            tenant_id=user_id,
            user_id=user_id,
        )

        t1 = await enable_share(chart.id, tenant_id=user_id)
        t2 = await enable_share(chart.id, tenant_id=user_id)
        assert t1 == t2

    async def test_enable_share_chart_not_found(self, bi_datasource):
        with pytest.raises(BizError) as exc:
            await enable_share(999_999_999, tenant_id=bi_datasource.tenant_id)
        assert exc.value.code == Code.BI_CHART_NOT_FOUND

    async def test_disable_share_clears_token(self, bi_datasource):
        user_id = bi_datasource.tenant_id
        chart = await create_chart(
            _create_schema(datasource_id=encode_id(bi_datasource.id)),
            tenant_id=user_id,
            user_id=user_id,
        )
        await enable_share(chart.id, tenant_id=user_id)

        await disable_share(chart.id, tenant_id=user_id)

        await chart.refresh_from_db()
        assert chart.is_public is False
        assert chart.share_token is None

    async def test_disable_share_chart_not_found(self, bi_datasource):
        with pytest.raises(BizError) as exc:
            await disable_share(999_999_999, tenant_id=bi_datasource.tenant_id)
        assert exc.value.code == Code.BI_CHART_NOT_FOUND

    async def test_get_shared_chart_by_token_valid(self, bi_datasource):
        user_id = bi_datasource.tenant_id
        chart = await create_chart(
            _create_schema(datasource_id=encode_id(bi_datasource.id)),
            tenant_id=user_id,
            user_id=user_id,
        )
        token = await enable_share(chart.id, tenant_id=user_id)

        shared = await get_shared_chart_by_token(token)
        assert shared.id == chart.id
        assert shared.is_public is True

    async def test_get_shared_chart_by_token_invalid(self):
        with pytest.raises(BizError) as exc:
            await get_shared_chart_by_token("invalid_token")
        assert exc.value.code == Code.NOT_FOUND

    async def test_get_shared_chart_by_token_when_disabled(self, bi_datasource):
        user_id = bi_datasource.tenant_id
        chart = await create_chart(
            _create_schema(datasource_id=encode_id(bi_datasource.id)),
            tenant_id=user_id,
            user_id=user_id,
        )
        token = await enable_share(chart.id, tenant_id=user_id)
        await disable_share(chart.id, tenant_id=user_id)

        with pytest.raises(BizError) as exc:
            await get_shared_chart_by_token(token)
        assert exc.value.code == Code.NOT_FOUND

    async def test_get_shared_chart_by_token_when_deleted(self, bi_datasource):
        user_id = bi_datasource.tenant_id
        chart = await create_chart(
            _create_schema(datasource_id=encode_id(bi_datasource.id)),
            tenant_id=user_id,
            user_id=user_id,
        )
        token = await enable_share(chart.id, tenant_id=user_id)
        await chart.delete()  # 软删

        with pytest.raises(BizError) as exc:
            await get_shared_chart_by_token(token)
        assert exc.value.code == Code.NOT_FOUND


# ===================== get_all_tags =====================


class TestGetAllTags:
    async def test_get_all_tags_dedupes(self, bi_datasource):
        user_id = bi_datasource.tenant_id
        for tags in ["销售,月报", "销售,周报", "库存"]:
            await create_chart(
                _create_schema(
                    datasource_id=encode_id(bi_datasource.id),
                    tags=tags,
                ),
                tenant_id=user_id,
                user_id=user_id,
            )

        tags = await get_all_tags(tenant_id=user_id)
        # sorted by Unicode codepoint: 周 < 库 < 月 < 销
        assert tags == ["周报", "库存", "月报", "销售"]

    async def test_get_all_tags_excludes_other_tenants(self, bi_datasource):
        """其他租户的图表标签不应混入当前租户。"""
        user_id = bi_datasource.tenant_id
        other_tenant = user_id + 100

        # 创建当前用户的图表
        await create_chart(
            _create_schema(
                datasource_id=encode_id(bi_datasource.id),
                tags="销售",
            ),
            tenant_id=user_id,
            user_id=user_id,
        )
        # 创建其他租户的图表（直接写库，绕过 service 层的租户校验）
        from app.business.bi.models import BiChart

        await BiChart.create(
            name="其他租户图表",
            datasource_id=bi_datasource.id,
            chart_type="bar",
            sql_text="SELECT 1",
            result_snapshot={"columns": [], "rows": [], "rowCount": 0},
            tags="机密",
            snapshot_at=datetime.now(UTC),
            tenant_id=other_tenant,
            created_by=str(other_tenant),
            updated_by=str(other_tenant),
        )

        tags = await get_all_tags(tenant_id=user_id)
        assert tags == ["销售"]
        assert "机密" not in tags

    async def test_get_all_tags_empty(self, bi_datasource):
        tags = await get_all_tags(tenant_id=bi_datasource.tenant_id)
        assert tags == []


# ===================== refresh_chart =====================


class TestRefreshChart:
    async def test_refresh_chart_not_found(self, bi_datasource):
        with pytest.raises(BizError) as exc:
            await refresh_chart(999_999_999, tenant_id=bi_datasource.tenant_id, user_id=bi_datasource.tenant_id)
        assert exc.value.code == Code.BI_CHART_NOT_FOUND

    async def test_refresh_chart_datasource_unavailable(self, bi_datasource, monkeypatch):
        """数据源不可用时抛 BI_DATASOURCE_UNAVAILABLE，前端降级显示快照。"""
        user_id = bi_datasource.tenant_id
        chart = await create_chart(
            _create_schema(datasource_id=encode_id(bi_datasource.id)),
            tenant_id=user_id,
            user_id=user_id,
        )

        async def _fake_test_connection(datasource):
            return False, "连接失败: mock", 5

        monkeypatch.setattr("app.business.bi.services_chart.test_connection", _fake_test_connection)

        with pytest.raises(BizError) as exc:
            await refresh_chart(chart.id, tenant_id=user_id, user_id=user_id)
        assert exc.value.code == Code.BI_DATASOURCE_UNAVAILABLE

    async def test_refresh_chart_success_overwrites_snapshot(self, bi_datasource, monkeypatch):
        """数据源可用时重跑 SQL 并覆盖快照。"""
        user_id = bi_datasource.tenant_id
        chart = await create_chart(
            _create_schema(datasource_id=encode_id(bi_datasource.id)),
            tenant_id=user_id,
            user_id=user_id,
        )
        original_snapshot = chart.result_snapshot

        async def _fake_test_connection(datasource):
            return True, "连接成功", 3

        def _fake_validate_sql(sql, dialect="sqlite"):
            return SimpleNamespace(sql=sql, is_valid=True, error=None, warnings=[])

        async def _fake_execute_sql(*, sql, datasource, user_id, timeout=None, max_rows=None):
            return SimpleNamespace(
                columns=["month", "sales"],
                rows=[{"month": "2026-03", "sales": 300}],
                row_count=1,
                elapsed_ms=8,
            )

        monkeypatch.setattr("app.business.bi.services_chart.test_connection", _fake_test_connection)
        monkeypatch.setattr("app.business.bi.services_chart.validate_sql", _fake_validate_sql)
        monkeypatch.setattr("app.business.bi.services_chart.execute_sql", _fake_execute_sql)

        refreshed = await refresh_chart(chart.id, tenant_id=user_id, user_id=user_id)
        assert refreshed.result_snapshot != original_snapshot
        assert refreshed.result_snapshot["rows"] == [{"month": "2026-03", "sales": 300}]
        assert refreshed.result_snapshot["rowCount"] == 1


# ===================== _truncate_snapshot (unit) =====================


class TestTruncateSnapshot:
    def test_under_limit_returns_unchanged(self):
        snapshot = {"columns": ["a"], "rows": [{"a": 1}, {"a": 2}], "rowCount": 2}
        result = _truncate_snapshot(snapshot, max_rows=10)
        assert result is snapshot  # 同一对象
        assert "isTruncated" not in result

    def test_over_limit_truncates_and_marks(self):
        rows = [{"a": i} for i in range(10)]
        snapshot = {"columns": ["a"], "rows": rows, "rowCount": 10}
        result = _truncate_snapshot(snapshot, max_rows=3)
        assert len(result["rows"]) == 3
        assert result["rowCount"] == 3
        assert result["isTruncated"] is True

    def test_empty_rows(self):
        snapshot = {"columns": [], "rows": [], "rowCount": 0}
        result = _truncate_snapshot(snapshot, max_rows=10)
        assert result is snapshot

    def test_preserves_extra_keys(self):
        snapshot = {"columns": ["a"], "rows": [{"a": 1}], "rowCount": 1, "elapsedMs": 5, "custom": "keep"}
        result = _truncate_snapshot(snapshot, max_rows=10)
        assert result.get("elapsedMs") == 5
        assert result.get("custom") == "keep"


# ===================== API Auth =====================


class TestBiChartAPIAuth:
    async def test_create_chart_no_auth(self, client: AsyncClient):
        resp = await client.post(f"{PREFIX}/charts", json={})
        assert resp.status_code == 200
        assert resp.json()["code"] == Code.INVALID_TOKEN

    async def test_list_charts_no_auth(self, client: AsyncClient):
        resp = await client.post(f"{PREFIX}/charts/search", json={"current": 1, "size": 10})
        assert resp.status_code == 200
        assert resp.json()["code"] == Code.INVALID_TOKEN

    async def test_get_chart_no_auth(self, client: AsyncClient):
        resp = await client.get(f"{PREFIX}/charts/abc")
        assert resp.status_code == 200
        assert resp.json()["code"] == Code.INVALID_TOKEN

    async def test_tags_endpoint_no_auth(self, client: AsyncClient):
        resp = await client.get(f"{PREFIX}/charts/tags")
        assert resp.status_code == 200
        assert resp.json()["code"] == Code.INVALID_TOKEN

    async def test_share_endpoint_public_no_auth_required(self, client: AsyncClient):
        """免登录分享端点不应返回 INVALID_TOKEN（token 无效返回业务错误）。"""
        resp = await client.get(f"{PREFIX}/charts/shared/invalid_token")
        # 公开端点：即使 token 无效也返回 200 + 业务错误码，而非 INVALID_TOKEN
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] != "0000"
        assert body["code"] != Code.INVALID_TOKEN

    async def test_create_chart_via_api(self, auth_client: AsyncClient, bi_datasource):
        """通过 API 创建图表，验证路由与按钮权限集成正常。"""
        resp = await auth_client.post(
            f"{PREFIX}/charts",
            json={
                "name": "API 图表",
                "description": "via http",
                "datasource_id": encode_id(bi_datasource.id),
                "chart_type": "line",
                "x_col": "month",
                "y_col": "sales",
                "sql_text": "SELECT month, sales FROM orders LIMIT 100",
                "result_snapshot": {
                    "columns": ["month", "sales"],
                    "rows": [{"month": "2026-01", "sales": 100}],
                    "rowCount": 1,
                    "elapsedMs": 5,
                },
                "tags": "销售",
                "snapshot_at": datetime.now(UTC).isoformat(),
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0000"
        assert body["data"]["createdId"]

    async def test_list_charts_via_api(self, auth_client: AsyncClient, bi_datasource):
        """分页查询图表列表，返回当前用户的图表。"""
        # 先创建一个图表
        await auth_client.post(
            f"{PREFIX}/charts",
            json={
                "name": "List 测试",
                "datasource_id": encode_id(bi_datasource.id),
                "chart_type": "bar",
                "sql_text": "SELECT 1",
                "result_snapshot": {"columns": [], "rows": [], "rowCount": 0, "elapsedMs": 1},
                "snapshot_at": datetime.now(UTC).isoformat(),
            },
        )

        resp = await auth_client.post(f"{PREFIX}/charts/search", json={"current": 1, "size": 10})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0000"
        assert body["data"]["total"] >= 1
        assert any(c["name"] == "List 测试" for c in body["data"]["records"])

    async def test_share_lifecycle_via_api(self, auth_client: AsyncClient, bi_datasource, app):
        """开启分享 → 免登录查看 → 关闭分享 全流程。"""
        from httpx import ASGITransport, AsyncClient as _AC

        create_resp = await auth_client.post(
            f"{PREFIX}/charts",
            json={
                "name": "Share 测试",
                "datasource_id": encode_id(bi_datasource.id),
                "chart_type": "bar",
                "sql_text": "SELECT 1",
                "result_snapshot": {"columns": [], "rows": [], "rowCount": 0, "elapsedMs": 1},
                "snapshot_at": datetime.now(UTC).isoformat(),
            },
        )
        assert create_resp.status_code == 200
        assert create_resp.json()["code"] == "0000"
        chart_id = create_resp.json()["data"]["createdId"]

        # 开启分享
        enable_resp = await auth_client.post(f"{PREFIX}/charts/{chart_id}/share/enable")
        assert enable_resp.status_code == 200
        assert enable_resp.json()["code"] == "0000"
        token = enable_resp.json()["data"]["shareToken"]
        assert token

        # 免登录查看（不带 Authorization）—— 用 app fixture 创建独立 client
        async with _AC(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
            shared_resp = await ac.get(f"{PREFIX}/charts/shared/{token}")
            assert shared_resp.status_code == 200
            shared = shared_resp.json()
            assert shared["code"] == "0000"
            assert shared["data"]["name"] == "Share 测试"
            # sql_text 不应在分享响应里
            assert "sql_text" not in shared["data"]

        # 关闭分享后再查应失败
        await auth_client.post(f"{PREFIX}/charts/{chart_id}/share/disable")
        async with _AC(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
            shared_resp2 = await ac.get(f"{PREFIX}/charts/shared/{token}")
            assert shared_resp2.status_code == 200
            assert shared_resp2.json()["code"] != "0000"
