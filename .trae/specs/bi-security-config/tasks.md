# BI 安全配置 实现计划 — Batch D-1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐 BiMaskingRule 与 BiQuotaConfig 的 CRUD API + 前端管理页，并接入 sandbox 执行链路让配置真正生效。

**Architecture:** 后端用 CRUDRouter 生成 6 路由（两模型各一套），新增 services_masking.py / services_quota.py 封装加载与缓存逻辑，在 executor_node / refresh_chart / execute_sql 三个接入点生效。前端仿 metrics 管理页模式。无新迁移。

**Tech Stack:** FastAPI + Tortoise ORM + Redis（后端）；Vue 3 + Naive UI + TypeScript（前端）

**Spec:** [.trae/specs/bi-security-config/spec.md](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/.trae/specs/bi-security-config/spec.md)

---

## 文件结构

### 后端新建/修改

| 文件 | 责任 | 动作 |
|------|------|------|
| `app/core/code.py` | 新增 4120/4121 + 登记 4102/4103/4104 | 修改 |
| `app/business/bi/config.py` | 缓存 TTL 配置项 | 修改 |
| `.env.example` | 缓存 TTL 配置 | 修改 |
| `app/business/bi/services_masking.py` | load_masking_rules + 缓存失效 | 新建 |
| `app/business/bi/services_quota.py` | load_quota_config + 缓存失效 | 新建 |
| `app/business/bi/sandbox/executor.py` | 接入 load_quota_config | 修改 |
| `app/business/bi/agent/nodes/executor.py` | 接入 mask_columns | 修改 |
| `app/business/bi/services_chart.py` | refresh_chart 接入 mask_columns | 修改 |
| `app/business/bi/api/masking.py` | 6 路由 CRUDRouter | 新建 |
| `app/business/bi/api/quota.py` | 6 路由 CRUDRouter | 新建 |
| `app/business/bi/api/__init__.py` | 挂载路由 | 修改 |
| `app/business/bi/init_data.py` | 菜单/按钮/角色权限 | 修改 |

### 前端新建/修改

| 文件 | 责任 | 动作 |
|------|------|------|
| `web/src/typings/api/bi.d.ts` | 补全类型 | 修改 |
| `web/src/service/api/bi-masking.ts` | API 服务 | 新建 |
| `web/src/service/api/bi-quota.ts` | API 服务 | 新建 |
| `web/src/views/bi/masking/index.vue` | 列表页 | 新建 |
| `web/src/views/bi/masking/modules/masking-operate-modal.vue` | 增改模态框 | 新建 |
| `web/src/views/bi/quota/index.vue` | 列表页 | 新建 |
| `web/src/views/bi/quota/modules/quota-operate-modal.vue` | 增改模态框 | 新建 |
| `web/src/locales/langs/_generated/bi/zh-cn.ts` | i18n | 修改 |
| `web/src/locales/langs/_generated/bi/en-us.ts` | i18n | 修改 |
| `web/src/locales/langs/_generated/bi/types.d.ts` | i18n 类型 | 修改 |
| `web/src/locales/langs/zh-cn.ts` | route 命名 | 修改 |
| `web/src/locales/langs/en-us.ts` | route 命名 | 修改 |

### 测试

| 文件 | 责任 | 动作 |
|------|------|------|
| `tests/test_bi_masking.py` | 后端脱敏测试 | 新建 |
| `tests/test_bi_quota.py` | 后端配额测试 | 新建 |
| `web/src/service/api/__tests__/bi-masking.test.ts` | 前端 API 测试 | 新建 |
| `web/src/service/api/__tests__/bi-quota.test.ts` | 前端 API 测试 | 新建 |

---

## Task 1: 配置项与错误码

**Files:**
- Modify: `app/business/bi/config.py`
- Modify: `.env.example`
- Modify: `app/core/code.py`

- [ ] **Step 1: 在 `app/business/bi/config.py` 末尾追加缓存 TTL 配置**

```python
    # ==================== Security Config ====================
    BI_MASKING_CACHE_TTL: int = 60  # 脱敏规则缓存 TTL（秒）
    BI_QUOTA_CACHE_TTL: int = 60    # 配额配置缓存 TTL（秒）
```

- [ ] **Step 2: 在 `.env.example` 的 BI 配置区块末尾追加**

```bash
# BI Security Config
BI_MASKING_CACHE_TTL=60              # 脱敏规则缓存 TTL（秒）
BI_QUOTA_CACHE_TTL=60                # 配额配置缓存 TTL（秒）
```

- [ ] **Step 3: 在 `app/core/code.py` 的 BI 错误码段追加**

> 先 Grep 找到 `BI_DASHBOARD_NOT_FOUND = 4202` 的位置，在其后追加。同时把 sandbox 硬编码的幽灵码登记进 41xx 段。

```python
    # 41xx — BI 安全配置
    BI_QUERY_BREAKER_OPEN = 4102      # 查询熔断（sandbox 已用，登记进 Code）
    BI_QUERY_ROW_LIMIT = 4103         # 行数超限（sandbox 已用，登记进 Code）
    BI_QUERY_EXEC_FAILED = 4104       # SQL 执行失败（sandbox 已用，登记进 Code）
    BI_MASKING_RULE_NOT_FOUND = 4120  # 脱敏规则不存在
    BI_QUOTA_CONFIG_NOT_FOUND = 4121  # 配额配置不存在
```

- [ ] **Step 4: 提交**

```bash
git add app/business/bi/config.py .env.example app/core/code.py
git commit -m "feat(bi): add security config and error codes (masking/quota)"
```

---

## Task 2: services_masking.py — 脱敏规则加载与缓存

**Files:**
- Create: `app/business/bi/services_masking.py`
- Test: `tests/test_bi_masking.py`

- [ ] **Step 1: 写 `load_masking_rules` 测试（先失败）**

创建 `tests/test_bi_masking.py`：

```python
"""BiMaskingRule 服务测试。"""
from __future__ import annotations

import pytest

from app.business.bi.models import BiMaskingRule
from app.business.bi.services_masking import (
    load_masking_rules,
    invalidate_masking_cache,
)
from app.core.enums import StatusType

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestLoadMaskingRules:
    async def test_returns_only_enabled_rules(self, app, monkeypatch):
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
        # 清缓存确保从 DB 读
        await invalidate_masking_cache()
        rules = await load_masking_rules()
        assert len(rules) == 1
        assert rules[0].name == "phone"

    async def test_cache_hit(self, app, monkeypatch):
        """第二次调用命中缓存，不查 DB。"""
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_bi_masking.py::TestLoadMaskingRules -v`
Expected: FAIL（`services_masking` 模块不存在）

- [ ] **Step 3: 创建 `services_masking.py`**

```python
"""BiMaskingRule 加载与缓存服务。"""
from __future__ import annotations

from app.business.bi.config import BIZ_SETTINGS
from app.business.bi.models import BiMaskingRule
from app.business.bi.sandbox.masking import mask_columns
from app.core.enums import StatusType
from app.utils import get_redis, log

_CACHE_KEY = "bi:masking:rules:enabled"


async def load_masking_rules() -> list[BiMaskingRule]:
    """加载所有启用的脱敏规则（带 Redis 缓存）。

    缓存 miss 时从 DB 查询并写回缓存；命中时直接返回。
    """
    redis = await get_redis()
    # 尝试读缓存
    cached = await redis.get(_CACHE_KEY)
    if cached is not None:
        import json
        try:
            data = json.loads(cached)
            # 重建 model 实例（不查 DB）
            return [BiMaskingRule(**item) for item in data]
        except Exception:
            log.warning("bi.masking.cache.parse_failed, fallback to DB")

    # 查 DB
    rules = await BiMaskingRule.filter(status_type=StatusType.enable).all()
    # 写缓存
    import json
    payload = json.dumps([
        {
            "id": r.id,
            "name": r.name,
            "column_pattern": r.column_pattern,
            "mask_type": r.mask_type,
            "mask_char": r.mask_char,
            "keep_prefix": r.keep_prefix,
            "keep_suffix": r.keep_suffix,
            "status_type": r.status_type,
        }
        for r in rules
    ])
    await redis.set(_CACHE_KEY, payload, ex=BIZ_SETTINGS.BI_MASKING_CACHE_TTL)
    return rules


async def invalidate_masking_cache() -> None:
    """失效脱敏规则缓存（CRUD 变更时调用）。"""
    redis = await get_redis()
    await redis.delete(_CACHE_KEY)
    log.info("bi.masking.cache.invalidated")


async def apply_masking(rows: list[dict]) -> list[dict]:
    """对查询结果应用脱敏规则（便捷封装）。

    无规则时直接返回原 rows（浅拷贝）。
    """
    if not rows:
        return rows
    rules = await load_masking_rules()
    if not rules:
        return rows
    return mask_columns(rows, rules)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_bi_masking.py::TestLoadMaskingRules -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add app/business/bi/services_masking.py tests/test_bi_masking.py
git commit -m "feat(bi): add services_masking with cache (load/invalidate/apply)"
```

---

## Task 3: services_quota.py — 配额配置加载与缓存

**Files:**
- Create: `app/business/bi/services_quota.py`
- Test: `tests/test_bi_quota.py`

- [ ] **Step 1: 写 `load_quota_config` 测试（先失败）**

创建 `tests/test_bi_quota.py`：

