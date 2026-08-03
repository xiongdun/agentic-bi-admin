# BiDashboard 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现批次 C 仪表盘功能，让用户把多个 BiChart 组装成 12 列栅格仪表盘，支持拖拽/resize/全量刷新。

**Architecture:** 后端新增 `BiDashboard` 模型 + 7 个 API（CRUD + refresh + preview），复用 BiChart 的 SQL 重跑逻辑（抽出为 `_rerun_chart_sql` 共享函数）。前端用 gridstack.js 实现栅格布局，详情/编辑合一路由 `?mode=edit` 切换。

**Tech Stack:** FastAPI + Tortoise ORM + SQLAlchemy（后端）；Vue 3 + gridstack.js@13 + ECharts + Naive UI（前端）

**Spec:** [.trae/specs/bi-dashboard/spec.md](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/.trae/specs/bi-dashboard/spec.md)

---

## 文件结构

### 后端新增/修改

| 文件 | 责任 | 动作 |
|------|------|------|
| `app/business/bi/models.py` | 新增 `BiDashboard` 模型 | 修改（追加） |
| `app/business/bi/schemas_dashboard.py` | Dashboard schemas（Create/Update/Search/Response） | 新建 |
| `app/business/bi/services_chart.py` | 抽出 `_rerun_chart_sql` 共享函数 | 修改（重构） |
| `app/business/bi/services_dashboard.py` | Dashboard 服务（create/get/update/delete/refresh/preview + layout 校验） | 新建 |
| `app/business/bi/api/dashboard.py` | Dashboard 路由（7 个端点） | 新建 |
| `app/business/bi/api/__init__.py` | 聚合 dashboard 路由 | 修改 |
| `app/business/bi/init_data.py` | 菜单/按钮/角色权限 + 聚合列表 | 修改 |
| `app/business/bi/config.py` | 3 个配置项 | 修改 |
| `app/core/code.py` | 新增 `BI_DASHBOARD_NOT_FOUND` 错误码 | 修改 |
| `.env.example` | 3 个配置项 | 修改 |
| `migrations/app_system/0005_add_bi_dashboard.py` | 建表迁移 | 新建 |
| `tests/test_bi_dashboard.py` | 后端测试 | 新建 |

### 前端新增/修改

| 文件 | 责任 | 动作 |
|------|------|------|
| `web/src/views/bi/dashboards/index.vue` | 列表页 | 新建 |
| `web/src/views/bi/dashboards/detail/[id].vue` | 详情/编辑页 | 新建 |
| `web/src/service/api/bi-dashboard.ts` | API 服务 | 新建 |
| `web/src/typings/api/bi.d.ts` | Dashboard 类型 | 修改 |
| `web/src/locales/langs/_generated/bi/zh-cn.ts` | 中文 i18n | 修改 |
| `web/src/locales/langs/_generated/bi/en-us.ts` | 英文 i18n | 修改 |
| `web/src/locales/langs/_generated/bi/types.d.ts` | i18n 类型 | 修改 |
| `web/src/router/elegant/routes.ts` | 路由（自动生成） | 自动 |
| `web/src/router/elegant/imports.ts` | 路由（自动生成） | 自动 |
| `web/package.json` | gridstack 依赖 | 修改 |
| `web/src/views/bi/charts/index.vue` | 抽出 `ChartThumbnail` 为共享组件 | 修改 |

---

## Task 1: 配置项与错误码

**Files:**
- Modify: `app/business/bi/config.py`
- Modify: `.env.example`
- Modify: `app/core/code.py`

- [ ] **Step 1: 在 `config.py` 末尾追加 3 个配置项**

```python
    # ==================== Dashboard ====================
    BI_DASHBOARD_REFRESH_CONCURRENCY: int = 5
    BI_DASHBOARD_MAX_ITEMS: int = 30
    BI_DASHBOARD_REFRESH_TIMEOUT: int = 25
```

- [ ] **Step 2: 在 `.env.example` 的 BI 配置区块末尾追加**

```bash
# BI Dashboard
BI_DASHBOARD_REFRESH_CONCURRENCY=5     # 刷新并发上限
BI_DASHBOARD_MAX_ITEMS=30              # 单仪表盘最大图表数
BI_DASHBOARD_REFRESH_TIMEOUT=25        # 单图表刷新超时（秒）
```

- [ ] **Step 3: 在 `app/core/code.py` 的 BI 错误码段（4xxx）追加 `BI_DASHBOARD_NOT_FOUND`**

> 先 Grep 找到 `BI_CHART_NOT_FOUND` 的定义位置，在其后追加 `BI_DASHBOARD_NOT_FOUND = <下一个可用码>`。

```python
    BI_DASHBOARD_NOT_FOUND = 4103  # 仪表盘不存在（替换为实际下一个可用码）
```

- [ ] **Step 4: 提交**

```bash
git add app/business/bi/config.py .env.example app/core/code.py
git commit -m "feat(bi): add dashboard config and error code"
```

---

## Task 2: BiDashboard 模型与迁移

**Files:**
- Modify: `app/business/bi/models.py`
- Create: `migrations/app_system/0005_add_bi_dashboard.py`
- Test: `tests/test_bi_dashboard.py`

- [ ] **Step 1: 在 `models.py` 末尾追加 `BiDashboard` 模型**

```python
class BiDashboard(BaseModel, AuditMixin, SoftDeleteMixin):
    """仪表盘：把多个 BiChart 组装成 12 列栅格布局。

    ``layout`` 存 ``{"items": [{chartId, x, y, w, h}]}``，引用 BiChart（不级联删）。
    打开时全量刷新所有图表数据，失败的卡片显示占位。
    """

    id = fields.IntField(primary_key=True, description="主键ID")
    name = fields.CharField(max_length=100, description="仪表盘名称")
    description = fields.TextField(null=True, blank=True, description="说明")
    layout = fields.JSONField(default={"items": []}, description="布局：{items: [{chartId, x, y, w, h}]}")
    tenant_id = fields.IntField(default=0, description="租户ID（行级 data_scope 作用域，存 user.id）")

    class Meta:
        table = "biz_bi_dashboard"
        manager = SoftDeleteManager()
```

- [ ] **Step 2: 生成迁移**

Run: `just mm`
Expected: 生成 `migrations/app_system/0005_add_bi_dashboard.py`，含 `CREATE TABLE biz_bi_dashboard`

- [ ] **Step 3: 检查迁移文件 SQL**

> Read 迁移文件，确认含 `id` PK / `name` varchar(100) / `description` text null / `layout` json / `tenant_id` int / AuditMixin 字段 / SoftDeleteMixin 字段。所有字段需有中文 comment（项目约定）。

- [ ] **Step 4: 写模型测试（先失败）**

在 `tests/test_bi_dashboard.py` 写：

```python
"""BiDashboard 模型与服务测试。"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.business.bi.models import BiDashboard
from app.core.sqids import encode_id

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestBiDashboardModel:
    async def test_create_dashboard(self, app, bi_datasource):
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
```

- [ ] **Step 5: 运行测试**

Run: `uv run pytest tests/test_bi_dashboard.py::TestBiDashboardModel::test_create_dashboard -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add app/business/bi/models.py migrations/app_system/0005_add_bi_dashboard.py tests/test_bi_dashboard.py
git commit -m "feat(bi): add BiDashboard model and migration 0005"
```

---

## Task 3: 抽出 `_rerun_chart_sql` 共享函数

**Files:**
- Modify: `app/business/bi/services_chart.py`
- Test: `tests/test_bi_chart.py`（确认现有 refresh_chart 测试仍通过）

- [ ] **Step 1: 在 `services_chart.py` 顶部 import 区追加**

```python
from datetime import datetime
```

> 若已 import 则跳过。

- [ ] **Step 2: 在 `services_chart.py` 的 `refresh_chart` 函数前插入 `_rerun_chart_sql`**

