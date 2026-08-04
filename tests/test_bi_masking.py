"""BiMaskingRule 服务测试。"""
from __future__ import annotations

import pytest

from app.business.bi.models import BiMaskingRule
from app.business.bi.services_masking import (
    apply_masking,
    invalidate_masking_cache,
    load_masking_rules,
)
from app.utils import StatusType

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(autouse=True)
async def _cleanup_masking_rules(app):
    """每个测试前后清理 BiMaskingRule 表 + 缓存，避免跨测试污染。"""
    from app.business.bi.async_query import state
    from app.business.bi.services_masking import invalidate_masking_cache

    state.set_runtime_redis(app.state.redis)
    await BiMaskingRule.all().delete()
    await invalidate_masking_cache()
    yield
    await BiMaskingRule.all().delete()
    await invalidate_masking_cache()


class TestLoadMaskingRules:
    async def test_returns_only_enabled_rules(self, app):
        """只返回 status_type=enable 的规则。"""
        await BiMaskingRule.create(
            name="phone",
            column_pattern=r"phone$",
            mask_type="phone",
            mask_char="*",
            keep_prefix=3,
            keep_suffix=4,
            status_type=StatusType.enable,
            created_by="1",
            updated_by="1",
        )
        await BiMaskingRule.create(
            name="disabled",
            column_pattern=r"email$",
            mask_type="email",
            status_type=StatusType.disable,
            created_by="1",
            updated_by="1",
        )
        rules = await load_masking_rules()
        assert len(rules) == 1
        assert rules[0].name == "phone"

    async def test_cache_hit(self, app):
        """第二次调用命中缓存，不查 DB。"""
        await BiMaskingRule.create(
            name="phone",
            column_pattern=r"phone$",
            mask_type="phone",
            status_type=StatusType.enable,
            created_by="1",
            updated_by="1",
        )
        rules1 = await load_masking_rules()
        # 再创建一条，但缓存未失效，应仍只返回 1 条
        await BiMaskingRule.create(
            name="idcard",
            column_pattern=r"id_card$",
            mask_type="idcard",
            status_type=StatusType.enable,
            created_by="1",
            updated_by="1",
        )
        rules2 = await load_masking_rules()
        assert len(rules2) == len(rules1)

    async def test_invalidate_clears_cache(self, app):
        """invalidate 后重新从 DB 读。"""
        await BiMaskingRule.create(
            name="phone",
            column_pattern=r"phone$",
            mask_type="phone",
            status_type=StatusType.enable,
            created_by="1",
            updated_by="1",
        )
        await load_masking_rules()  # 填充缓存
        await BiMaskingRule.create(
            name="idcard",
            column_pattern=r"id_card$",
            mask_type="idcard",
            status_type=StatusType.enable,
            created_by="1",
            updated_by="1",
        )
        await invalidate_masking_cache()
        rules = await load_masking_rules()
        assert len(rules) == 2


class TestApplyMasking:
    async def test_masks_phone_column(self, app):
        """phone 列被脱敏。"""
        await BiMaskingRule.create(
            name="phone",
            column_pattern=r"phone$",
            mask_type="phone",
            mask_char="*",
            keep_prefix=3,
            keep_suffix=4,
            status_type=StatusType.enable,
            created_by="1",
            updated_by="1",
        )
        rows = [{"phone": "13800138000", "name": "Alice"}]
        masked = await apply_masking(rows)
        assert masked[0]["phone"] == "138****8000"
        assert masked[0]["name"] == "Alice"

    async def test_no_rules_returns_unchanged(self, app):
        """无规则时返回原 rows。"""
        rows = [{"phone": "13800138000"}]
        masked = await apply_masking(rows)
        assert masked[0]["phone"] == "13800138000"

    async def test_empty_rows(self, app):
        """空 rows 直接返回。"""
        assert await apply_masking([]) == []


PREFIX = "/api/v1/business/bi"


class TestMaskingAPIAuth:
    async def test_search_requires_auth(self, app, client):
        """未登录访问 /masking/search 返回 2100。"""
        resp = await client.post(f"{PREFIX}/masking/search", json={"current": 1, "size": 10})
        assert resp.status_code == 200
        assert str(resp.json()["code"]) == "2100"

    async def test_create_requires_auth(self, app, client):
        resp = await client.post(
            f"{PREFIX}/masking",
            json={"name": "r1", "column_pattern": "phone", "mask_type": "phone"},
        )
        assert str(resp.json()["code"]) == "2100"