```python
"""BiQuotaConfig 服务测试。"""
from __future__ import annotations

import pytest

from app.business.bi.models import BiQuotaConfig
from app.business.bi.sandbox.quota import QuotaConfig
from app.business.bi.services_quota import (
    load_quota_config,
    invalidate_quota_cache,
)
from app.core.enums import StatusType

pytestmark = pytest.mark.asyncio(loop_scope="session")


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
        await invalidate_quota_cache()
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
        await invalidate_quota_cache()
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
        await invalidate_quota_cache()
        cfg = await load_quota_config("datasource", 1, user_id=1)
        assert cfg.max_rows == 50

    async def test_no_config_returns_default(self, app):
        """无任何配置时返回 env 默认值。"""
        await invalidate_quota_cache()
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
        await invalidate_quota_cache()
        cfg = await load_quota_config("user", 1)
        # 应回退 env 默认
        assert cfg.max_rows == 10000
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_bi_quota.py::TestLoadQuotaConfig -v`
Expected: FAIL（`services_quota` 模块不存在）

- [ ] **Step 3: 创建 `services_quota.py`**

```python
"""BiQuotaConfig 加载与缓存服务。"""
from __future__ import annotations

from app.business.bi.models import BiQuotaConfig
from app.business.bi.sandbox.quota import QuotaConfig, _default_config
from app.core.enums import StatusType
from app.utils import get_redis, log


def _cache_key(scope_type: str, scope_id: int | None) -> str:
    return f"bi:quota:config:{scope_type}:{scope_id}"


async def _load_one(scope_type: str, scope_id: int | None) -> BiQuotaConfig | None:
    """从 DB 查询单条启用配置。"""
    qs = BiQuotaConfig.filter(scope_type=scope_type, status_type=StatusType.enable)
    if scope_id is None:
        qs = qs.filter(scope_id__isnull=True)
    else:
        qs = qs.filter(scope_id=scope_id)
    return await qs.first()


async def load_quota_config(
    scope_type: str, scope_id: int | None, *, user_id: int | None = None
) -> QuotaConfig:
    """链式查找配额配置（datasource > user > global > env 默认）。

    Args:
        scope_type: 初始查找作用域（'datasource' 或 'user'）
        scope_id: 初始查找作用域 ID
        user_id: 用户 ID（datasource 查找失败时回退到 user 作用域用）
    Returns:
        QuotaConfig dataclass（sandbox 可直接使用）
    """
    redis = await get_redis()

    # 构建查找链
    chain: list[tuple[str, int | None]] = []
    if scope_type == "datasource" and scope_id is not None:
        chain.append(("datasource", scope_id))
    if user_id is not None:
        chain.append(("user", user_id))
    chain.append(("global", None))

    for st, sid in chain:
        key = _cache_key(st, sid)
        cached = await redis.get(key)
        if cached is not None:
            import json
            try:
                data = json.loads(cached)
                if data:  # 非空字典表示命中
                    return QuotaConfig(
                        max_rows=data["max_rows"],
                        timeout_seconds=data["timeout_seconds"],
                        breaker_threshold=data["breaker_threshold"],
                        breaker_window_seconds=data["breaker_window_seconds"],
                    )
                else:  # 空字典表示"已查过但无配置"，跳过
                    continue
            except Exception:
                log.warning("bi.quota.cache.parse_failed key={}", key)

        # 查 DB
        cfg = await _load_one(st, sid)
        if cfg:
            import json
            payload = json.dumps({
                "max_rows": cfg.max_rows,
                "timeout_seconds": cfg.timeout_seconds,
                "breaker_threshold": cfg.breaker_threshold,
                "breaker_window_seconds": cfg.breaker_window_seconds,
            })
            await redis.set(key, payload, ex=60)  # TTL 写死 60，避免循环依赖 BIZ_SETTINGS
            return QuotaConfig(
                max_rows=cfg.max_rows,
                timeout_seconds=cfg.timeout_seconds,
                breaker_threshold=cfg.breaker_threshold,
                breaker_window_seconds=cfg.breaker_window_seconds,
            )
        else:
            # 写空字典标记"已查无"，避免重复查 DB
            await redis.set(key, "{}", ex=60)

    # 全链路都没命中，回退 env 默认
    return _default_config


async def invalidate_quota_cache(scope_type: str | None = None, scope_id: int | None = None) -> None:
    """失效配额配置缓存。

    传参时只失效对应 key；不传参时清空所有 bi:quota:config:* 前缀。
    """
    redis = await get_redis()
    if scope_type is not None:
        await redis.delete(_cache_key(scope_type, scope_id))
    else:
        # 清所有配额缓存 key
        async for key in redis.scan_iter("bi:quota:config:*"):
            await redis.delete(key)
    log.info("bi.quota.cache.invalidated scope_type={} scope_id={}", scope_type, scope_id)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_bi_quota.py::TestLoadQuotaConfig -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add app/business/bi/services_quota.py tests/test_bi_quota.py
git commit -m "feat(bi): add services_quota with cache (load/invalidate, chain lookup)"
```

---

## Task 4: 接入 mask_columns 到 executor_node

**Files:**
- Modify: `app/business/bi/agent/nodes/executor.py`
- Test: `tests/test_bi_masking.py`

- [ ] **Step 1: 写 executor_node 脱敏测试**

在 `tests/test_bi_masking.py` 追加：

```python
from app.business.bi.services_masking import apply_masking


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
        await invalidate_masking_cache()
        rows = [{"phone": "13800138000", "name": "Alice"}]
        masked = await apply_masking(rows)
        assert masked[0]["phone"] == "138****8000"
        assert masked[0]["name"] == "Alice"

    async def test_no_rules_returns_unchanged(self, app):
        """无规则时返回原 rows。"""
        await invalidate_masking_cache()
        rows = [{"phone": "13800138000"}]
        masked = await apply_masking(rows)
        assert masked[0]["phone"] == "13800138000"

    async def test_empty_rows(self, app):
        """空 rows 直接返回。"""
        await invalidate_masking_cache()
        assert await apply_masking([]) == []
```

- [ ] **Step 2: 运行测试确认通过（apply_masking 已在 Task 2 实现）**

Run: `uv run pytest tests/test_bi_masking.py::TestApplyMasking -v`
Expected: PASS

- [ ] **Step 3: 在 `agent/nodes/executor.py` 的 executor_node 接入 apply_masking**

> 先 Read `agent/nodes/executor.py`，找到 SQL 执行成功后构造 result 的位置。在返回 rows 前调用 `apply_masking`。

```python
# 在 executor_node 函数内，SQL 执行成功后：
from app.business.bi.services_masking import apply_masking

# 原代码：
# result = {"columns": cols, "rows": raw_rows, "rowCount": len(raw_rows), "elapsedMs": ...}

# 改为：
masked_rows = await apply_masking(raw_rows)
result = {"columns": cols, "rows": masked_rows, "rowCount": len(masked_rows), "elapsedMs": ...}
```

- [ ] **Step 4: 跑现有 agent 测试确认无回归**

Run: `uv run pytest tests/test_bi_chat.py -v -k "executor or chat"`
Expected: PASS（脱敏对无规则场景无影响）

- [ ] **Step 5: 提交**

```bash
git add app/business/bi/agent/nodes/executor.py tests/test_bi_masking.py
git commit -m "feat(bi): apply masking in executor_node (chat path)"
```

---

## Task 5: 接入 mask_columns 到 refresh_chart

**Files:**
- Modify: `app/business/bi/services_chart.py`
- Test: `tests/test_bi_masking.py`

- [ ] **Step 1: 写 refresh_chart 脱敏测试**

在 `tests/test_bi_masking.py` 追加：

```python
from app.business.bi.models import BiChart, BiDatasource
from app.business.bi.services_chart import refresh_chart


class TestRefreshChartMasking:
    async def test_refresh_applies_masking(self, app, bi_datasource, monkeypatch):
        """refresh_chart 对结果快照应用脱敏。"""
        from datetime import datetime
        from unittest.mock import patch

        # 创建脱敏规则
        await BiMaskingRule.create(
            name="phone",
            column_pattern=r"phone$",
            mask_type="phone",
            keep_prefix=3,
            keep_suffix=4,
            status_type=StatusType.enable,
            created_by="1",
            updated_by="1",
        )
        await invalidate_masking_cache()

        chart = await BiChart.create(
            name="c1",
            datasource_id=bi_datasource.id,
            chart_type="bar",
            x_col="name",
            y_col="phone",
            sql_text="SELECT name, phone FROM users LIMIT 10",
            result_snapshot={"columns": [], "rows": [], "rowCount": 0, "elapsedMs": 0},
            snapshot_at=datetime.now(),
            tenant_id=bi_datasource.tenant_id,
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )

        # mock _rerun_chart_sql 返回含 phone 的数据
        async def fake_rerun(chart_obj, **kw):
            return {
                "columns": ["name", "phone"],
                "rows": [{"name": "Alice", "phone": "13800138000"}],
                "rowCount": 1,
                "elapsedMs": 50,
            }

        with patch("app.business.bi.services_chart._rerun_chart_sql", side_effect=fake_rerun):
            refreshed = await refresh_chart(chart.id, bi_datasource.tenant_id, bi_datasource.tenant_id)

        assert refreshed.result_snapshot["rows"][0]["phone"] == "138****8000"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_bi_masking.py::TestRefreshChartMasking -v`
Expected: FAIL（refresh_chart 未脱敏）

- [ ] **Step 3: 在 `services_chart.py` 的 `refresh_chart` 接入 apply_masking**

> 先 Read `services_chart.py`，找到 `_rerun_chart_sql` 返回后写 `chart.result_snapshot` 的位置。

```python
# 在 refresh_chart 函数内：
from app.business.bi.services_masking import apply_masking

# 原代码：
# snapshot = await _rerun_chart_sql(chart)
# chart.result_snapshot = snapshot

# 改为：
snapshot = await _rerun_chart_sql(chart)
# 对快照 rows 应用脱敏
if snapshot.get("rows"):
    snapshot["rows"] = await apply_masking(snapshot["rows"])
chart.result_snapshot = snapshot
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_bi_masking.py::TestRefreshChartMasking -v`
Expected: PASS

