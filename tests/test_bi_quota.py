"""BiQuotaConfig 服务测试。"""
from __future__ import annotations

import pytest

from app.business.bi.models import BiQuotaConfig
from app.business.bi.services_quota import (
    invalidate_quota_cache,
    load_quota_config,
)
from app.utils import StatusType

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(autouse=True)
async def _cleanup_quota_configs(app):
    """每个测试前后清理 BiQuotaConfig 表 + 缓存。"""
    from app.business.bi.async_query import state

    state.set_runtime_redis(app.state.redis)
    await BiQuotaConfig.all().delete()
    await invalidate_quota_cache()
    yield
    await BiQuotaConfig.all().delete()
    await invalidate_quota_cache()


class TestLoadQuotaConfig:
    async def test_global_fallback(self, app):
        """无 user/datasource 配置时回退 global。"""
        await BiQuotaConfig.create(
            name="global",
            max_rows=5000,
            timeout_seconds=20,
            breaker_threshold=5,
            breaker_window_seconds=60,
            scope_type="global",
            scope_id=None,
            status_type=StatusType.enable,
            created_by="1",
            updated_by="1",
        )
        cfg = await load_quota_config("user", 999)
        assert cfg.max_rows == 5000
        assert cfg.timeout_seconds == 20

    async def test_user_overrides_global(self, app):
        """user 配置优先于 global。"""
        await BiQuotaConfig.create(
            name="global",
            max_rows=5000,
            timeout_seconds=20,
            breaker_threshold=5,
            breaker_window_seconds=60,
            scope_type="global",
            scope_id=None,
            status_type=StatusType.enable,
            created_by="1",
            updated_by="1",
        )
        await BiQuotaConfig.create(
            name="user-1",
            max_rows=100,
            timeout_seconds=10,
            breaker_threshold=3,
            breaker_window_seconds=30,
            scope_type="user",
            scope_id=1,
            status_type=StatusType.enable,
            created_by="1",
            updated_by="1",
        )
        cfg = await load_quota_config("user", 1)
        assert cfg.max_rows == 100
        assert cfg.timeout_seconds == 10

    async def test_datasource_overrides_user(self, app):
        """datasource 配置优先于 user。"""
        await BiQuotaConfig.create(
            name="global",
            max_rows=5000,
            timeout_seconds=20,
            breaker_threshold=5,
            breaker_window_seconds=60,
            scope_type="global",
            scope_id=None,
            status_type=StatusType.enable,
            created_by="1",
            updated_by="1",
        )
        await BiQuotaConfig.create(
            name="user-1",
            max_rows=100,
            timeout_seconds=10,
            breaker_threshold=3,
            breaker_window_seconds=30,
            scope_type="user",
            scope_id=1,
            status_type=StatusType.enable,
            created_by="1",
            updated_by="1",
        )
        await BiQuotaConfig.create(
            name="ds-1",
            max_rows=50,
            timeout_seconds=5,
            breaker_threshold=2,
            breaker_window_seconds=15,
            scope_type="datasource",
            scope_id=1,
            status_type=StatusType.enable,
            created_by="1",
            updated_by="1",
        )
        cfg = await load_quota_config("datasource", 1, user_id=1)
        assert cfg.max_rows == 50

    async def test_no_config_returns_default(self, app):
        """无任何配置时返回 env 默认值。"""
        cfg = await load_quota_config("user", 999)
        # env 默认值：BI_QUERY_MAX_ROWS=10000, BI_QUERY_TIMEOUT=30
        assert cfg.max_rows == 10000
        assert cfg.timeout_seconds == 30

    async def test_disabled_config_skipped(self, app):
        """禁用的配置被跳过。"""
        await BiQuotaConfig.create(
            name="global-disabled",
            max_rows=100,
            timeout_seconds=5,
            breaker_threshold=1,
            breaker_window_seconds=10,
            scope_type="global",
            scope_id=None,
            status_type=StatusType.disable,
            created_by="1",
            updated_by="1",
        )
        cfg = await load_quota_config("user", 1)
        # 应回退 env 默认
        assert cfg.max_rows == 10000


PREFIX = "/api/v1/business/bi"


class TestQuotaAPIAuth:
    async def test_search_requires_auth(self, app, client):
        resp = await client.post(f"{PREFIX}/quota/search", json={"current": 1, "size": 10})
        assert resp.status_code == 200
        assert resp.json()["code"] == 2100

    async def test_create_requires_auth(self, app, client):
        resp = await client.post(
            f"{PREFIX}/quota",
            json={"name": "q1", "scope_type": "global", "max_rows": 10000},
        )
        assert resp.json()["code"] == 2100