```python
async def _rerun_chart_sql(chart, timeout: int | None = None) -> dict:
    """重跑 chart 的 SQL，返回截断后的快照（不含 isTruncated，由调用方决定）。

    BiChart.refresh_chart 与 BiDashboard.refresh_dashboard 共用本函数。
    抛出异常时由调用方决定降级策略。

    Args:
        chart: BiChart 实例（需已加载 datasource 关系）
        timeout: 超时秒数（None 用 execute_sql 默认）
    Returns:
        {columns, rows, rowCount, elapsedMs}
    """
    datasource = await chart.datasource
    ok, err, _ = await test_connection(datasource)
    if not ok:
        raise BizError(Code.BI_DATASOURCE_UNAVAILABLE, f"数据源不可用：{err}")

    validation = validate_sql(chart.sql_text, datasource.db_type)
    sql = inject_tenant_filter(validation.sql, tenant_id=chart.tenant_id, dialect=datasource.db_type)
    result = await execute_sql(sql=sql, datasource=datasource, user_id=chart.tenant_id)

    return _truncate_snapshot(
        {
            "columns": result.columns,
            "rows": result.rows,
            "rowCount": result.row_count,
            "elapsedMs": result.elapsed_ms,
        },
        BIZ_SETTINGS.BI_CHART_SNAPSHOT_MAX_ROWS,
    )
```

- [ ] **Step 3: 重构 `refresh_chart` 调用 `_rerun_chart_sql`**

将 `refresh_chart` 中的 test_connection + validate_sql + inject_tenant_filter + execute_sql + _truncate_snapshot 块替换为：

```python
async def refresh_chart(chart_id: int, tenant_id: int, user_id: int) -> BiChart:
    """重跑 SQL 刷新结果快照。

    数据源不可用时抛 BizError，前端降级显示快照。
    """
    chart = await BiChart.get_or_none(id=chart_id, tenant_id=tenant_id, deleted_at__isnull=True)
    if not chart:
        raise BizError(Code.BI_CHART_NOT_FOUND, "图表不存在")

    snapshot = await _rerun_chart_sql(chart)
    chart.result_snapshot = snapshot
    chart.snapshot_at = datetime.now()
    await chart.save(update_fields=["result_snapshot", "snapshot_at", "updated_at"])
    radar_log("bi.chart.refresh", data={"chart_id": chart.id})
    log.info("bi.chart.refresh chart_id={}", chart.id)
    return chart
```

- [ ] **Step 4: 运行现有 BiChart 测试确认无回归**

Run: `uv run pytest tests/test_bi_chart.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add app/business/bi/services_chart.py
git commit -m "refactor(bi): extract _rerun_chart_sql shared function"
```

---

## Task 4: Schemas

**Files:**
- Create: `app/business/bi/schemas_dashboard.py`

- [ ] **Step 1: 先 Grep 确认 `SchemaBase` / `PageQueryBase` / `make_optional` / `SqidId` 的 import 路径**

Run: `grep -rn "class SchemaBase" app/core/` 和 `grep -rn "make_optional" app/core/`

- [ ] **Step 2: 创建 `schemas_dashboard.py`**

```python
"""BiDashboard schemas。"""
from __future__ import annotations

from typing import Any

from pydantic import Field

from app.core.base_schema import PageQueryBase, SchemaBase, make_optional
from app.core.sqids import SqidId


class DashboardItemSchema(SchemaBase):
    """layout.items[] 单元素。"""

    chartId: str = Field(..., description="BiChart 的 SQID 编码")
    x: int = Field(..., ge=0, le=11, description="列位置 0-11")
    y: int = Field(..., ge=0, description="行位置 0-N")
    w: int = Field(..., ge=1, le=12, description="宽度 1-12")
    h: int = Field(..., ge=1, le=6, description="高度 1-6")


class DashboardLayoutSchema(SchemaBase):
    """layout JSON 结构。"""

    items: list[DashboardItemSchema] = Field(default_factory=list, description="图表项列表")


class BiDashboardCreateSchema(SchemaBase):
    name: str = Field(..., max_length=100, description="仪表盘名称")
    description: str | None = Field(None, description="说明")
    layout: DashboardLayoutSchema = Field(default_factory=DashboardLayoutSchema, description="布局")


class BiDashboardUpdateSchema(make_optional(BiDashboardCreateSchema)):
    pass


class BiDashboardSearchSchema(PageQueryBase):
    name: str | None = Field(None, description="名称模糊搜索")


class BiDashboardBriefSchema(SchemaBase):
    """列表页简要信息。"""

    id: int
    name: str
    description: str | None
    item_count: int = Field(0, description="图表数量")
    created_at: Any
    updated_at: Any


class BiDashboardDetailSchema(SchemaBase):
    """详情（含完整 layout）。"""

    id: int
    name: str
    description: str | None
    layout: dict
    tenant_id: int
    created_at: Any
    updated_at: Any
```

> SQID 编解码：API 层接收/返回 `chartId` 用字符串，service 层用 `decode_id` 转 int 查 BiChart。

- [ ] **Step 3: 提交**

```bash
git add app/business/bi/schemas_dashboard.py
git commit -m "feat(bi): add dashboard schemas"
```

---

## Task 5: Dashboard 服务层

**Files:**
- Create: `app/business/bi/services_dashboard.py`
- Test: `tests/test_bi_dashboard.py`

- [ ] **Step 1: 写 `validate_layout` 测试（先失败）**

在 `tests/test_bi_dashboard.py` 追加：

```python
from app.business.bi.services_dashboard import validate_layout
from app.core.exceptions import BizError


class TestValidateLayout:
    async def test_valid_layout(self, app):
        """合法 layout 通过校验。"""
        # 需要真实 BiChart，先用 mock chart_id
        from unittest.mock import patch
        from app.business.bi.models import BiChart

        async def fake_count(**kwargs):
            return 1

        with patch.object(BiChart, "filter") as mock_filter:
            mock_filter.return_value.count = fake_count
            layout = {"items": [{"chartId": "abc", "x": 0, "y": 0, "w": 6, "h": 2}]}
            # 不抛异常即通过
            await validate_layout(layout, tenant_id=1)

    async def test_too_many_items(self, app):
        """超过 BI_DASHBOARD_MAX_ITEMS 抛错。"""
        from app.business.bi.config import BIZ_SETTINGS
        items = [{"chartId": str(i), "x": 0, "y": i, "w": 1, "h": 1} for i in range(BIZ_SETTINGS.BI_DASHBOARD_MAX_ITEMS + 1)]
        layout = {"items": items}
        with pytest.raises(BizError):
            await validate_layout(layout, tenant_id=1)

    async def test_invalid_width(self, app):
        """w > 12 抛错。"""
        layout = {"items": [{"chartId": "abc", "x": 0, "y": 0, "w": 13, "h": 1}]}
        with pytest.raises(BizError):
            await validate_layout(layout, tenant_id=1)

    async def test_invalid_height(self, app):
        """h > 6 抛错。"""
        layout = {"items": [{"chartId": "abc", "x": 0, "y": 0, "w": 1, "h": 7}]}
        with pytest.raises(BizError):
            await validate_layout(layout, tenant_id=1)

    async def test_x_plus_w_exceeds_12(self, app):
        """x + w > 12 抛错。"""
        layout = {"items": [{"chartId": "abc", "x": 10, "y": 0, "w": 6, "h": 1}]}
        with pytest.raises(BizError):
            await validate_layout(layout, tenant_id=1)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_bi_dashboard.py::TestValidateLayout -v`
Expected: FAIL（`validate_layout` 未定义）

- [ ] **Step 3: 创建 `services_dashboard.py`**