- [ ] **Step 5: 跑现有 chart 测试确认无回归**

Run: `uv run pytest tests/test_bi_chart.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add app/business/bi/services_chart.py tests/test_bi_masking.py
git commit -m "feat(bi): apply masking in refresh_chart (chart snapshot path)"
```

---

## Task 6: 接入 load_quota_config 到 execute_sql

**Files:**
- Modify: `app/business/bi/sandbox/executor.py`
- Test: `tests/test_bi_quota.py`

- [ ] **Step 1: 写 execute_sql 配额接入测试**

在 `tests/test_bi_quota.py` 追加：

```python
class TestExecuteSqlQuotaIntegration:
    async def test_user_quota_enforced(self, app, bi_datasource, monkeypatch):
        """用户级配额配置被 execute_sql 强制执行。"""
        from unittest.mock import patch, AsyncMock
        from app.business.bi.sandbox.executor import execute_sql

        # 创建 user 级配额：max_rows=5
        await BiQuotaConfig.create(
            name="user-strict",
            max_rows=5,
            timeout_seconds=10,
            breaker_threshold=3,
            breaker_window_seconds=30,
            scope_type="user",
            scope_id=bi_datasource.tenant_id,
            status_type=StatusType.enable,
            created_by="1",
            updated_by="1",
        )
        await invalidate_quota_cache()

        # mock 实际查询返回 10 行（超过 max_rows=5）
        async def fake_execute(query, datasource, **kw):
            class FakeResult:
                columns = ["id"]
                rows = [{"id": i} for i in range(10)]
                row_count = 10
                elapsed_ms = 50
            return FakeResult()

        with patch("app.business.bi.sandbox.executor._execute_raw", side_effect=fake_execute):
            from app.core.exceptions import BizError
            with pytest.raises(BizError) as exc_info:
                await execute_sql(
                    sql="SELECT id FROM t",
                    datasource=bi_datasource,
                    user_id=bi_datasource.tenant_id,
                )
            # 错误码 4103 = BI_QUERY_ROW_LIMIT
            assert exc_info.value.code == 4103
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_bi_quota.py::TestExecuteSqlQuotaIntegration -v`
Expected: FAIL（execute_sql 未接入 load_quota_config）

- [ ] **Step 3: 在 `sandbox/executor.py` 的 `execute_sql` 接入 load_quota_config**

> 先 Read `sandbox/executor.py`，找到 `check_quota` / `check_row_limit` / `get_timeout` 调用位置。把 `_default_config` 替换为 `load_quota_config` 返回值。

```python
# 在 execute_sql 函数内，原代码：
# scope = f"user:{user_id}"
# await check_quota(scope, redis)
# ...
# await check_row_limit(result.row_count)
# timeout = get_timeout()

# 改为：
from app.business.bi.services_quota import load_quota_config

scope = f"user:{user_id}"
# 按 (user, user_id) 查找配额配置（datasource 作用域暂不传，因 execute_sql 的 datasource 是模型实例）
cfg = await load_quota_config("user", user_id)
await check_quota(scope, redis, config=cfg)
# ...
await check_row_limit(result.row_count, config=cfg)
# timeout 用 cfg
```

> 注意：`execute_sql` 的 `datasource` 参数已是模型实例，可顺带传 `datasource.id` 做更细粒度查找。但为保持改动最小，先只传 user 作用域。

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_bi_quota.py::TestExecuteSqlQuotaIntegration -v`
Expected: PASS

- [ ] **Step 5: 跑现有 sandbox/executor 测试确认无回归**

Run: `uv run pytest tests/ -v -k "executor or sql_workbench or async_query"`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add app/business/bi/sandbox/executor.py tests/test_bi_quota.py
git commit -m "feat(bi): wire load_quota_config into execute_sql (enforce user quota)"
```

---

## Task 7: API 路由 masking.py

**Files:**
- Create: `app/business/bi/api/masking.py`
- Modify: `app/business/bi/api/__init__.py`
- Test: `tests/test_bi_masking.py`

- [ ] **Step 1: 写 API 鉴权测试**

在 `tests/test_bi_masking.py` 追加：

```python
from httpx import AsyncClient

PREFIX = "/api/v1/business/bi"


class TestMaskingAPIAuth:
    async def test_search_requires_auth(self, app, client: AsyncClient):
        """未登录访问 /masking/search 返回 2100。"""
        resp = await client.post(f"{PREFIX}/masking/search", json={"current": 1, "size": 10})
        assert resp.status_code == 200
        assert resp.json()["code"] == 2100

    async def test_create_requires_auth(self, app, client: AsyncClient):
        resp = await client.post(f"{PREFIX}/masking", json={"name": "r1", "column_pattern": "phone", "mask_type": "phone"})
        assert resp.json()["code"] == 2100
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_bi_masking.py::TestMaskingAPIAuth -v`
Expected: FAIL（路由未注册，返回 404）

- [ ] **Step 3: 创建 `api/masking.py`**

```python
"""BiMaskingRule API 路由。"""
from __future__ import annotations

from fastapi import APIRouter

from app.business.bi.controllers import bi_masking_rule_controller
from app.business.bi.schemas import (
    BiMaskingRuleCreate,
    BiMaskingRuleSearch,
    BiMaskingRuleUpdate,
)
from app.business.bi.services_masking import invalidate_masking_cache
from app.utils import CRUDRouter, SearchFieldConfig, require_buttons

masking_crud = CRUDRouter(
    prefix="/masking",
    controller=bi_masking_rule_controller,
    create_schema=BiMaskingRuleCreate,
    update_schema=BiMaskingRuleUpdate,
    list_schema=BiMaskingRuleSearch,
    search_fields=SearchFieldConfig(
        contains_fields=["name"],
        exact_fields=["mask_type", "status_type"],
    ),
    summary_prefix="脱敏规则",
    enable_routes={"list", "get", "create", "update", "delete", "batch_delete"},
    route_key_prefix="bi.masking",
    action_dependencies={
        "list": [require_buttons("B_BI_MASKING_VIEW")],
        "get": [require_buttons("B_BI_MASKING_VIEW")],
        "create": [require_buttons("B_BI_MASKING_CREATE")],
        "update": [require_buttons("B_BI_MASKING_EDIT")],
        "delete": [require_buttons("B_BI_MASKING_DELETE")],
        "batch_delete": [require_buttons("B_BI_MASKING_DELETE")],
    },
)


@masking_crud.override("create")
async def _after_create(*args, **kwargs):
    """创建后失效缓存。"""
    result = await masking_crud.default_create(*args, **kwargs)
    await invalidate_masking_cache()
    return result


@masking_crud.override("update")
async def _after_update(*args, **kwargs):
    """更新后失效缓存。"""
    result = await masking_crud.default_update(*args, **kwargs)
    await invalidate_masking_cache()
    return result


@masking_crud.override("delete")
async def _after_delete(*args, **kwargs):
    """删除后失效缓存。"""
    result = await masking_crud.default_delete(*args, **kwargs)
    await invalidate_masking_cache()
    return result


router = APIRouter()
router.include_router(masking_crud.router)
```

- [ ] **Step 4: 在 `api/__init__.py` 挂载路由**

> 先 Read `api/__init__.py`，按现有模式追加。

```python
from .masking import router as masking_router
# ...
router.include_router(masking_router)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run pytest tests/test_bi_masking.py::TestMaskingAPIAuth -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add app/business/bi/api/masking.py app/business/bi/api/__init__.py tests/test_bi_masking.py
git commit -m "feat(bi): add masking API routes (6 endpoints with cache invalidation)"
```

---

## Task 8: API 路由 quota.py

**Files:**
- Create: `app/business/bi/api/quota.py`
- Modify: `app/business/bi/api/__init__.py`
- Test: `tests/test_bi_quota.py`

- [ ] **Step 1: 写 API 鉴权测试**

在 `tests/test_bi_quota.py` 追加：

```python
from httpx import AsyncClient

PREFIX = "/api/v1/business/bi"


class TestQuotaAPIAuth:
    async def test_search_requires_auth(self, app, client: AsyncClient):
        resp = await client.post(f"{PREFIX}/quota/search", json={"current": 1, "size": 10})
        assert resp.status_code == 200
        assert resp.json()["code"] == 2100

    async def test_create_requires_auth(self, app, client: AsyncClient):
        resp = await client.post(
            f"{PREFIX}/quota",
            json={"name": "q1", "scope_type": "global", "max_rows": 10000},
        )
        assert resp.json()["code"] == 2100
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_bi_quota.py::TestQuotaAPIAuth -v`
Expected: FAIL（路由未注册）

- [ ] **Step 3: 创建 `api/quota.py`**

