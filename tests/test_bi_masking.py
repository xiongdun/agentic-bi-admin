"""BiMaskingRule 服务测试。"""
from __future__ import annotations

import pytest

from app.business.bi.models import BiMaskingRule
from app.business.bi.services_masking import (
    apply_masking,
    invalidate_masking_cache,
    load_masking_rules,
)
from app.core.enums import StatusType

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestLoadMaskingRules:
    async def test_returns_only_enabled_rules(self, app):
        """只返回 status_type=enable 的规则。"""
        from app.business.bi.async_query import state

        state.set_runtime_redis(app.state.redis)
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
        await invalidate_masking_cache()
        rules = await load_masking_rules()
        assert len(rules) == 1
        assert rules[0].name == "phone"

    async def test_cache_hit(self, app):
        """第二次调用命中缓存，不查 DB。"""
        from app.business.bi.async_query import state

        state.set_runtime_redis(app.state.redis)
        await BiMaskingRule.create(
            name="phone",
            column_pattern=r"phone$",
            mask_type="phone",
            status_type=StatusType.enable,
            created_by="1",
            updated_by="1",
        )
        await invalidate_masking_cache()
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
        from app.business.bi.async_query import state

        state.set_runtime_redis(app.state.redis)
        await BiMaskingRule.create(
            name="phone",
            column_pattern=r"phone$",
            mask_type="phone",
            status_type=StatusType.enable,
            created_by="1",
            updated_by="1",
        )
        await invalidate_masking_cache()
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
        from app.business.bi.async_query import state

        state.set_runtime_redis(app.state.redis)
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
        await invalidate_masking_cache()
        rows = [{"phone": "13800138000", "name": "Alice"}]
        masked = await apply_masking(rows)
        assert masked[0]["phone"] == "138****8000"
        assert masked[0]["name"] == "Alice"

    async def test_no_rules_returns_unchanged(self, app):
        """无规则时返回原 rows。"""
        from app.business.bi.async_query import state

        state.set_runtime_redis(app.state.redis)
        await invalidate_masking_cache()
        rows = [{"phone": "13800138000"}]
        masked = await apply_masking(rows)
        assert masked[0]["phone"] == "13800138000"

    async def test_empty_rows(self, app):
        """空 rows 直接返回。"""
        from app.business.bi.async_query import state

        state.set_runtime_redis(app.state.redis)
        await invalidate_masking_cache()
        assert await apply_masking([]) == []