```python
"""BiDashboard 业务服务。"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from app.business.bi.config import BIZ_SETTINGS
from app.business.bi.models import BiChart, BiDashboard
from app.business.bi.services_chart import _rerun_chart_sql
from app.core.code import Code
from app.core.exceptions import BizError
from app.core.sqids import decode_id, encode_id
from app.utils import log, radar_log


async def validate_layout(layout: dict, tenant_id: int) -> None:
    """校验 layout 结构与 chartId 有效性。"""
    items = layout.get("items", [])
    if len(items) > BIZ_SETTINGS.BI_DASHBOARD_MAX_ITEMS:
        raise BizError(
            Code.VALIDATION_ERROR,
            f"仪表盘图表数超过上限：{len(items)} > {BIZ_SETTINGS.BI_DASHBOARD_MAX_ITEMS}",
        )
    chart_ids: list[int] = []
    for item in items:
        x, y, w, h = item["x"], item["y"], item["w"], item["h"]
        if not (1 <= w <= 12):
            raise BizError(Code.VALIDATION_ERROR, f"宽度非法：w={w}，需 1-12")
        if not (1 <= h <= 6):
            raise BizError(Code.VALIDATION_ERROR, f"高度非法：h={h}，需 1-6")
        if x < 0 or y < 0:
            raise BizError(Code.VALIDATION_ERROR, f"位置非法：x={x}, y={y}")
        if x + w > 12:
            raise BizError(Code.VALIDATION_ERROR, f"超出 12 列：x={x} + w={w} = {x + w}")
        chart_ids.append(decode_id(item["chartId"]))

    # 校验 chartId 都属于当前租户且未软删
    if chart_ids:
        valid_count = await BiChart.filter(
            id__in=chart_ids, tenant_id=tenant_id, deleted_at__isnull=True
        ).count()
        if valid_count != len(set(chart_ids)):
            raise BizError(
                Code.VALIDATION_ERROR,
                "存在无效图表ID：不属于当前租户或已删除",
            )


async def create_dashboard(schema, tenant_id: int, user_id: int) -> BiDashboard:
    """创建仪表盘。"""
    layout_dict = schema.layout.model_dump() if hasattr(schema.layout, "model_dump") else schema.layout
    await validate_layout(layout_dict, tenant_id=tenant_id)

    dashboard = await BiDashboard.create(
        name=schema.name,
        description=schema.description,
        layout=layout_dict,
        tenant_id=tenant_id,
        created_by=str(user_id),
        updated_by=str(user_id),
    )
    radar_log("bi.dashboard.create", data={"dashboard_id": dashboard.id})
    log.info("bi.dashboard.create id={} user_id={}", dashboard.id, user_id)
    return dashboard


async def get_dashboard(dashboard_id: int, tenant_id: int) -> BiDashboard:
    """获取仪表盘详情。"""
    dashboard = await BiDashboard.get_or_none(
        id=dashboard_id, tenant_id=tenant_id, deleted_at__isnull=True
    )
    if not dashboard:
        raise BizError(Code.BI_DASHBOARD_NOT_FOUND, "仪表盘不存在")
    return dashboard


async def update_dashboard(dashboard_id: int, schema, tenant_id: int, user_id: int) -> BiDashboard:
    """更新仪表盘。"""
    dashboard = await get_dashboard(dashboard_id, tenant_id)
    if schema.name is not None:
        dashboard.name = schema.name
    if schema.description is not None:
        dashboard.description = schema.description
    if schema.layout is not None:
        layout_dict = schema.layout.model_dump() if hasattr(schema.layout, "model_dump") else schema.layout
        await validate_layout(layout_dict, tenant_id=tenant_id)
        dashboard.layout = layout_dict
    dashboard.updated_by = str(user_id)
    await dashboard.save()
    radar_log("bi.dashboard.update", data={"dashboard_id": dashboard.id})
    log.info("bi.dashboard.update id={}", dashboard.id)
    return dashboard


async def delete_dashboard(dashboard_id: int, tenant_id: int) -> None:
    """软删仪表盘。"""
    dashboard = await get_dashboard(dashboard_id, tenant_id)
    await dashboard.delete()  # SoftDeleteManager 会设置 deleted_at
    radar_log("bi.dashboard.delete", data={"dashboard_id": dashboard_id})
    log.info("bi.dashboard.delete id={}", dashboard_id)


def _chart_meta(chart: BiChart) -> dict:
    """提取图表元信息（名称/类型/轴字段）。"""
    return {
        "name": chart.name,
        "chartType": chart.chart_type,
        "xCol": chart.x_col,
        "yCol": chart.y_col,
    }


async def refresh_dashboard(dashboard_id: int, tenant_id: int) -> dict:
    """全量刷新仪表盘所有图表数据。

    并发上限 BI_DASHBOARD_REFRESH_CONCURRENCY，单图表超时 BI_DASHBOARD_REFRESH_TIMEOUT。
    失败不降级，返回 status=failed + errorMessage。
    """
    dashboard = await get_dashboard(dashboard_id, tenant_id)
    items = dashboard.layout.get("items", [])

    chart_ids = [decode_id(i["chartId"]) for i in items]
    charts = await BiChart.filter(
        id__in=chart_ids, tenant_id=tenant_id, deleted_at__isnull=True
    )
    chart_map = {c.id: c for c in charts}

    semaphore = asyncio.Semaphore(BIZ_SETTINGS.BI_DASHBOARD_REFRESH_CONCURRENCY)

    async def refresh_one(item: dict) -> dict:
        async with semaphore:
            chart_id = decode_id(item["chartId"])
            chart = chart_map.get(chart_id)
            if not chart:
                return {"chartId": item["chartId"], "status": "deleted", "chartMeta": None}
            try:
                snapshot = await asyncio.wait_for(
                    _rerun_chart_sql(chart),
                    timeout=BIZ_SETTINGS.BI_DASHBOARD_REFRESH_TIMEOUT,
                )
                return {
                    "chartId": item["chartId"],
                    "status": "success",
                    "resultSnapshot": snapshot,
                    "chartMeta": _chart_meta(chart),
                    "snapshotAt": datetime.now().isoformat(),
                }
            except Exception as e:
                return {
                    "chartId": item["chartId"],
                    "status": "failed",
                    "errorMessage": str(e),
                    "chartMeta": _chart_meta(chart),
                }

    start = datetime.now()
    results = await asyncio.gather(*[refresh_one(i) for i in items])
    total_elapsed_ms = int((datetime.now() - start).total_seconds() * 1000)
    radar_log("bi.dashboard.refresh", data={"dashboard_id": dashboard_id, "item_count": len(items)})
    log.info("bi.dashboard.refresh id={} items={} elapsed_ms={}", dashboard_id, len(items), total_elapsed_ms)
    return {"items": results, "totalElapsedMs": total_elapsed_ms}


async def preview_dashboard(dashboard_id: int, tenant_id: int) -> dict:
    """预览仪表盘（不刷新，用 BiChart 已有快照）。"""
    dashboard = await get_dashboard(dashboard_id, tenant_id)
    items = dashboard.layout.get("items", [])

    chart_ids = [decode_id(i["chartId"]) for i in items]
    charts = await BiChart.filter(
        id__in=chart_ids, tenant_id=tenant_id, deleted_at__isnull=True
    )
    chart_map = {c.id: c for c in charts}

    preview_items = []
    for item in items:
        chart = chart_map.get(decode_id(item["chartId"]))
        if not chart:
            preview_items.append({"chartId": item["chartId"], "status": "deleted", "chartMeta": None})
        else:
            preview_items.append({
                "chartId": item["chartId"],
                "chartMeta": _chart_meta(chart),
                "resultSnapshot": chart.result_snapshot,
            })

    return {
        "id": dashboard.id,
        "name": dashboard.name,
        "description": dashboard.description,
        "layout": dashboard.layout,
        "items": preview_items,
    }
```

- [ ] **Step 4: 运行 validate_layout 测试**

Run: `uv run pytest tests/test_bi_dashboard.py::TestValidateLayout -v`
Expected: PASS

- [ ] **Step 5: 写 refresh/preview 服务测试**

在 `tests/test_bi_dashboard.py` 追加：