```python
"""BiQuotaConfig API 路由。"""
from __future__ import annotations

from fastapi import APIRouter

from app.business.bi.controllers import bi_quota_config_controller
from app.business.bi.schemas import (
    BiQuotaConfigCreate,
    BiQuotaConfigSearch,
    BiQuotaConfigUpdate,
)
from app.business.bi.services_quota import invalidate_quota_cache
from app.utils import CRUDRouter, SearchFieldConfig, require_buttons

quota_crud = CRUDRouter(
    prefix="/quota",
    controller=bi_quota_config_controller,
    create_schema=BiQuotaConfigCreate,
    update_schema=BiQuotaConfigUpdate,
    list_schema=BiQuotaConfigSearch,
    search_fields=SearchFieldConfig(
        contains_fields=["name"],
        exact_fields=["scope_type", "status_type"],
    ),
    summary_prefix="配额配置",
    enable_routes={"list", "get", "create", "update", "delete", "batch_delete"},
    route_key_prefix="bi.quota",
    action_dependencies={
        "list": [require_buttons("B_BI_QUOTA_VIEW")],
        "get": [require_buttons("B_BI_QUOTA_VIEW")],
        "create": [require_buttons("B_BI_QUOTA_CREATE")],
        "update": [require_buttons("B_BI_QUOTA_EDIT")],
        "delete": [require_buttons("B_BI_QUOTA_DELETE")],
        "batch_delete": [require_buttons("B_BI_QUOTA_DELETE")],
    },
)


@quota_crud.override("create")
async def _after_create(*args, **kwargs):
    result = await quota_crud.default_create(*args, **kwargs)
    await invalidate_quota_cache()
    return result


@quota_crud.override("update")
async def _after_update(*args, **kwargs):
    result = await quota_crud.default_update(*args, **kwargs)
    await invalidate_quota_cache()
    return result


@quota_crud.override("delete")
async def _after_delete(*args, **kwargs):
    result = await quota_crud.default_delete(*args, **kwargs)
    await invalidate_quota_cache()
    return result


router = APIRouter()
router.include_router(quota_crud.router)
```

- [ ] **Step 4: 在 `api/__init__.py` 挂载路由**

```python
from .quota import router as quota_router
# ...
router.include_router(quota_router)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run pytest tests/test_bi_quota.py::TestQuotaAPIAuth -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add app/business/bi/api/quota.py app/business/bi/api/__init__.py tests/test_bi_quota.py
git commit -m "feat(bi): add quota API routes (6 endpoints with cache invalidation)"
```

---

## Task 9: 菜单/按钮/角色权限

**Files:**
- Modify: `app/business/bi/init_data.py`

- [ ] **Step 1: 在 `BI_MENU_CHILDREN` 追加 2 个菜单**

> 在仪表盘菜单块之后追加：

```python
    {
        "menu_name": "脱敏规则",
        "route_name": "bi_masking",
        "route_path": "/bi/masking",
        "component": "view.bi_masking",
        "icon": "mdi:shield-half-full",
        "order": 10,
        "buttons": [
            {"button_code": "B_BI_MASKING_VIEW", "button_desc": "查看脱敏规则"},
            {"button_code": "B_BI_MASKING_CREATE", "button_desc": "创建脱敏规则"},
            {"button_code": "B_BI_MASKING_EDIT", "button_desc": "编辑脱敏规则"},
            {"button_code": "B_BI_MASKING_DELETE", "button_desc": "删除脱敏规则"},
        ],
    },
    {
        "menu_name": "配额配置",
        "route_name": "bi_quota",
        "route_path": "/bi/quota",
        "component": "view.bi_quota",
        "icon": "mdi:speedometer",
        "order": 11,
        "buttons": [
            {"button_code": "B_BI_QUOTA_VIEW", "button_desc": "查看配额配置"},
            {"button_code": "B_BI_QUOTA_CREATE", "button_desc": "创建配额配置"},
            {"button_code": "B_BI_QUOTA_EDIT", "button_desc": "编辑配额配置"},
            {"button_code": "B_BI_QUOTA_DELETE", "button_desc": "删除配额配置"},
        ],
    },
```

- [ ] **Step 2: 在 `BI_ALL_BUTTONS` 追加 8 个按钮码**

```python
    # masking / quota
    "B_BI_MASKING_VIEW",
    "B_BI_MASKING_CREATE",
    "B_BI_MASKING_EDIT",
    "B_BI_MASKING_DELETE",
    "B_BI_QUOTA_VIEW",
    "B_BI_QUOTA_CREATE",
    "B_BI_QUOTA_EDIT",
    "B_BI_QUOTA_DELETE",
```

- [ ] **Step 3: 在 `BI_ALL_MENUS` 追加**

```python
    "bi_masking",
    "bi_quota",
```

- [ ] **Step 4: 在 `BI_ADMIN_APIS` 追加 12 个 route_name**

```python
    # masking（CRUD）
    "bi.masking.list",
    "bi.masking.get",
    "bi.masking.create",
    "bi.masking.update",
    "bi.masking.delete",
    "bi.masking.batch_delete",
    # quota（CRUD）
    "bi.quota.list",
    "bi.quota.get",
    "bi.quota.create",
    "bi.quota.update",
    "bi.quota.delete",
    "bi.quota.batch_delete",
```

- [ ] **Step 5: 确认 `BI_ANALYST_*` 不追加**

> 脱敏/配额仅管理员可见。确认 `BI_ANALYST_MENUS` / `BI_ANALYST_BUTTONS` / `BI_ANALYST_APIS` 未被修改。

- [ ] **Step 6: 提交**

```bash
git add app/business/bi/init_data.py
git commit -m "feat(bi): add masking/quota menu/buttons/role permissions (admin only)"
```

---

## Task 10: 前端 typings 补全

**Files:**
- Modify: `web/src/typings/api/bi.d.ts`

- [ ] **Step 1: 在 `web/src/typings/api/bi.d.ts` 找到 Security 区块，补全类型**

> 先 Grep 找到 `BiMaskingRule` 和 `BiQuotaConfig` 类型定义位置。补全 statusType 字段 + OperateParams / SearchParams / List 类型。

```typescript
// Security（脱敏规则 / 配额配置）
type MaskType = 'phone' | 'idcard' | 'email' | 'bankcard' | 'custom';

type BiMaskingRule = Common.CommonRecord<{
  name: string;
  columnPattern: string;
  maskType: MaskType;
  maskChar: string | null;
  keepPrefix: number;
  keepSuffix: number;
}>;

type BiMaskingRuleOperateParams = {
  id?: string;
  name: string;
  columnPattern: string;
  maskType: MaskType;
  maskChar?: string | null;
  keepPrefix?: number;
  keepSuffix?: number;
  statusType?: 'enable' | 'disable';
};

type BiMaskingRuleSearchParams = Pick<Common.PaginatingCommonParams, 'current' | 'size'> & {
  name?: string;
  maskType?: MaskType;
  statusType?: 'enable' | 'disable';
};

type BiMaskingRuleList = Common.PaginatingCommonParams & {
  records: BiMaskingRule[];
  total: number;
};

type BiQuotaConfig = Common.CommonRecord<{
  name: string;
  maxRows: number;
  timeoutSeconds: number;
  breakerThreshold: number;
  breakerWindowSeconds: number;
  scopeType: 'global' | 'user' | 'datasource';
  scopeId: number | null;
}>;

type BiQuotaConfigOperateParams = {
  id?: string;
  name: string;
  maxRows?: number;
  timeoutSeconds?: number;
  breakerThreshold?: number;
  breakerWindowSeconds?: number;
  scopeType: 'global' | 'user' | 'datasource';
  scopeId?: number | null;
  statusType?: 'enable' | 'disable';
};

type BiQuotaConfigSearchParams = Pick<Common.PaginatingCommonParams, 'current' | 'size'> & {
  name?: string;
  scopeType?: 'global' | 'user' | 'datasource';
  statusType?: 'enable' | 'disable';
};

type BiQuotaConfigList = Common.PaginatingCommonParams & {
  records: BiQuotaConfig[];
  total: number;
};
```

- [ ] **Step 2: 提交**

```bash
git add web/src/typings/api/bi.d.ts
git commit -m "feat(bi-web): complete masking/quota typings"
```

---

## Task 11: 前端 service API

**Files:**
- Create: `web/src/service/api/bi-masking.ts`
- Create: `web/src/service/api/bi-quota.ts`

- [ ] **Step 1: 创建 `bi-masking.ts`**

```typescript
import { request } from '../request';

/** 脱敏规则分页搜索 */
export function fetchBiMaskingList(data?: Api.Bi.BiMaskingRuleSearchParams) {
  return request<Api.Bi.BiMaskingRuleList>({
    url: '/business/bi/masking/search',
    method: 'post',
    data: data ?? {}
  });
}

/** 获取脱敏规则详情 */
export function fetchBiMasking(id: string) {
  return request<Api.Bi.BiMaskingRule>({
    url: `/business/bi/masking/${id}`,
    method: 'get'
  });
}

/** 创建脱敏规则 */
export function fetchAddBiMasking(data: Api.Bi.BiMaskingRuleOperateParams) {
  return request<Api.Bi.CreateResult>({
    url: '/business/bi/masking',
    method: 'post',
    data
  });
}

/** 更新脱敏规则 */
export function fetchUpdateBiMasking(data: Api.Bi.BiMaskingRuleOperateParams) {
  return request<Api.Bi.UpdateResult>({
    url: `/business/bi/masking/${data.id}`,
    method: 'put',
    data
  });
}

/** 删除脱敏规则 */
export function fetchDeleteBiMasking(data: Api.Bi.CommonDeleteParams) {
  return request<null>({
    url: `/business/bi/masking/${data.id}`,
    method: 'delete'
  });
}

/** 批量删除脱敏规则 */
export function fetchBatchDeleteBiMasking(data: Api.Bi.CommonBatchDeleteParams) {
  return request<null>({
    url: '/business/bi/masking/batch_delete',
    method: 'delete',
    data
  });
}
```

- [ ] **Step 2: 创建 `bi-quota.ts`**

```typescript
import { request } from '../request';

/** 配额配置分页搜索 */
export function fetchBiQuotaList(data?: Api.Bi.BiQuotaConfigSearchParams) {
  return request<Api.Bi.BiQuotaConfigList>({
    url: '/business/bi/quota/search',
    method: 'post',
    data: data ?? {}
  });
}

/** 获取配额配置详情 */
export function fetchBiQuota(id: string) {
  return request<Api.Bi.BiQuotaConfig>({
    url: `/business/bi/quota/${id}`,
    method: 'get'
  });
}

/** 创建配额配置 */
export function fetchAddBiQuota(data: Api.Bi.BiQuotaConfigOperateParams) {
  return request<Api.Bi.CreateResult>({
    url: '/business/bi/quota',
    method: 'post',
    data
  });
}

/** 更新配额配置 */
export function fetchUpdateBiQuota(data: Api.Bi.BiQuotaConfigOperateParams) {
  return request<Api.Bi.UpdateResult>({
    url: `/business/bi/quota/${data.id}`,
    method: 'put',
    data
  });
}

/** 删除配额配置 */
export function fetchDeleteBiQuota(data: Api.Bi.CommonDeleteParams) {
  return request<null>({
    url: `/business/bi/quota/${data.id}`,
    method: 'delete'
  });
}

/** 批量删除配额配置 */
export function fetchBatchDeleteBiQuota(data: Api.Bi.CommonBatchDeleteParams) {
  return request<null>({
    url: '/business/bi/quota/batch_delete',
    method: 'delete',
    data
  });
}
```

- [ ] **Step 3: 提交**

```bash
git add web/src/service/api/bi-masking.ts web/src/service/api/bi-quota.ts
git commit -m "feat(bi-web): add masking/quota API services"
```

---

## Task 12: 前端 i18n

**Files:**
- Modify: `web/src/locales/langs/_generated/bi/zh-cn.ts`
- Modify: `web/src/locales/langs/_generated/bi/en-us.ts`
- Modify: `web/src/locales/langs/_generated/bi/types.d.ts`
- Modify: `web/src/locales/langs/zh-cn.ts`
- Modify: `web/src/locales/langs/en-us.ts`

- [ ] **Step 1: 在 `route` 区块追加路由名（zh-cn.ts）**

```typescript
    bi_masking: '脱敏规则',
    bi_quota: '配额配置',
```

- [ ] **Step 2: 在 `route` 区块追加路由名（en-us.ts）**

```typescript
    bi_masking: 'Masking Rules',
    bi_quota: 'Quota Config',
```

- [ ] **Step 3: 在 `page.bi` 区块追加 masking 文案（_generated/bi/zh-cn.ts）**

```typescript
    masking: {
      title: '脱敏规则',
      create: '新建规则',
      edit: '编辑规则',
      name: '规则名称',
      columnPattern: '列名匹配模式',
      maskType: '脱敏类型',
      maskChar: '占位字符',
      keepPrefix: '保留前缀',
      keepSuffix: '保留后缀',
      status: '状态',
      searchPlaceholder: '搜索规则名称',
      maskTypes: {
        phone: '手机号',
        idcard: '身份证',
        email: '邮箱',
        bankcard: '银行卡',
        custom: '自定义',
      },
      confirmDelete: '确认删除该规则吗？',
      empty: '暂无脱敏规则',
    },
```

- [ ] **Step 4: 在 `page.bi` 区块追加 quota 文案（_generated/bi/zh-cn.ts）**

```typescript
    quota: {
      title: '配额配置',
      create: '新建配置',
      edit: '编辑配置',
      name: '配置名称',
      maxRows: '最大行数',
      timeoutSeconds: '超时秒数',
      breakerThreshold: '熔断阈值',
      breakerWindowSeconds: '熔断窗口秒数',
      scopeType: '作用域',
      scopeId: '作用域ID',
      status: '状态',
      searchPlaceholder: '搜索配置名称',
      scopeTypes: {
        global: '全局',
        user: '按用户',
        datasource: '按数据源',
      },
      confirmDelete: '确认删除该配置吗？',
      empty: '暂无配额配置',
    },
```

- [ ] **Step 5: 在 en-us.ts 追加对应英文（masking + quota）**

```typescript
    masking: {
      title: 'Masking Rules',
      create: 'New Rule',
      edit: 'Edit Rule',
      name: 'Rule Name',
      columnPattern: 'Column Pattern (Regex)',
      maskType: 'Mask Type',
      maskChar: 'Mask Char',
      keepPrefix: 'Keep Prefix',
      keepSuffix: 'Keep Suffix',
      status: 'Status',
      searchPlaceholder: 'Search rule name',
      maskTypes: {
        phone: 'Phone',
        idcard: 'ID Card',
        email: 'Email',
        bankcard: 'Bank Card',
        custom: 'Custom',
      },
      confirmDelete: 'Delete this rule?',
      empty: 'No masking rules',
    },
    quota: {
      title: 'Quota Config',
      create: 'New Config',
      edit: 'Edit Config',
      name: 'Config Name',
      maxRows: 'Max Rows',
      timeoutSeconds: 'Timeout (s)',
      breakerThreshold: 'Breaker Threshold',
      breakerWindowSeconds: 'Breaker Window (s)',
      scopeType: 'Scope',
      scopeId: 'Scope ID',
      status: 'Status',
      searchPlaceholder: 'Search config name',
      scopeTypes: {
        global: 'Global',
        user: 'Per User',
        datasource: 'Per Datasource',
      },
      confirmDelete: 'Delete this config?',
      empty: 'No quota configs',
    },
```

- [ ] **Step 6: 在 `types.d.ts` 追加类型**

```typescript
    masking: {
      title: string;
      create: string;
      edit: string;
      name: string;
      columnPattern: string;
      maskType: string;
      maskChar: string;
      keepPrefix: string;
      keepSuffix: string;
      status: string;
      searchPlaceholder: string;
      maskTypes: {
        phone: string;
        idcard: string;
        email: string;
        bankcard: string;
        custom: string;
      };
      confirmDelete: string;
      empty: string;
    };
    quota: {
      title: string;
      create: string;
      edit: string;
      name: string;
      maxRows: string;
      timeoutSeconds: string;
      breakerThreshold: string;
      breakerWindowSeconds: string;
      scopeType: string;
      scopeId: string;
      status: string;
      searchPlaceholder: string;
      scopeTypes: {
        global: string;
        user: string;
        datasource: string;
      };
      confirmDelete: string;
      empty: string;
    };
```

- [ ] **Step 7: 提交**

```bash
git add web/src/locales/
git commit -m "feat(bi-web): add masking/quota i18n (zh-cn/en-us)"
```

---

## Task 13: 前端脱敏规则管理页

**Files:**
- Create: `web/src/views/bi/masking/index.vue`
- Create: `web/src/views/bi/masking/modules/masking-operate-modal.vue`

- [ ] **Step 1: 创建 `masking-operate-modal.vue`**

> 仿 `web/src/views/bi/metrics/modules/metric-operate-modal.vue` 模式。

```vue
<script setup lang="ts">
import { computed, reactive, watch } from 'vue';
import { NForm, NFormItem, NInput, NInputNumber, NSelect, NSwitch, useForm } from 'naive-ui';
import { fetchAddBiMasking, fetchBiMasking, fetchUpdateBiMasking } from '@/service/api/bi-masking';
import { $t } from '@/locales';
import { useNaiveForm } from '@/hooks/common/form';

defineOptions({ name: 'BiMaskingOperateModal' });

const visible = defineModel<boolean>('visible', { default: false });
const emit = defineEmits<{ submitted: [] }>();

const props = defineProps<{
  operateType: 'add' | 'edit';
  editingId?: string | null;
}>();

const { formRef, validate } = useNaiveForm();

const model = reactive({
  name: '',
  columnPattern: '',
  maskType: 'phone' as Api.Bi.MaskType,
  maskChar: '*',
  keepPrefix: 0,
  keepSuffix: 0,
  statusType: 'enable' as 'enable' | 'disable',
});

const rules = {
  name: { required: true, message: $t('common.pattern.require'), trigger: 'blur' },
  columnPattern: { required: true, message: $t('common.pattern.require'), trigger: 'blur' },
  maskType: { required: true, message: $t('common.pattern.require'), trigger: 'change' },
};

const maskTypeOptions = [
  { label: $t('page.bi.masking.maskTypes.phone'), value: 'phone' },
  { label: $t('page.bi.masking.maskTypes.idcard'), value: 'idcard' },
  { label: $t('page.bi.masking.maskTypes.email'), value: 'email' },
  { label: $t('page.bi.masking.maskTypes.bankcard'), value: 'bankcard' },
  { label: $t('page.bi.masking.maskTypes.custom'), value: 'custom' },
];

const isEdit = computed(() => props.operateType === 'edit');
const title = computed(() => (isEdit.value ? $t('page.bi.masking.edit') : $t('page.bi.masking.create')));

function resetModel() {
  model.name = '';
  model.columnPattern = '';
  model.maskType = 'phone';
  model.maskChar = '*';
  model.keepPrefix = 0;
  model.keepSuffix = 0;
  model.statusType = 'enable';
}

async function handleInitModel() {
  resetModel();
  if (isEdit.value && props.editingId) {
    const { data } = await fetchBiMasking(props.editingId);
    if (data) {
      model.name = data.name;
      model.columnPattern = data.columnPattern;
      model.maskType = data.maskType;
      model.maskChar = data.maskChar || '*';
      model.keepPrefix = data.keepPrefix ?? 0;
      model.keepSuffix = data.keepSuffix ?? 0;
      model.statusType = data.statusType === 'enable' ? 'enable' : 'disable';
    }
  }
}

watch(visible, val => {
  if (val) handleInitModel();
});

async function handleSubmit() {
  await validate();
  const params: Api.Bi.BiMaskingRuleOperateParams = {
    name: model.name,
    columnPattern: model.columnPattern,
    maskType: model.maskType,
    maskChar: model.maskChar || null,
    keepPrefix: model.keepPrefix,
    keepSuffix: model.keepSuffix,
    statusType: model.statusType,
  };
  if (isEdit.value && props.editingId) {
    params.id = props.editingId;
    const { error } = await fetchUpdateBiMasking(params);
    if (!error) {
      window.$message?.success($t('common.updateSuccess'));
      visible.value = false;
      emit('submitted');
    }
  } else {
    const { error } = await fetchAddBiMasking(params);
    if (!error) {
      window.$message?.success($t('common.addSuccess'));
      visible.value = false;
      emit('submitted');
    }
  }
}
</script>

<template>
  <NModal v-model:show="visible" preset="card" :title="title" style="width: 520px">
    <NForm ref="formRef" :model="model" :rules="rules" label-placement="top">
      <NFormItem :label="$t('page.bi.masking.name')" path="name">
        <NInput v-model:value="model.name" :placeholder="$t('page.bi.masking.name')" maxlength="100" show-count />
      </NFormItem>
      <NFormItem :label="$t('page.bi.masking.columnPattern')" path="columnPattern">
        <NInput v-model:value="model.columnPattern" :placeholder="$t('page.bi.masking.columnPattern')" maxlength="200" />
      </NFormItem>
      <NFormItem :label="$t('page.bi.masking.maskType')" path="maskType">
        <NSelect v-model:value="model.maskType" :options="maskTypeOptions" />
      </NFormItem>
      <NFormItem :label="$t('page.bi.masking.maskChar')">
        <NInput v-model:value="model.maskChar" maxlength="10" style="width: 100px" />
      </NFormItem>
      <NFormItem :label="$t('page.bi.masking.keepPrefix')">
        <NInputNumber v-model:value="model.keepPrefix" :min="0" :max="50" />
      </NFormItem>
      <NFormItem :label="$t('page.bi.masking.keepSuffix')">
        <NInputNumber v-model:value="model.keepSuffix" :min="0" :max="50" />
      </NFormItem>
      <NFormItem :label="$t('page.bi.masking.status')">
        <NSwitch v-model:value="model.statusType" checked-value="enable" unchecked-value="disable" />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="visible = false">{{ $t('common.cancel') }}</NButton>
        <NButton type="primary" @click="handleSubmit">{{ $t('common.confirm') }}</NButton>
      </NSpace>
    </template>
  </NModal>
</template>
```