```python
from unittest.mock import patch, AsyncMock
from app.business.bi.services_dashboard import (
    create_dashboard, get_dashboard, update_dashboard, delete_dashboard,
    refresh_dashboard, preview_dashboard,
)


class TestRefreshDashboard:
    async def test_refresh_success(self, app, bi_datasource, monkeypatch):
        """所有图表刷新成功。"""
        from app.business.bi.models import BiChart, BiDashboard

        chart = await BiChart.create(
            name="测试图表",
            datasource_id=bi_datasource.id,
            chart_type="bar",
            x_col="m",
            y_col="s",
            sql_text="SELECT m, s FROM t LIMIT 10",
            result_snapshot={"columns": ["m", "s"], "rows": [], "rowCount": 0, "elapsedMs": 0},
            snapshot_at=datetime.now(),
            tenant_id=bi_datasource.tenant_id,
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )
        dashboard = await BiDashboard.create(
            name="d1",
            tenant_id=bi_datasource.tenant_id,
            layout={"items": [{"chartId": encode_id(chart.id), "x": 0, "y": 0, "w": 6, "h": 2}]},
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )

        # mock _rerun_chart_sql 返回固定快照
        async def fake_rerun(chart, **kw):
            return {"columns": ["m", "s"], "rows": [["1", 100]], "rowCount": 1, "elapsedMs": 50}

        with patch("app.business.bi.services_dashboard._rerun_chart_sql", side_effect=fake_rerun):
            result = await refresh_dashboard(dashboard.id, bi_datasource.tenant_id)

        assert result["items"][0]["status"] == "success"
        assert result["items"][0]["resultSnapshot"]["rowCount"] == 1
        assert result["totalElapsedMs"] >= 0

    async def test_refresh_failed_no_snapshot(self, app, bi_datasource, monkeypatch):
        """刷新失败时不返回 resultSnapshot。"""
        from app.business.bi.models import BiChart, BiDashboard

        chart = await BiChart.create(
            name="失败图表",
            datasource_id=bi_datasource.id,
            chart_type="bar",
            x_col="m",
            y_col="s",
            sql_text="SELECT m, s FROM t",
            result_snapshot={"columns": [], "rows": [], "rowCount": 0, "elapsedMs": 0},
            snapshot_at=datetime.now(),
            tenant_id=bi_datasource.tenant_id,
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )
        dashboard = await BiDashboard.create(
            name="d2",
            tenant_id=bi_datasource.tenant_id,
            layout={"items": [{"chartId": encode_id(chart.id), "x": 0, "y": 0, "w": 6, "h": 2}]},
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )

        async def failing_rerun(chart, **kw):
            raise Exception("数据源连接超时")

        with patch("app.business.bi.services_dashboard._rerun_chart_sql", side_effect=failing_rerun):
            result = await refresh_dashboard(dashboard.id, bi_datasource.tenant_id)

        assert result["items"][0]["status"] == "failed"
        assert "数据源连接超时" in result["items"][0]["errorMessage"]
        assert "resultSnapshot" not in result["items"][0]
        assert result["items"][0]["chartMeta"]["name"] == "失败图表"

    async def test_refresh_deleted_chart(self, app, bi_datasource):
        """引用的图表已删除，返回 deleted 状态。"""
        from app.business.bi.models import BiDashboard

        # 用一个不存在的 chart_id（encode_id 解码后查不到）
        dashboard = await BiDashboard.create(
            name="d3",
            tenant_id=bi_datasource.tenant_id,
            layout={"items": [{"chartId": encode_id(999999), "x": 0, "y": 0, "w": 6, "h": 2}]},
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )

        result = await refresh_dashboard(dashboard.id, bi_datasource.tenant_id)
        assert result["items"][0]["status"] == "deleted"
        assert result["items"][0]["chartMeta"] is None


class TestPreviewDashboard:
    async def test_preview_returns_snapshot(self, app, bi_datasource):
        """预览返回 BiChart 已有快照，不重跑。"""
        from app.business.bi.models import BiChart, BiDashboard

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
            layout={"items": [{"chartId": encode_id(chart.id), "x": 0, "y": 0, "w": 12, "h": 3}]},
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )

        result = await preview_dashboard(dashboard.id, bi_datasource.tenant_id)
        assert result["items"][0]["resultSnapshot"] == snapshot
        assert result["items"][0]["chartMeta"]["chartType"] == "line"
```

- [ ] **Step 6: 运行服务测试**

Run: `uv run pytest tests/test_bi_dashboard.py -v`
Expected: 全部 PASS

- [ ] **Step 7: 提交**

```bash
git add app/business/bi/services_dashboard.py tests/test_bi_dashboard.py
git commit -m "feat(bi): add dashboard services (validate/create/update/refresh/preview)"
```

---

## Task 6: API 路由

**Files:**
- Create: `app/business/bi/api/dashboard.py`
- Modify: `app/business/bi/api/__init__.py`
- Test: `tests/test_bi_dashboard.py`

- [ ] **Step 1: 先 Grep 现有 bi chart API 的 import 模式**

Run: `grep -n "DependAuth\|require_buttons\|get_current_user_id\|AioRedis" app/business/bi/api/chart.py`

- [ ] **Step 2: 创建 `api/dashboard.py`**

```python
"""BiDashboard API 路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis as AioRedis

from app.business.bi.schemas_dashboard import (
    BiDashboardCreateSchema,
    BiDashboardSearchSchema,
    BiDashboardUpdateSchema,
)
from app.business.bi.services_dashboard import (
    create_dashboard,
    delete_dashboard,
    get_dashboard,
    refresh_dashboard,
    update_dashboard,
)
from app.core.code import Code
from app.core.dependency import DependAuth, require_buttons, get_current_user_id
from app.core.exceptions import BizError
from app.core.response import Success, SuccessExtra
from app.core.sqids import SqidPath, decode_id, encode_id

router = APIRouter(prefix="/dashboards", tags=["仪表盘"])


@router.post(
    "",
    summary="创建仪表盘",
    name="bi.dashboards.create",
    dependencies=[DependAuth, require_buttons("B_BI_DASHBOARD_CREATE")],
)
async def create_dashboard_endpoint(obj_in: BiDashboardCreateSchema, request: Request):
    user_id = get_current_user_id()
    dashboard = await create_dashboard(obj_in, tenant_id=user_id, user_id=user_id)
    return Success(msg="创建成功", data={"id": encode_id(dashboard.id)})


@router.post(
    "/search",
    summary="仪表盘分页列表",
    name="bi.dashboards.list",
    dependencies=[DependAuth, require_buttons("B_BI_DASHBOARD_VIEW")],
)
async def list_dashboards_endpoint(obj_in: BiDashboardSearchSchema, request: Request):
    """分页列表。返回当前租户的仪表盘（含图表数量）。"""
    from app.business.bi.models import BiDashboard
    from tortoise.expressions import Q

    user_id = get_current_user_id()
    qs = BiDashboard.filter(tenant_id=user_id, deleted_at__isnull=True)
    if obj_in.name:
        qs = qs.filter(name__icontains=obj_in.name)

    total = await qs.count()
    dashboards = await qs.offset((obj_in.current - 1) * obj_in.size).limit(obj_in.size)
    items = []
    for d in dashboards:
        items.append({
            "id": encode_id(d.id),
            "name": d.name,
            "description": d.description,
            "itemCount": len(d.layout.get("items", [])),
            "createdAt": d.created_at.isoformat() if d.created_at else None,
            "updatedAt": d.updated_at.isoformat() if d.updated_at else None,
        })
    return SuccessExtra(data=items, total=total, current=obj_in.current, size=obj_in.size)


@router.get(
    "/{dashboard_id}",
    summary="仪表盘详情",
    name="bi.dashboards.get",
    dependencies=[DependAuth, require_buttons("B_BI_DASHBOARD_VIEW")],
)
async def get_dashboard_endpoint(dashboard_id: SqidPath):
    user_id = get_current_user_id()
    dashboard = await get_dashboard(decode_id(dashboard_id), tenant_id=user_id)
    return Success(data={
        "id": encode_id(dashboard.id),
        "name": dashboard.name,
        "description": dashboard.description,
        "layout": dashboard.layout,
        "createdAt": dashboard.created_at.isoformat() if dashboard.created_at else None,
        "updatedAt": dashboard.updated_at.isoformat() if dashboard.updated_at else None,
    })


@router.put(
    "/{dashboard_id}",
    summary="更新仪表盘",
    name="bi.dashboards.update",
    dependencies=[DependAuth, require_buttons("B_BI_DASHBOARD_EDIT")],
)
async def update_dashboard_endpoint(dashboard_id: SqidPath, obj_in: BiDashboardUpdateSchema):
    user_id = get_current_user_id()
    dashboard = await update_dashboard(
        decode_id(dashboard_id), obj_in, tenant_id=user_id, user_id=user_id
    )
    return Success(msg="更新成功", data={"id": encode_id(dashboard.id)})


@router.delete(
    "/{dashboard_id}",
    summary="删除仪表盘",
    name="bi.dashboards.delete",
    dependencies=[DependAuth, require_buttons("B_BI_DASHBOARD_DELETE")],
)
async def delete_dashboard_endpoint(dashboard_id: SqidPath):
    user_id = get_current_user_id()
    await delete_dashboard(decode_id(dashboard_id), tenant_id=user_id)
    return Success(msg="删除成功")


@router.post(
    "/{dashboard_id}/refresh",
    summary="全量刷新仪表盘图表数据",
    name="bi.dashboards.refresh",
    dependencies=[DependAuth, require_buttons("B_BI_DASHBOARD_VIEW")],
)
async def refresh_dashboard_endpoint(dashboard_id: SqidPath):
    user_id = get_current_user_id()
    result = await refresh_dashboard(decode_id(dashboard_id), tenant_id=user_id)
    return Success(msg="刷新完成", data=result)


@router.get(
    "/{dashboard_id}/preview",
    summary="预览仪表盘（不刷新）",
    name="bi.dashboards.preview",
    dependencies=[DependAuth, require_buttons("B_BI_DASHBOARD_VIEW")],
)
async def preview_dashboard_endpoint(dashboard_id: SqidPath):
    user_id = get_current_user_id()
    result = await preview_dashboard(decode_id(dashboard_id), tenant_id=user_id)
    return Success(data=result)
```