- [ ] **Step 2: 创建 `masking/index.vue`**

> 仿 `web/src/views/bi/metrics/index.vue` 模式。

```vue
<script setup lang="tsx">
import { ref } from 'vue';
import { NButton, NPopconfirm, NTag } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { fetchBatchDeleteBiMasking, fetchBiMaskingList, fetchDeleteBiMasking } from '@/service/api/bi-masking';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';
import { useNaiveTable } from '@/hooks/common/table';
import MaskingOperateModal from './modules/masking-operate-modal.vue';

defineOptions({ name: 'BiMasking' });

const { hasAuth } = useAuth();

const searchParams = ref({
  name: '',
  maskType: null as Api.Bi.MaskType | null,
  statusType: null as 'enable' | 'disable' | null,
});

const {
  loading,
  data,
  pagination,
  getData,
  getDataByPage,
  searchParams: tableSearchParams,
} = useNaiveTable({
  api: fetchBiMaskingList,
  searchParams,
});

const operateType = ref<'add' | 'edit'>('add');
const editingId = ref<string | null>(null);
const modalVisible = ref(false);

function handleAdd() {
  operateType.value = 'add';
  editingId.value = null;
  modalVisible.value = true;
}

function handleEdit(id: string) {
  operateType.value = 'edit';
  editingId.value = id;
  modalVisible.value = true;
}

async function handleDelete(id: string) {
  const { error } = await fetchDeleteBiMasking({ id });
  if (!error) {
    window.$message?.success($t('common.deleteSuccess'));
    getData();
  }
}

async function handleBatchDelete(ids: string[]) {
  const { error } = await fetchBatchDeleteBiMasking({ ids });
  if (!error) {
    window.$message?.success($t('common.deleteSuccess'));
    getData();
  }
}

const columns: DataTableColumns<Api.Bi.BiMaskingRule> = [
  { key: 'name', title: $t('page.bi.masking.name'), minWidth: 120 },
  { key: 'columnPattern', title: $t('page.bi.masking.columnPattern'), minWidth: 160 },
  {
    key: 'maskType',
    title: $t('page.bi.masking.maskType'),
    width: 100,
    render: row => $t(`page.bi.masking.maskTypes.${row.maskType}`),
  },
  { key: 'maskChar', title: $t('page.bi.masking.maskChar'), width: 80 },
  { key: 'keepPrefix', title: $t('page.bi.masking.keepPrefix'), width: 90 },
  { key: 'keepSuffix', title: $t('page.bi.masking.keepSuffix'), width: 90 },
  {
    key: 'statusType',
    title: $t('page.bi.masking.status'),
    width: 80,
    render: row =>
      row.statusType === 'enable'
        ? <NTag type="success" size="small">{$t('common.enable')}</NTag>
        : <NTag type="default" size="small">{$t('common.disable')}</NTag>,
  },
  {
    key: 'actions',
    title: $t('common.action'),
    width: 160,
    fixed: 'right',
    render: row => (
      <NSpace size={4}>
        {hasAuth('B_BI_MASKING_EDIT') && (
          <NButton type="primary" ghost size="small" onClick={() => handleEdit(row.id)}>
            {$t('common.edit')}
          </NButton>
        )}
        {hasAuth('B_BI_MASKING_DELETE') && (
          <NPopconfirm onPositiveClick={() => handleDelete(row.id)}>
            {{
              default: () => $t('page.bi.masking.confirmDelete'),
              trigger: () => (
                <NButton type="error" ghost size="small">{$t('common.delete')}</NButton>
              ),
            }}
          </NPopconfirm>
        )}
      </NSpace>
    ),
  },
];
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <NCard :bordered="false" size="small" class="card-wrapper">
      <NSpace justify="space-between" align="center">
        <NSpace align="center" :size="12">
          <NInput
            v-model:value="searchParams.name"
            clearable
            :placeholder="$t('page.bi.masking.searchPlaceholder')"
            style="width: 200px"
            @keydown.enter="getDataByPage(1)"
          />
          <NSelect
            v-model:value="searchParams.maskType"
            clearable
            :placeholder="$t('page.bi.masking.maskType')"
            :options="[
              { label: $t('page.bi.masking.maskTypes.phone'), value: 'phone' },
              { label: $t('page.bi.masking.maskTypes.idcard'), value: 'idcard' },
              { label: $t('page.bi.masking.maskTypes.email'), value: 'email' },
              { label: $t('page.bi.masking.maskTypes.bankcard'), value: 'bankcard' },
              { label: $t('page.bi.masking.maskTypes.custom'), value: 'custom' },
            ]"
            style="width: 140px"
            @update:value="getDataByPage(1)"
          />
          <NButton size="small" type="primary" ghost @click="getDataByPage(1)">
            <template #icon><icon-ic-round-search class="text-icon" /></template>
            {{ $t('common.search') }}
          </NButton>
        </NSpace>
        <NButton v-if="hasAuth('B_BI_MASKING_CREATE')" type="primary" @click="handleAdd">
          <template #icon><icon-ic-round-add class="text-icon" /></template>
          {{ $t('page.bi.masking.create') }}
        </NButton>
      </NSpace>
    </NCard>

    <NCard :title="$t('page.bi.masking.title')" :bordered="false" size="small" class="card-wrapper sm:flex-1-hidden">
      <NDataTable
        :columns="columns"
        :data="data"
        :loading="loading"
        :pagination="pagination"
        size="small"
        flex-height
        :row-key="(row: Api.Bi.BiMaskingRule) => row.id"
      />
    </NCard>

    <MaskingOperateModal
      v-model:visible="modalVisible"
      :operate-type="operateType"
      :editing-id="editingId"
      @submitted="getData"
    />
  </div>
</template>
```

- [ ] **Step 3: 跑前端 lint + typecheck**

Run: `cd web && pnpm lint && pnpm typecheck`
Expected: PASS（如有类型问题需调整 useNaiveTable hook 引用）

- [ ] **Step 4: 提交**

```bash
git add web/src/views/bi/masking/
git commit -m "feat(bi-web): add masking rule management page (list + operate modal)"
```

---

## Task 14: 前端配额配置管理页

**Files:**
- Create: `web/src/views/bi/quota/index.vue`
- Create: `web/src/views/bi/quota/modules/quota-operate-modal.vue`

- [ ] **Step 1: 创建 `quota-operate-modal.vue`**

> 结构与 masking-operate-modal.vue 类似，字段改为 maxRows/timeoutSeconds/breakerThreshold/breakerWindowSeconds/scopeType/scopeId。

```vue
<script setup lang="ts">
import { computed, reactive, watch } from 'vue';
import { NForm, NFormItem, NInput, NInputNumber, NSelect, NSwitch } from 'naive-ui';
import { fetchAddBiQuota, fetchBiQuota, fetchUpdateBiQuota } from '@/service/api/bi-quota';
import { $t } from '@/locales';
import { useNaiveForm } from '@/hooks/common/form';

defineOptions({ name: 'BiQuotaOperateModal' });

const visible = defineModel<boolean>('visible', { default: false });
const emit = defineEmits<{ submitted: [] }>();

const props = defineProps<{
  operateType: 'add' | 'edit';
  editingId?: string | null;
}>();

const { formRef, validate } = useNaiveForm();

const model = reactive({
  name: '',
  maxRows: 10000,
  timeoutSeconds: 30,
  breakerThreshold: 10,
  breakerWindowSeconds: 60,
  scopeType: 'global' as 'global' | 'user' | 'datasource',
  scopeId: null as number | null,
  statusType: 'enable' as 'enable' | 'disable',
});

const rules = {
  name: { required: true, message: $t('common.pattern.require'), trigger: 'blur' },
  scopeType: { required: true, message: $t('common.pattern.require'), trigger: 'change' },
};

const scopeTypeOptions = [
  { label: $t('page.bi.quota.scopeTypes.global'), value: 'global' },
  { label: $t('page.bi.quota.scopeTypes.user'), value: 'user' },
  { label: $t('page.bi.quota.scopeTypes.datasource'), value: 'datasource' },
];

const isEdit = computed(() => props.operateType === 'edit');
const title = computed(() => (isEdit.value ? $t('page.bi.quota.edit') : $t('page.bi.quota.create')));
const showScopeId = computed(() => model.scopeType !== 'global');

function resetModel() {
  model.name = '';
  model.maxRows = 10000;
  model.timeoutSeconds = 30;
  model.breakerThreshold = 10;
  model.breakerWindowSeconds = 60;
  model.scopeType = 'global';
  model.scopeId = null;
  model.statusType = 'enable';
}

async function handleInitModel() {
  resetModel();
  if (isEdit.value && props.editingId) {
    const { data } = await fetchBiQuota(props.editingId);
    if (data) {
      model.name = data.name;
      model.maxRows = data.maxRows;
      model.timeoutSeconds = data.timeoutSeconds;
      model.breakerThreshold = data.breakerThreshold;
      model.breakerWindowSeconds = data.breakerWindowSeconds;
      model.scopeType = data.scopeType as 'global' | 'user' | 'datasource';
      model.scopeId = data.scopeId;
      model.statusType = data.statusType === 'enable' ? 'enable' : 'disable';
    }
  }
}

watch(visible, val => {
  if (val) handleInitModel();
});

async function handleSubmit() {
  await validate();
  const params: Api.Bi.BiQuotaConfigOperateParams = {
    name: model.name,
    maxRows: model.maxRows,
    timeoutSeconds: model.timeoutSeconds,
    breakerThreshold: model.breakerThreshold,
    breakerWindowSeconds: model.breakerWindowSeconds,
    scopeType: model.scopeType,
    scopeId: model.scopeType === 'global' ? null : model.scopeId,
    statusType: model.statusType,
  };
  if (isEdit.value && props.editingId) {
    params.id = props.editingId;
    const { error } = await fetchUpdateBiQuota(params);
    if (!error) {
      window.$message?.success($t('common.updateSuccess'));
      visible.value = false;
      emit('submitted');
    }
  } else {
    const { error } = await fetchAddBiQuota(params);
    if (!error) {
      window.$message?.success($t('common.addSuccess'));
      visible.value = false;
      emit('submitted');
    }
  }
}
</script>

<template>
  <NModal v-model:show="visible" preset="card" :title="title" style="width: 560px">
    <NForm ref="formRef" :model="model" :rules="rules" label-placement="top">
      <NFormItem :label="$t('page.bi.quota.name')" path="name">
        <NInput v-model:value="model.name" maxlength="100" show-count />
      </NFormItem>
      <NFormItem :label="$t('page.bi.quota.scopeType')" path="scopeType">
        <NSelect v-model:value="model.scopeType" :options="scopeTypeOptions" />
      </NFormItem>
      <NFormItem v-if="showScopeId" :label="$t('page.bi.quota.scopeId')">
        <NInputNumber v-model:value="model.scopeId" :min="1" style="width: 100%" />
      </NFormItem>
      <NFormItem :label="$t('page.bi.quota.maxRows')">
        <NInputNumber v-model:value="model.maxRows" :min="1" :max="1000000" style="width: 100%" />
      </NFormItem>
      <NFormItem :label="$t('page.bi.quota.timeoutSeconds')">
        <NInputNumber v-model:value="model.timeoutSeconds" :min="1" :max="600" style="width: 100%" />
      </NFormItem>
      <NFormItem :label="$t('page.bi.quota.breakerThreshold')">
        <NInputNumber v-model:value="model.breakerThreshold" :min="1" :max="1000" style="width: 100%" />
      </NFormItem>
      <NFormItem :label="$t('page.bi.quota.breakerWindowSeconds')">
        <NInputNumber v-model:value="model.breakerWindowSeconds" :min="1" :max="3600" style="width: 100%" />
      </NFormItem>
      <NFormItem :label="$t('page.bi.quota.status')">
        <NSwitch v-model:value="model.statusType" checked-value="enable" unchecked-value="disable" />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="visible = false">{{ $t('common.cancel') }}</NButton>
        <NButton type="primary" @click="handleSubmit">{{ $t('common.confirm') }}</NButton>
      </NSpace>
    </template>
  </NModal>
</template>
```

- [ ] **Step 2: 创建 `quota/index.vue`**

> 结构与 masking/index.vue 类似。

```vue
<script setup lang="tsx">
import { ref } from 'vue';
import { NButton, NPopconfirm, NTag } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { fetchBatchDeleteBiQuota, fetchBiQuotaList, fetchDeleteBiQuota } from '@/service/api/bi-quota';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';
import { useNaiveTable } from '@/hooks/common/table';
import QuotaOperateModal from './modules/quota-operate-modal.vue';

defineOptions({ name: 'BiQuota' });

const { hasAuth } = useAuth();

const searchParams = ref({
  name: '',
  scopeType: null as 'global' | 'user' | 'datasource' | null,
  statusType: null as 'enable' | 'disable' | null,
});

const { loading, data, pagination, getData, getDataByPage } = useNaiveTable({
  api: fetchBiQuotaList,
  searchParams,
});

const operateType = ref<'add' | 'edit'>('add');
const editingId = ref<string | null>(null);
const modalVisible = ref(false);

function handleAdd() {
  operateType.value = 'add';
  editingId.value = null;
  modalVisible.value = true;
}

function handleEdit(id: string) {
  operateType.value = 'edit';
  editingId.value = id;
  modalVisible.value = true;
}

async function handleDelete(id: string) {
  const { error } = await fetchDeleteBiQuota({ id });
  if (!error) {
    window.$message?.success($t('common.deleteSuccess'));
    getData();
  }
}

const columns: DataTableColumns<Api.Bi.BiQuotaConfig> = [
  { key: 'name', title: $t('page.bi.quota.name'), minWidth: 120 },
  {
    key: 'scopeType',
    title: $t('page.bi.quota.scopeType'),
    width: 110,
    render: row => $t(`page.bi.quota.scopeTypes.${row.scopeType}`),
  },
  { key: 'scopeId', title: $t('page.bi.quota.scopeId'), width: 100, render: row => row.scopeId ?? '-' },
  { key: 'maxRows', title: $t('page.bi.quota.maxRows'), width: 100 },
  { key: 'timeoutSeconds', title: $t('page.bi.quota.timeoutSeconds'), width: 110 },
  { key: 'breakerThreshold', title: $t('page.bi.quota.breakerThreshold'), width: 110 },
  { key: 'breakerWindowSeconds', title: $t('page.bi.quota.breakerWindowSeconds'), width: 140 },
  {
    key: 'statusType',
    title: $t('page.bi.quota.status'),
    width: 80,
    render: row =>
      row.statusType === 'enable'
        ? <NTag type="success" size="small">{$t('common.enable')}</NTag>
        : <NTag type="default" size="small">{$t('common.disable')}</NTag>,
  },
  {
    key: 'actions',
    title: $t('common.action'),
    width: 160,
    fixed: 'right',
    render: row => (
      <NSpace size={4}>
        {hasAuth('B_BI_QUOTA_EDIT') && (
          <NButton type="primary" ghost size="small" onClick={() => handleEdit(row.id)}>
            {$t('common.edit')}
          </NButton>
        )}
        {hasAuth('B_BI_QUOTA_DELETE') && (
          <NPopconfirm onPositiveClick={() => handleDelete(row.id)}>
            {{
              default: () => $t('page.bi.quota.confirmDelete'),
              trigger: () => (
                <NButton type="error" ghost size="small">{$t('common.delete')}</NButton>
              ),
            }}
          </NPopconfirm>
        )}
      </NSpace>
    ),
  },
];
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <NCard :bordered="false" size="small" class="card-wrapper">
      <NSpace justify="space-between" align="center">
        <NSpace align="center" :size="12">
          <NInput
            v-model:value="searchParams.name"
            clearable
            :placeholder="$t('page.bi.quota.searchPlaceholder')"
            style="width: 200px"
            @keydown.enter="getDataByPage(1)"
          />
          <NSelect
            v-model:value="searchParams.scopeType"
            clearable
            :placeholder="$t('page.bi.quota.scopeType')"
            :options="[
              { label: $t('page.bi.quota.scopeTypes.global'), value: 'global' },
              { label: $t('page.bi.quota.scopeTypes.user'), value: 'user' },
              { label: $t('page.bi.quota.scopeTypes.datasource'), value: 'datasource' },
            ]"
            style="width: 140px"
            @update:value="getDataByPage(1)"
          />
          <NButton size="small" type="primary" ghost @click="getDataByPage(1)">
            <template #icon><icon-ic-round-search class="text-icon" /></template>
            {{ $t('common.search') }}
          </NButton>
        </NSpace>
        <NButton v-if="hasAuth('B_BI_QUOTA_CREATE')" type="primary" @click="handleAdd">
          <template #icon><icon-ic-round-add class="text-icon" /></template>
          {{ $t('page.bi.quota.create') }}
        </NButton>
      </NSpace>
    </NCard>

    <NCard :title="$t('page.bi.quota.title')" :bordered="false" size="small" class="card-wrapper sm:flex-1-hidden">
      <NDataTable
        :columns="columns"
        :data="data"
        :loading="loading"
        :pagination="pagination"
        size="small"
        flex-height
        :row-key="(row: Api.Bi.BiQuotaConfig) => row.id"
      />
    </NCard>

    <QuotaOperateModal
      v-model:visible="modalVisible"
      :operate-type="operateType"
      :editing-id="editingId"
      @submitted="getData"
    />
  </div>
</template>
```