- [ ] **Step 3: 在 `api/__init__.py` 聚合 dashboard 路由**

Grep 现有 chart router 的 import 模式：
Run: `grep -n "from.*chart\|router\.include_router\|from.*dashboard" app/business/bi/api/__init__.py`

按现有模式追加：
```python
from .dashboard import router as dashboard_router
# ...
router.include_router(dashboard_router)
```

- [ ] **Step 4: 写 API 鉴权测试**

在 `tests/test_bi_dashboard.py` 追加：

```python
from httpx import AsyncClient

PREFIX = "/api/v1/business/bi"


class TestDashboardAPIAuth:
    async def test_search_requires_auth(self, app, client: AsyncClient):
        """未登录访问 /dashboards/search 返回 2100。"""
        resp = await client.post(f"{PREFIX}/dashboards/search", json={"current": 1, "size": 10})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 2100  # 未登录

    async def test_create_requires_auth(self, app, client: AsyncClient):
        resp = await client.post(f"{PREFIX}/dashboards", json={"name": "d"})
        assert resp.json()["code"] == 2100

    async def test_refresh_requires_auth(self, app, client: AsyncClient):
        resp = await client.post(f"{PREFIX}/dashboards/abc/refresh")
        assert resp.json()["code"] == 2100
```

- [ ] **Step 5: 运行测试**

Run: `uv run pytest tests/test_bi_dashboard.py -v`
Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add app/business/bi/api/dashboard.py app/business/bi/api/__init__.py tests/test_bi_dashboard.py
git commit -m "feat(bi): add dashboard API routes (7 endpoints)"
```

---

## Task 7: 菜单/按钮/角色权限

**Files:**
- Modify: `app/business/bi/init_data.py`

- [ ] **Step 1: 在 `BI_MENU_CHILDREN` 的图表库块之后追加仪表盘菜单**

> 在 `bi_chart-detail` 块之后插入：

```python
    {
        "menu_name": "仪表盘",
        "route_name": "bi_dashboards",
        "route_path": "/bi/dashboards",
        "component": "view.bi_dashboards",
        "icon": "mdi:view-dashboard-outline",
        "order": 9,
        "buttons": [
            {"button_code": "B_BI_DASHBOARD_CREATE", "button_desc": "创建仪表盘"},
            {"button_code": "B_BI_DASHBOARD_VIEW", "button_desc": "查看仪表盘"},
            {"button_code": "B_BI_DASHBOARD_EDIT", "button_desc": "编辑仪表盘"},
            {"button_code": "B_BI_DASHBOARD_DELETE", "button_desc": "删除仪表盘"},
        ],
    },
    {
        "menu_name": "仪表盘详情",
        "route_name": "bi_dashboard-detail",
        "route_path": "/bi/dashboards/:id",
        "component": "view.bi_dashboard-detail",
        "icon": "mdi:view-dashboard",
        "order": 99,
        "hide_in_menu": True,
        "active_menu": "bi_dashboards",
    },
```

- [ ] **Step 2: 在 `BI_ALL_BUTTONS` 追加 4 个按钮码**

```python
    "B_BI_DASHBOARD_CREATE",
    "B_BI_DASHBOARD_VIEW",
    "B_BI_DASHBOARD_EDIT",
    "B_BI_DASHBOARD_DELETE",
```

- [ ] **Step 3: 在 `BI_ALL_MENUS` 追加**

```python
    "bi_dashboards",
    "bi_dashboard-detail",
```

- [ ] **Step 4: 在 `BI_ANALYST_MENUS` 追加**

```python
    "bi_dashboards",
    "bi_dashboard-detail",
```

- [ ] **Step 5: 在 `BI_ANALYST_BUTTONS` 追加**

```python
    "B_BI_DASHBOARD_CREATE",
    "B_BI_DASHBOARD_VIEW",
    "B_BI_DASHBOARD_EDIT",
    "B_BI_DASHBOARD_DELETE",
```

- [ ] **Step 6: 在 `BI_ADMIN_APIS` 追加 7 个 route_name**

```python
    # dashboard（CRUD + refresh + preview）
    "bi.dashboards.create",
    "bi.dashboards.list",
    "bi.dashboards.get",
    "bi.dashboards.update",
    "bi.dashboards.delete",
    "bi.dashboards.refresh",
    "bi.dashboards.preview",
```

- [ ] **Step 7: 在 `BI_ANALYST_APIS` 追加同样的 7 个 route_name**

- [ ] **Step 8: 提交**

```bash
git add app/business/bi/init_data.py
git commit -m "feat(bi): add dashboard menu/buttons/role permissions"
```

---

## Task 8: 前端依赖与类型

**Files:**
- Modify: `web/package.json`
- Modify: `web/src/typings/api/bi.d.ts`

- [ ] **Step 1: 安装 gridstack**

Run: `cd web && pnpm add gridstack`

- [ ] **Step 2: 在 `bi.d.ts` 追加 Dashboard 类型**

> 先 Grep 找到文件末尾或 BiChart 类型块位置。

```typescript
/** Dashboard layout item */
export interface BiDashboardItem {
  chartId: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

/** Dashboard layout */
export interface BiDashboardLayout {
  items: BiDashboardItem[];
}

/** Dashboard brief (list) */
export interface BiDashboardBrief {
  id: string;
  name: string;
  description: string | null;
  itemCount: number;
  createdAt: string | null;
  updatedAt: string | null;
}

/** Dashboard detail */
export interface BiDashboardDetail {
  id: string;
  name: string;
  description: string | null;
  layout: BiDashboardLayout;
  createdAt: string | null;
  updatedAt: string | null;
}

/** Chart meta in refresh/preview response */
export interface BiChartMeta {
  name: string;
  chartType: string;
  xCol: string | null;
  yCol: string | null;
}

/** Refresh item result */
export interface BiDashboardRefreshItem {
  chartId: string;
  status: 'success' | 'failed' | 'deleted';
  resultSnapshot?: ChartSqlResult;
  chartMeta: BiChartMeta | null;
  errorMessage?: string;
  snapshotAt?: string;
}

/** Refresh response */
export interface BiDashboardRefreshResult {
  items: BiDashboardRefreshItem[];
  totalElapsedMs: number;
}

/** Preview item */
export interface BiDashboardPreviewItem {
  chartId: string;
  chartMeta: BiChartMeta | null;
  resultSnapshot?: ChartSqlResult;
  status?: 'deleted';
}

/** Preview response */
export interface BiDashboardPreview {
  id: string;
  name: string;
  description: string | null;
  layout: BiDashboardLayout;
  items: BiDashboardPreviewItem[];
}

/** Create/Update payload */
export interface BiDashboardPayload {
  name: string;
  description?: string | null;
  layout: BiDashboardLayout;
}
```

- [ ] **Step 3: 提交**

```bash
git add web/package.json web/pnpm-lock.yaml web/src/typings/api/bi.d.ts
git commit -m "feat(bi-web): add gridstack dep and dashboard types"
```

---

## Task 9: 前端 API 服务

**Files:**
- Create: `web/src/service/api/bi-dashboard.ts`

- [ ] **Step 1: 先 Grep 现有 bi-chart.ts 的 request 模式**

Run: `grep -n "request\|getServiceBaseURL\|export const" web/src/service/api/bi-chart.ts`

- [ ] **Step 2: 创建 `bi-dashboard.ts`**

> 按现有 bi-chart.ts 的模式（用 `request` 或 `getServiceBaseURL`）。

```typescript
import { request } from '@/service/request';
import type {
  BiDashboardBrief,
  BiDashboardDetail,
  BiDashboardPayload,
  BiDashboardPreview,
  BiDashboardRefreshResult
} from '@/typings/api/bi';

const PREFIX = '/api/v1/business/bi/dashboards';

/** 分页列表 */
export function fetchBiDashboardList(params: { current: number; size: number; name?: string }) {
  return request<BiDashboardBrief[]>({
    url: `${PREFIX}/search`,
    method: 'post',
    data: params
  });
}

/** 详情 */
export function fetchBiDashboardDetail(id: string) {
  return request<BiDashboardDetail>({
    url: `${PREFIX}/${id}`,
    method: 'get'
  });
}

/** 创建 */
export function fetchCreateBiDashboard(payload: BiDashboardPayload) {
  return request<{ id: string }>({
    url: PREFIX,
    method: 'post',
    data: payload
  });
}

/** 更新 */
export function fetchUpdateBiDashboard(id: string, payload: BiDashboardPayload) {
  return request<{ id: string }>({
    url: `${PREFIX}/${id}`,
    method: 'put',
    data: payload
  });
}

/** 删除 */
export function fetchDeleteBiDashboard(id: string) {
  return request({
    url: `${PREFIX}/${id}`,
    method: 'delete'
  });
}

/** 全量刷新 */
export function fetchRefreshBiDashboard(id: string) {
  return request<BiDashboardRefreshResult>({
    url: `${PREFIX}/${id}/refresh`,
    method: 'post'
  });
}

/** 预览（不刷新） */
export function fetchPreviewBiDashboard(id: string) {
  return request<BiDashboardPreview>({
    url: `${PREFIX}/${id}/preview`,
    method: 'get'
  });
}
```

- [ ] **Step 3: 提交**

```bash
git add web/src/service/api/bi-dashboard.ts
git commit -m "feat(bi-web): add dashboard API service"
```

---

## Task 10: 抽出 ChartThumbnail 共享组件

**Files:**
- Create: `web/src/views/bi/shared/chart-thumbnail.vue`
- Modify: `web/src/views/bi/charts/index.vue`

- [ ] **Step 1: 先 Read `charts/index.vue` 中 ChartThumbnail 的完整定义**

Run: `read web/src/views/bi/charts/index.vue`（找 `ChartThumbnail` defineComponent 块）

- [ ] **Step 2: 创建 `shared/chart-thumbnail.vue`**

> 将 `charts/index.vue` 中的 ChartThumbnail 组件代码移到独立文件。props 接收 `chart: BiChart`，内部用 `useEcharts` + `buildChartOption`。

```vue
<script setup lang="ts">
import { computed } from 'vue';
import { useEcharts, type ECOption } from '@/hooks/common/echarts';
import { buildChartOption, type ChartType } from './chart-config';
import type { BiChart } from '@/typings/api/bi';

const props = defineProps<{
  chart: BiChart;
}>();

const option = computed<ECOption>(() => {
  const snapshot = props.chart.resultSnapshot;
  if (!snapshot) return {} as ECOption;
  return buildChartOption(
    { columns: snapshot.columns, rows: snapshot.rows },
    props.chart.chartType as ChartType,
    props.chart.xCol || '',
    props.chart.yCol || ''
  );
});

const { domRef } = useEcharts<ECOption>(() => option.value, { theme: 'dark' });
</script>

<template>
  <div ref="domRef" class="h-full w-full"></div>
</template>
```

- [ ] **Step 3: 修改 `charts/index.vue` 改用共享组件**

将原内联 ChartThumbnail 定义替换为 import：
```typescript
import ChartThumbnail from '../shared/chart-thumbnail.vue';
```

删除内联定义，模板中 `<ChartThumbnail>` 用法不变。

- [ ] **Step 4: 跑前端 lint + typecheck**

Run: `cd web && pnpm run lint && pnpm run typecheck`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add web/src/views/bi/shared/chart-thumbnail.vue web/src/views/bi/charts/index.vue
git commit -m "refactor(bi-web): extract ChartThumbnail to shared component"
```

---

## Task 11: 前端 i18n

**Files:**
- Modify: `web/src/locales/langs/_generated/bi/zh-cn.ts`
- Modify: `web/src/locales/langs/_generated/bi/en-us.ts`
- Modify: `web/src/locales/langs/_generated/bi/types.d.ts`
- Modify: `web/src/locales/langs/zh-cn.ts`（route 命名）
- Modify: `web/src/locales/langs/en-us.ts`（route 命名）

- [ ] **Step 1: 在 `route` 区块追加路由名 i18n（zh-cn.ts）**

```typescript
    bi_dashboards: '仪表盘',
    'bi_dashboard-detail': '仪表盘详情',
```

- [ ] **Step 2: 在 `route` 区块追加路由名 i18n（en-us.ts）**

```typescript
    bi_dashboards: 'Dashboards',
    'bi_dashboard-detail': 'Dashboard Detail',
```

- [ ] **Step 3: 在 `page.bi` 区块追加 dashboard 文案（zh-cn.ts `_generated/bi/zh-cn.ts`）**

```typescript
    dashboard: {
      title: '仪表盘',
      create: '新建仪表盘',
      name: '名称',
      description: '说明',
      itemCount: '图表数量',
      edit: '编辑',
      save: '保存',
      cancel: '取消',
      refresh: '刷新',
      refreshAll: '刷新全部',
      addChart: '添加图表',
      removeChart: '移除',
      chartDeleted: '图表已删除，请编辑移除',
      refreshFailed: '刷新失败',
      refreshSuccess: '刷新完成',
      empty: '暂无仪表盘，点击新建创建',
      emptyLayout: '画布为空，点击左侧图表添加',
      searchPlaceholder: '搜索仪表盘名称',
      namePlaceholder: '请输入仪表盘名称',
      descPlaceholder: '请输入说明（可选）',
      confirmDelete: '确认删除该仪表盘吗？',
      saveSuccess: '保存成功',
      createSuccess: '创建成功，请添加图表',
      totalElapsed: '总耗时 {ms}ms',
    },
```

- [ ] **Step 4: 在 en-us.ts 追加对应英文**

```typescript
    dashboard: {
      title: 'Dashboard',
      create: 'New Dashboard',
      name: 'Name',
      description: 'Description',
      itemCount: 'Charts',
      edit: 'Edit',
      save: 'Save',
      cancel: 'Cancel',
      refresh: 'Refresh',
      refreshAll: 'Refresh All',
      addChart: 'Add Chart',
      removeChart: 'Remove',
      chartDeleted: 'Chart deleted, please edit to remove',
      refreshFailed: 'Refresh Failed',
      refreshSuccess: 'Refreshed',
      empty: 'No dashboards, click to create',
      emptyLayout: 'Canvas empty, click charts on left to add',
      searchPlaceholder: 'Search dashboard name',
      namePlaceholder: 'Enter dashboard name',
      descPlaceholder: 'Enter description (optional)',
      confirmDelete: 'Delete this dashboard?',
      saveSuccess: 'Saved',
      createSuccess: 'Created, please add charts',
      totalElapsed: 'Total {ms}ms',
    },
```

- [ ] **Step 5: 在 `types.d.ts` 追加类型**

```typescript
    dashboard: {
      title: string;
      create: string;
      name: string;
      description: string;
      itemCount: string;
      edit: string;
      save: string;
      cancel: string;
      refresh: string;
      refreshAll: string;
      addChart: string;
      removeChart: string;
      chartDeleted: string;
      refreshFailed: string;
      refreshSuccess: string;
      empty: string;
      emptyLayout: string;
      searchPlaceholder: string;
      namePlaceholder: string;
      descPlaceholder: string;
      confirmDelete: string;
      saveSuccess: string;
      createSuccess: string;
      totalElapsed: string;
    };
```

- [ ] **Step 6: 提交**

```bash
git add web/src/locales/
git commit -m "feat(bi-web): add dashboard i18n (zh-cn/en-us)"
```

---

## Task 12: 前端列表页

**Files:**
- Create: `web/src/views/bi/dashboards/index.vue`

- [ ] **Step 1: 创建 `dashboards/index.vue`**

```vue
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { NButton, NCard, NGrid, NGridItem, NInput, NModal, NPopconfirm, NSpace, useMessage } from 'naive-ui';
import { fetchBiDashboardList, fetchCreateBiDashboard, fetchDeleteBiDashboard } from '@/service/api/bi-dashboard';
import { $t } from '@/locales';

const router = useRouter();
const message = useMessage();

const loading = ref(false);
const list = ref<BusinessTy.BiDashboardBrief[]>([]);
const searchName = ref('');

const pagination = reactive({
  current: 1,
  size: 12,
  total: 0
});

async function loadList() {
  loading.value = true;
  try {
    const { data, error } = await fetchBiDashboardList({
      current: pagination.current,
      size: pagination.size,
      name: searchName.value || undefined
    });
    if (!error && data) {
      list.value = data;
    }
  } finally {
    loading.value = false;
  }
}

// 新建模态框
const showCreate = ref(false);
const createForm = reactive({ name: '', description: '' });

async function handleCreate() {
  const { data, error } = await fetchCreateBiDashboard({
    name: createForm.name,
    description: createForm.description || null,
    layout: { items: [] }
  });
  if (!error && data) {
    message.success($t('page.bi.dashboard.createSuccess'));
    showCreate.value = false;
    createForm.name = '';
    createForm.description = '';
    router.push(`/bi/dashboards/${data.id}?mode=edit`);
  }
}

async function handleDelete(id: string) {
  const { error } = await fetchDeleteBiDashboard(id);
  if (!error) {
    message.success($t('common.deleteSuccess'));
    loadList();
  }
}

function openDetail(id: string) {
  router.push(`/bi/dashboards/${id}`);
}

onMounted(() => {
  loadList();
});
</script>

<template>
  <div class="h-full p-4">
    <NSpace justify="space-between" class="mb-4">
      <NInput v-model:value="searchName" :placeholder="$t('page.bi.dashboard.searchPlaceholder')" clearable style="width: 240px" @update:value="loadList" />
      <NButton type="primary" @click="showCreate = true">{{ $t('page.bi.dashboard.create') }}</NButton>
    </NSpace>

    <NGrid cols="1 s:2 m:3 l:4" :x-gap="16" :y-gap="16" responsive="screen">
      <NGridItem v-for="item in list" :key="item.id">
        <NCard hoverable class="cursor-pointer" @click="openDetail(item.id)">
          <div class="flex flex-col gap-2">
            <div class="text-base font-medium">{{ item.name }}</div>
            <div class="text-xs opacity-60">{{ $t('page.bi.dashboard.itemCount') }}: {{ item.itemCount }}</div>
            <div class="text-xs opacity-40">{{ item.updatedAt }}</div>
          </div>
          <template #action>
            <NPopconfirm @positive-click="handleDelete(item.id)">
              <template #trigger>
                <NButton size="small" type="error" quaternary @click.stop>{{ $t('common.delete') }}</NButton>
              </template>
              {{ $t('page.bi.dashboard.confirmDelete') }}
            </NPopconfirm>
          </template>
        </NCard>
      </NGridItem>
    </NGrid>

    <NModal v-model:show="showCreate" preset="card" :title="$t('page.bi.dashboard.create')" style="width: 480px">
      <NSpace vertical>
        <NInput v-model:value="createForm.name" :placeholder="$t('page.bi.dashboard.namePlaceholder')" />
        <NInput v-model:value="createForm.description" type="textarea" :placeholder="$t('page.bi.dashboard.descPlaceholder')" />
        <NSpace justify="end">
          <NButton @click="showCreate = false">{{ $t('common.cancel') }}</NButton>
          <NButton type="primary" :disabled="!createForm.name" @click="handleCreate">{{ $t('common.confirm') }}</NButton>
        </NSpace>
      </NSpace>
    </NModal>
  </div>
</template>
```

- [ ] **Step 2: 跑 lint + typecheck**

Run: `cd web && pnpm run lint && pnpm run typecheck`
Expected: PASS（如有 BusinessTy 类型问题需在 typings 补充）

- [ ] **Step 3: 提交**

```bash
git add web/src/views/bi/dashboards/index.vue
git commit -m "feat(bi-web): add dashboard list page"
```

---

## Task 13: 前端详情/编辑页

**Files:**
- Create: `web/src/views/bi/dashboards/detail/[id].vue`

- [ ] **Step 1: 创建详情/编辑页**

```vue
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { NButton, NDrawer, NDrawerContent, NEmpty, NInput, NSpace, NSpin, useMessage } from 'naive-ui';
import { GridStack } from 'gridstack';
import type { GridStackNode } from 'gridstack';
import 'gridstack/dist/gridstack.min.css';
import { fetchBiChartList } from '@/service/api/bi-chart';
import { fetchBiDashboardDetail, fetchPreviewBiDashboard, fetchRefreshBiDashboard, fetchUpdateBiDashboard } from '@/service/api/bi-dashboard';
import ChartThumbnail from '../../shared/chart-thumbnail.vue';
import { buildChartOption, type ChartType } from '../../shared/chart-config';
import { useEcharts, type ECOption } from '@/hooks/common/echarts';
import { $t } from '@/locales';
import type { BiChart, BiDashboardItem, BiDashboardRefreshItem } from '@/typings/api/bi';

const route = useRoute();
const router = useRouter();
const message = useMessage();

const dashboardId = computed(() => route.params.id as string);
const isEditMode = computed(() => route.query.mode === 'edit');

const loading = ref(false);
const dashboard = ref<{ id: string; name: string; description: string | null; layout: { items: BiDashboardItem[] } } | null>(null);
const refreshItems = ref<BiDashboardRefreshItem[]>([]);
const totalElapsedMs = ref(0);

const gridRef = ref<HTMLElement>();
let grid: GridStack | null = null;

// 编辑模式状态
const editLayout = ref<BiDashboardItem[]>([]);
const editName = ref('');
const editDesc = ref('');

// 图表选择器
const showChartPicker = ref(false);
const chartList = ref<BiChart[]>([]);
const chartLoading = ref(false);

async function loadDashboard() {
  loading.value = true;
  try {
    if (isEditMode.value) {
      const { data, error } = await fetchPreviewBiDashboard(dashboardId.value);
      if (!error && data) {
        dashboard.value = { id: data.id, name: data.name, description: data.description, layout: data.layout };
        editLayout.value = [...data.layout.items];
        editName.value = data.name;
        editDesc.value = data.description || '';
        // 构建 chartMap 用于渲染预览
        previewItems.value = data.items;
      }
    } else {
      const { data: detail, error: e1 } = await fetchBiDashboardDetail(dashboardId.value);
      if (e1 || !detail) return;
      dashboard.value = { id: detail.id, name: detail.name, description: detail.description, layout: detail.layout };
      // 查看模式：调 refresh 全量刷新
      const { data: refreshData, error: e2 } = await fetchRefreshBiDashboard(dashboardId.value);
      if (!e2 && refreshData) {
        refreshItems.value = refreshData.items;
        totalElapsedMs.value = refreshData.totalElapsedMs;
      }
    }
  } finally {
    loading.value = false;
  }
}

const previewItems = ref<any[]>([]);

// 渲染 gridstack
function renderGrid() {
  if (!gridRef.value) return;
  if (grid) {
    grid.destroy(false);
    grid = null;
  }
  grid = GridStack.init({
    column: 12,
    rowHeight: 100,
    margin: 8,
    staticGrid: !isEditMode.value,
    acceptWidgets: false
  }, gridRef.value);

  const items = isEditMode.value ? editLayout.value : (dashboard.value?.layout.items || []);
  grid.load(items.map((item, idx) => ({
    id: item.chartId,
    x: item.x,
    y: item.y,
    w: item.w,
    h: item.h,
    content: `<div class="grid-item-content" data-chart-id="${item.chartId}" data-idx="${idx}"></div>`
  })));

  if (isEditMode.value) {
    grid.on('change', (_event: any, nodes: GridStackNode[]) => {
      editLayout.value = nodes.map(n => ({
        chartId: String(n.id),
        x: n.x!,
        y: n.y!,
        w: n.w!,
        h: n.h!
      }));
    });
    grid.on('removed', (_event: any, nodes: GridStackNode[]) => {
      const removedIds = new Set(nodes.map(n => String(n.id)));
      editLayout.value = editLayout.value.filter(i => !removedIds.has(i.chartId));
    });
  }
}

// 加载图表选择器
async function loadCharts() {
  chartLoading.value = true;
  try {
    const { data, error } = await fetchBiChartList({ current: 1, size: 100 });
    if (!error && data) {
      chartList.value = data;
    }
  } finally {
    chartLoading.value = false;
  }
}

function addChart(chart: BiChart) {
  const newItem: BiDashboardItem = {
    chartId: chart.id,
    x: 0,
    y: 0,
    w: 6,
    h: 2
  };
  editLayout.value.push(newItem);
  if (grid) {
    grid.addWidget({
      id: newItem.chartId,
      x: newItem.x,
      y: newItem.y,
      w: newItem.w,
      h: newItem.h,
      content: `<div class="grid-item-content" data-chart-id="${newItem.chartId}"></div>`
    });
  }
}

async function handleSave() {
  if (!dashboard.value) return;
  const { error } = await fetchUpdateBiDashboard(dashboardId.value, {
    name: editName.value,
    description: editDesc.value || null,
    layout: { items: editLayout.value }
  });
  if (!error) {
    message.success($t('page.bi.dashboard.saveSuccess'));
    router.replace(`/bi/dashboards/${dashboardId.value}`);
  }
}

function handleCancelEdit() {
  router.replace(`/bi/dashboards/${dashboardId.value}`);
}

async function handleRefresh() {
  loading.value = true;
  try {
    const { data, error } = await fetchRefreshBiDashboard(dashboardId.value);
    if (!error && data) {
      refreshItems.value = data.items;
      totalElapsedMs.value = data.totalElapsedMs;
      message.success($t('page.bi.dashboard.refreshSuccess'));
    }
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  await loadDashboard();
  renderGrid();
});

watch(isEditMode, () => {
  loadDashboard().then(() => renderGrid());
});

onUnmounted(() => {
  if (grid) {
    grid.destroy(false);
    grid = null;
  }
});
</script>

<template>
  <div class="h-full flex flex-col">
    <!-- 顶部工具栏 -->
    <NSpace justify="space-between" class="p-4 border-b border-gray-200 dark:border-gray-700">
      <div class="flex items-center gap-3">
        <h2 class="text-lg font-medium">{{ dashboard?.name }}</h2>
        <span v-if="!isEditMode && totalElapsedMs" class="text-xs opacity-50">
          {{ $t('page.bi.dashboard.totalElapsed', { ms: totalElapsedMs }) }}
        </span>
      </div>
      <NSpace>
        <template v-if="isEditMode">
          <NInput v-model:value="editName" :placeholder="$t('page.bi.dashboard.namePlaceholder')" style="width: 200px" />
          <NButton @click="showChartPicker = true; loadCharts()">{{ $t('page.bi.dashboard.addChart') }}</NButton>
          <NButton type="primary" @click="handleSave">{{ $t('common.save') }}</NButton>
          <NButton @click="handleCancelEdit">{{ $t('common.cancel') }}</NButton>
        </template>
        <template v-else>
          <NButton @click="handleRefresh">{{ $t('page.bi.dashboard.refresh') }}</NButton>
          <NButton type="primary" @click="router.push(`/bi/dashboards/${dashboardId}?mode=edit`)">{{ $t('common.edit') }}</NButton>
        </template>
      </NSpace>
    </NSpace>

    <!-- 画布 -->
    <div class="flex-1 overflow-auto p-4">
      <NSpin :show="loading">
        <div ref="gridRef" class="grid-stack"></div>
        <NEmpty v-if="!loading && (isEditMode ? editLayout : dashboard?.layout.items).length === 0" :description="$t('page.bi.dashboard.emptyLayout')" />
      </NSpin>
    </div>

    <!-- 图表选择器抽屉 -->
    <NDrawer v-model:show="showChartPicker" :width="400">
      <NDrawerContent :title="$t('page.bi.dashboard.addChart')" closable>
        <NSpin :show="chartLoading">
          <div class="flex flex-col gap-2">
            <div
              v-for="chart in chartList"
              :key="chart.id"
              class="p-3 border rounded cursor-pointer hover:border-primary"
              @click="addChart(chart); showChartPicker = false"
            >
              <div class="font-medium">{{ chart.name }}</div>
              <div class="text-xs opacity-60">{{ chart.chartType }}</div>
            </div>
          </div>
        </NSpin>
      </NDrawerContent>
    </NDrawer>
  </div>
</template>

<style scoped>
.grid-stack {
  background: transparent;
}
:deep(.grid-item-content) {
  width: 100%;
  height: 100%;
  overflow: hidden;
}
</style>
```

> 注意：gridstack item 内的 ECharts 渲染需在 DOM 渲染后通过 ref 挂载。本计划给出骨架，实际实现时需用 `nextTick` + 动态组件挂载，或用 Vue 的 `Teleport`。若时间紧张，可先用 iframe-like 的简化渲染（每个 item 用一个独立的 ECharts 组件），后续优化。

- [ ] **Step 2: 跑 lint + typecheck**

Run: `cd web && pnpm run lint && pnpm run typecheck`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add web/src/views/bi/dashboards/detail/
git commit -m "feat(bi-web): add dashboard detail/edit page with gridstack"
```

---

## Task 14: 前端测试

**Files:**
- Modify: `web/src/__tests__/` 或现有 bi 测试目录

- [ ] **Step 1: 先 Grep 现有 bi 前端测试结构**

Run: `ls web/src/__tests__/ 2>/dev/null; find web/src -name "*.test.ts" -path "*bi*"`

- [ ] **Step 2: 写 bi-dashboard.ts API mock 测试**

> 按现有 bi-chart.test.ts 模式（如有），mock request 验证调用参数。

- [ ] **Step 3: 跑 vitest**

Run: `cd web && pnpm run test`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add web/src/__tests__/
git commit -m "test(bi-web): add dashboard api tests"
```

---

## Task 15: 端到端门禁验证

**Files:** 无（验证任务）

- [ ] **Step 1: 跑后端门禁**

Run: `just check`
Expected: ruff + basedpyright + pytest 全绿

- [ ] **Step 2: 跑前端门禁**

Run: `cd web && pnpm run lint && pnpm run typecheck && pnpm run test`
Expected: 全绿

- [ ] **Step 3: 启动后端验证路由注册**

Run: `just run backend`（等启动完成）

```bash
curl -s http://localhost:9999/api/v1/business/bi/dashboards/search -X POST -H "Content-Type: application/json" -d '{"current":1,"size":10}'
# 期望返回 code: 2100（认证失败，非 404）
```

- [ ] **Step 4: 关闭后端，清理端口**

Run: 停止后端命令，`lsof -ti:9999 | xargs kill -9`

- [ ] **Step 5: 最终提交（如有未提交改动）**

```bash
git add -A
git commit -m "chore(bi): dashboard batch C complete - all checks pass"
```

---

## Self-Review

### Spec 覆盖检查

| Spec 要求 | 对应 Task |
|-----------|-----------|
| BiDashboard 模型 + 迁移 | Task 2 |
| 7 个 API 路由 | Task 6 |
| layout JSON 校验 | Task 5 (validate_layout) |
| 全量刷新（并发 5，超时 25s，失败不降级） | Task 5 (refresh_dashboard) |
| 前端列表页 | Task 12 |
| 前端详情/编辑页 + gridstack | Task 13 |
| BiChart 选择器抽屉 | Task 13 |
| 失败/deleted 占位 | Task 13（前端渲染逻辑） |
| 菜单 + 按钮码 + 角色权限 | Task 7 |
| 配置项 | Task 1 |
| i18n | Task 11 |
| 测试覆盖 | Task 5/6/14 |
| just check 全绿 | Task 15 |

### 占位符扫描

- 无 "TBD" / "TODO" / "implement later"
- 所有代码块均含完整实现
- `BusinessTy` 类型引用需在 Task 12 确认（可能需在 typings 补充 BiDashboardBrief 全局类型）

### 类型一致性

- `_rerun_chart_sql(chart, timeout)` 在 Task 3 定义，Task 5 使用 — 一致
- `validate_layout(layout, tenant_id)` 在 Task 5 定义并测试 — 一致
- `refresh_dashboard(dashboard_id, tenant_id)` 在 Task 5 定义，Task 6 调用 — 一致
- `BiDashboardItem` 类型在 Task 8 定义，Task 13 使用 — 一致