- [ ] **Step 3: 跑前端 lint + typecheck**

Run: `cd web && pnpm lint && pnpm typecheck`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add web/src/views/bi/quota/
git commit -m "feat(bi-web): add quota config management page (list + operate modal)"
```

---

## Task 15: 前端测试

**Files:**
- Create: `web/src/service/api/__tests__/bi-masking.test.ts`
- Create: `web/src/service/api/__tests__/bi-quota.test.ts`

- [ ] **Step 1: 创建 `bi-masking.test.ts`**

> 仿 `web/src/service/api/__tests__/bi-dashboard.test.ts` 模式。

```typescript
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockRequest = vi.fn();
vi.mock('../../request', () => ({
  request: mockRequest
}));

const {
  fetchBiMaskingList,
  fetchBiMasking,
  fetchAddBiMasking,
  fetchUpdateBiMasking,
  fetchDeleteBiMasking,
  fetchBatchDeleteBiMasking
} = await import('../bi-masking');

describe('BI Masking API Service', () => {
  beforeEach(() => {
    mockRequest.mockReset();
    mockRequest.mockResolvedValue({ data: null, error: null });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fetchBiMaskingList should POST to /business/bi/masking/search', async () => {
    const params = { current: 1, size: 10, name: 'phone' };
    await fetchBiMaskingList(params);
    expect(mockRequest).toHaveBeenCalledWith({
      url: '/business/bi/masking/search',
      method: 'post',
      data: params
    });
  });

  it('fetchBiMaskingList should default to empty object', async () => {
    await fetchBiMaskingList();
    expect(mockRequest).toHaveBeenCalledWith({
      url: '/business/bi/masking/search',
      method: 'post',
      data: {}
    });
  });

  it('fetchBiMasking should GET by id', async () => {
    await fetchBiMasking('abc');
    expect(mockRequest).toHaveBeenCalledWith({
      url: '/business/bi/masking/abc',
      method: 'get'
    });
  });

  it('fetchAddBiMasking should POST payload', async () => {
    const payload = { name: 'r1', columnPattern: 'phone$', maskType: 'phone' as const };
    await fetchAddBiMasking(payload);
    expect(mockRequest).toHaveBeenCalledWith({
      url: '/business/bi/masking',
      method: 'post',
      data: payload
    });
  });

  it('fetchUpdateBiMasking should PUT to /{id}', async () => {
    const payload = { id: 'm1', name: 'updated', columnPattern: 'phone$', maskType: 'phone' as const };
    await fetchUpdateBiMasking(payload);
    expect(mockRequest).toHaveBeenCalledWith({
      url: '/business/bi/masking/m1',
      method: 'put',
      data: payload
    });
  });

  it('fetchDeleteBiMasking should DELETE by id', async () => {
    await fetchDeleteBiMasking({ id: 'm1' });
    expect(mockRequest).toHaveBeenCalledWith({
      url: '/business/bi/masking/m1',
      method: 'delete'
    });
  });

  it('fetchBatchDeleteBiMasking should DELETE with ids', async () => {
    const payload = { ids: ['m1', 'm2'] };
    await fetchBatchDeleteBiMasking(payload);
    expect(mockRequest).toHaveBeenCalledWith({
      url: '/business/bi/masking/batch_delete',
      method: 'delete',
      data: payload
    });
  });
});
```

- [ ] **Step 2: 创建 `bi-quota.test.ts`**

```typescript
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockRequest = vi.fn();
vi.mock('../../request', () => ({
  request: mockRequest
}));

const {
  fetchBiQuotaList,
  fetchBiQuota,
  fetchAddBiQuota,
  fetchUpdateBiQuota,
  fetchDeleteBiQuota,
  fetchBatchDeleteBiQuota
} = await import('../bi-quota');

describe('BI Quota API Service', () => {
  beforeEach(() => {
    mockRequest.mockReset();
    mockRequest.mockResolvedValue({ data: null, error: null });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fetchBiQuotaList should POST to /business/bi/quota/search', async () => {
    const params = { current: 1, size: 10, scopeType: 'global' as const };
    await fetchBiQuotaList(params);
    expect(mockRequest).toHaveBeenCalledWith({
      url: '/business/bi/quota/search',
      method: 'post',
      data: params
    });
  });

  it('fetchBiQuota should GET by id', async () => {
    await fetchBiQuota('q1');
    expect(mockRequest).toHaveBeenCalledWith({
      url: '/business/bi/quota/q1',
      method: 'get'
    });
  });

  it('fetchAddBiQuota should POST payload', async () => {
    const payload = { name: 'global', scopeType: 'global' as const, maxRows: 5000 };
    await fetchAddBiQuota(payload);
    expect(mockRequest).toHaveBeenCalledWith({
      url: '/business/bi/quota',
      method: 'post',
      data: payload
    });
  });

  it('fetchUpdateBiQuota should PUT to /{id}', async () => {
    const payload = { id: 'q1', name: 'updated', scopeType: 'global' as const, maxRows: 8000 };
    await fetchUpdateBiQuota(payload);
    expect(mockRequest).toHaveBeenCalledWith({
      url: '/business/bi/quota/q1',
      method: 'put',
      data: payload
    });
  });

  it('fetchDeleteBiQuota should DELETE by id', async () => {
    await fetchDeleteBiQuota({ id: 'q1' });
    expect(mockRequest).toHaveBeenCalledWith({
      url: '/business/bi/quota/q1',
      method: 'delete'
    });
  });

  it('fetchBatchDeleteBiQuota should DELETE with ids', async () => {
    const payload = { ids: ['q1', 'q2'] };
    await fetchBatchDeleteBiQuota(payload);
    expect(mockRequest).toHaveBeenCalledWith({
      url: '/business/bi/quota/batch_delete',
      method: 'delete',
      data: payload
    });
  });
});
```

- [ ] **Step 3: 跑 vitest**

Run: `cd web && pnpm test`
Expected: PASS（含原有测试 + 新增 masking/quota 测试）

- [ ] **Step 4: 提交**

```bash
git add web/src/service/api/__tests__/bi-masking.test.ts web/src/service/api/__tests__/bi-quota.test.ts
git commit -m "test(bi-web): add masking/quota API service tests"
```

---

## Task 16: 端到端门禁验证

**Files:** 无（验证任务）

- [ ] **Step 1: 跑后端门禁**

Run: `just check`
Expected: ruff + basedpyright + pytest 全绿（原有 310 + 新增 masking/quota 测试）

- [ ] **Step 2: 跑前端门禁**

Run: `cd web && pnpm lint && pnpm typecheck && pnpm test`
Expected: 全绿

- [ ] **Step 3: 启动后端验证路由注册**

Run: `just run backend`（等启动完成）

```bash
curl -s http://localhost:9999/api/v1/business/bi/masking/search -X POST -H "Content-Type: application/json" -d '{"current":1,"size":10}'
# 期望返回 code: 2100（认证失败，非 404）

curl -s http://localhost:9999/api/v1/business/bi/quota/search -X POST -H "Content-Type: application/json" -d '{"current":1,"size":10}'
# 期望返回 code: 2100
```

- [ ] **Step 4: 关闭后端，清理端口**

Run: 停止后端命令，`lsof -ti:9999 | xargs kill -9`

- [ ] **Step 5: 最终提交（如有未提交改动）**

```bash
git add -A
git commit -m "chore(bi): security config batch D-1 complete - all checks pass"
```

---

## Self-Review

### Spec 覆盖检查

| Spec 要求 | 对应 Task |
|-----------|-----------|
| BiMaskingRule CRUD 6 路由 | Task 7 |
| BiQuotaConfig CRUD 6 路由 | Task 8 |
| mask_columns 接入 executor_node | Task 4 |
| mask_columns 接入 refresh_chart | Task 5 |
| load_quota_config 接入 execute_sql | Task 6 |
| 缓存（60s TTL + 主动失效） | Task 2 (masking) + Task 3 (quota) |
| 菜单/按钮/角色权限（仅 ADMIN） | Task 9 |
| 错误码 4120/4121 + 登记 4102/4103/4104 | Task 1 |
| 前端 typings 补全 | Task 10 |
| 前端 service API | Task 11 |
| 前端 i18n | Task 12 |
| 前端脱敏规则管理页 | Task 13 |
| 前端配额配置管理页 | Task 14 |
| 前端测试 | Task 15 |
| just check 全绿 | Task 16 |

### 占位符扫描

- 无 "TBD" / "TODO" / "implement later"
- 所有代码块均含完整实现
- `useNaiveTable` hook 引用需在 Task 13/14 确认（若 hook 不存在则改用 `useNaivePaginatedTable`）

### 类型一致性

- `load_masking_rules() -> list[BiMaskingRule]` 在 Task 2 定义，Task 4/5 使用 — 一致
- `apply_masking(rows) -> list[dict]` 在 Task 2 定义，Task 4/5 使用 — 一致
- `load_quota_config(scope_type, scope_id, user_id) -> QuotaConfig` 在 Task 3 定义，Task 6 使用 — 一致
- `invalidate_masking_cache()` / `invalidate_quota_cache()` 在 Task 2/3 定义，Task 7/8 override 使用 — 一致
- 前端 `Api.Bi.BiMaskingRuleOperateParams` / `BiQuotaConfigOperateParams` 在 Task 10 定义，Task 11/13/14 使用 — 一致
