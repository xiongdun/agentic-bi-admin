# BI 报表导出中心 实现计划 — Batch E

**Goal:** 把 BI 图表/仪表盘导出为 Excel/CSV（后端 openpyxl/csv）与 PDF（前端 jspdf + ECharts getDataURL）。

**Architecture:** 无新表。后端新增 `services_export.py` + `api/export.py`（3 接口，行级隔离 + 按钮权限）；前端新增 `bi-export.ts` 服务 + `shared/export-pdf.ts` 工具，图表详情页与仪表盘详情页加导出下拉。数据源一律用 BiChart.result_snapshot（≤1000 行），不重跑 SQL。

**Tech Stack:** FastAPI + openpyxl（后端）；Vue3 + jspdf + ECharts（前端）

**Spec:** [.trae/specs/bi-export/spec.md](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/.trae/specs/bi-export/spec.md)

> ⚠️ 前置说明：Batch D-2（订阅推送）改动未提交，本次改动会叠加在其上；完成后一并提交。

---

## Task 1: 依赖 + 错误码 + 配置

**Files:**
- Modify: `pyproject.toml`
- Modify: `app/core/code.py`
- Modify: `app/business/bi/config.py`

- [ ] **Step 1: `pyproject.toml` 追加 `openpyxl>=3.1.0`**
- [ ] **Step 2: `app/core/code.py` BI 错误码段追加**

```python
    BI_EXPORT_CHART_NOT_FOUND = "4140"  # 图表不存在或越权
    BI_EXPORT_DASHBOARD_NOT_FOUND = "4141"  # 仪表盘不存在或越权
    BI_EXPORT_NO_SNAPSHOT = "4142"  # 图表无结果快照或 rows 为空
```

- [ ] **Step 3: `app/business/bi/config.py` 追加导出配置**

```python
    # ==================== Export ====================
    BI_EXPORT_MAX_ROWS: int = 1000  # 单图表导出行数上限（与快照截断一致）
```

- [ ] **Step 4: 安装依赖**

Run: `cd /Users/Summer/Documents/works/codes/python/agentic-bi-admin && uv sync`

- [ ] **Step 5: 验证**

Run: `uv run python -c "import openpyxl; print(openpyxl.__version__)"`（确认可导入）

---

## Task 2: services_export.py — CSV + Excel 生成

**Files:**
- Create: `app/business/bi/services_export.py`

- [ ] **Step 1: 创建服务模块**

```python
"""BiExport 报表导出服务 — CSV（标准库）+ Excel（openpyxl）生成。

所有导出基于 BiChart.result_snapshot（≤ BI_EXPORT_MAX_ROWS 行），不重跑 SQL。
快照结构：{"columns": [str], "rows": [dict], "rowCount", "elapsedMs"}
行级隔离由 API 层负责（tenant_id 过滤），本模块只做纯数据 → 文件字节。
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from openpyxl import Workbook
from openpyxl.styles import Font

from app.business.bi.config import BIZ_SETTINGS
from app.business.bi.models import BiChart, BiDashboard

# Excel Sheet 名限制：≤31 字符，且不能含 []:*?/\
_INVALID_SHEET_CHARS = set('[]:*?/\\')


def _safe_sheet_name(name: str, max_len: int = 31) -> str:
    """清洗为合法 Excel Sheet 名（去非法字符 + 截断）。"""
    cleaned = ''.join('_' if ch in _INVALID_SHEET_CHARS else ch for ch in (name or '图表'))
    return cleaned[:max_len] or '图表'


def _snapshot_table(snapshot: dict) -> tuple[list[str], list[list]]:
    """从快照提取 (表头, 行列表)。行按 columns 顺序取值，缺失列填空。"""
    columns = [str(c) for c in snapshot.get("columns", [])]
    rows = []
    for row in snapshot.get("rows", []):
        rows.append([row.get(c, "") for c in columns])
    return columns, rows


def build_chart_csv(chart: BiChart) -> bytes:
    """单图表 CSV（UTF-8 BOM，兼容 Excel 中文）。"""
    snapshot = chart.result_snapshot or {}
    columns, rows = _snapshot_table(snapshot)

    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)

    data = buf.getvalue()
    return ("\ufeff" + data).encode("utf-8")


def build_charts_excel(charts: list[BiChart]) -> bytes:
    """批量图表 Excel：每图表一个 Sheet（首行标题 + 表头 + 数据行）。"""
    wb = Workbook()
    wb.remove(wb.active)  # 删除默认空 Sheet

    for chart in charts:
        ws = wb.create_sheet(title=_safe_sheet_name(chart.name))
        ws.append([chart.name])
        ws.append([f"图表类型: {chart.chart_type}"])
        columns, rows = _snapshot_table(chart.result_snapshot or {})
        ws.append([])
        ws.append(columns)
        for row in rows:
            ws.append(row)
        ws.cell(row=1, column=1).font = Font(bold=True)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_dashboard_excel(dashboard: BiDashboard, charts: list[BiChart]) -> bytes:
    """仪表盘 Excel：概览 Sheet + 每图表一个 Sheet。"""
    wb = Workbook()
    wb.remove(wb.active)

    # 概览 Sheet
    overview = wb.create_sheet(title="概览")
    overview.append(["仪表盘名称", dashboard.name])
    overview.append(["描述", dashboard.description or ""])
    overview.append(["图表数", len(charts)])
    overview.append(["导出时间", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")])

    for chart in charts:
        ws = wb.create_sheet(title=_safe_sheet_name(chart.name))
        ws.append([chart.name])
        ws.append([f"图表类型: {chart.chart_type}"])
        columns, rows = _snapshot_table(chart.result_snapshot or {})
        ws.append([])
        ws.append(columns)
        for row in rows:
            ws.append(row)
        ws.cell(row=1, column=1).font = Font(bold=True)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
```

- [ ] **Step 2: 提交**（如用户要求分步提交；默认暂不提交，见前置说明）

---

## Task 3: 后端测试 tests/test_bi_export.py

**Files:**
- Create: `tests/test_bi_export.py`

- [ ] **Step 1: 创建测试**

```python
"""BiExport 报表导出服务与 API 测试。"""
from __future__ import annotations

import io
from datetime import datetime

import pytest
from openpyxl import load_workbook

from app.business.bi.models import BiChart, BiDashboard
from app.business.bi.services_export import (
    build_chart_csv,
    build_charts_excel,
    build_dashboard_excel,
    _safe_sheet_name,
)
from app.core.code import Code

pytestmark = pytest.mark.asyncio(loop_scope="session")

PREFIX = "/api/v1/business/bi/export"


async def _make_chart(bi_datasource, name="导出测试图表", snapshot=None):
    """工具：创建带快照的 BiChart。"""
    return await BiChart.create(
        name=name,
        datasource_id=bi_datasource.id,
        chart_type="bar",
        x_col="m",
        y_col="s",
        sql_text="SELECT 1",
        result_snapshot=snapshot
        or {"columns": ["m", "s"], "rows": [{"m": "1月", "s": 100}, {"m": "2月", "s": 200}], "rowCount": 2, "elapsedMs": 5},
        snapshot_at=datetime.now(),
        tenant_id=bi_datasource.tenant_id,
        created_by=str(bi_datasource.tenant_id),
        updated_by=str(bi_datasource.tenant_id),
    )


class TestBuildChartCsv:
    async def test_csv_content(self, app, bi_datasource):
        """CSV 含 BOM + 表头 + 数据行。"""
        chart = await _make_chart(bi_datasource)
        raw = build_chart_csv(chart)
        text = raw.decode("utf-8")
        assert text.startswith("\ufeff")
        assert "m,s" in text
        assert '"1月",100' in text or "1月,100" in text

    async def test_csv_quotes_special_chars(self, app, bi_datasource):
        """含逗号/引号的值正确转义。"""
        snapshot = {"columns": ["a"], "rows": [{"a": 'x,y"z'}], "rowCount": 1, "elapsedMs": 0}
        chart = await _make_chart(bi_datasource, snapshot=snapshot)
        text = build_chart_csv(chart).decode("utf-8")
        assert '"x,y""z"' in text

    async def test_csv_empty_rows(self, app, bi_datasource):
        """rows 为空也输出表头。"""
        snapshot = {"columns": ["a"], "rows": [], "rowCount": 0, "elapsedMs": 0}
        chart = await _make_chart(bi_datasource, snapshot=snapshot)
        text = build_chart_csv(chart).decode("utf-8")
        assert text.endswith("a\n")


class TestBuildExcel:
    async def test_charts_excel_multi_sheet(self, app, bi_datasource):
        """批量图表 Excel：每图表一个 Sheet，Sheet 名合法。"""
        c1 = await _make_chart(bi_datasource, name="销售:趋势")
        c2 = await _make_chart(bi_datasource, name="用户*增长")
        raw = build_charts_excel([c1, c2])
        wb = load_workbook(io.BytesIO(raw))
        assert set(wb.sheetnames) == {"销售_趋势", "用户_增长"}
        ws = wb["销售_趋势"]
        assert ws["A1"].value == "销售:趋势"
        assert ws.cell(row=4, column=1).value == "m"  # 表头行
        assert ws.cell(row=5, column=2).value == 100

    async def test_sheet_name_truncation(self, app):
        """超长 Sheet 名截断到 31 字符。"""
        name = _safe_sheet_name("x" * 50)
        assert len(name) == 31

    async def test_dashboard_excel_has_overview(self, app, bi_datasource):
        """仪表盘 Excel：概览 Sheet + 每图表 Sheet。"""
        chart = await _make_chart(bi_datasource)
        dashboard = await BiDashboard.create(
            name="经营日报",
            description="每日更新",
            tenant_id=bi_datasource.tenant_id,
            layout={"items": [{"chartId": str(chart.id), "x": 0, "y": 0, "w": 6, "h": 2}]},
            created_by=str(bi_datasource.tenant_id),
            updated_by=str(bi_datasource.tenant_id),
        )
        raw = build_dashboard_excel(dashboard, [chart])
        wb = load_workbook(io.BytesIO(raw))
        assert "概览" in wb.sheetnames
        assert chart.name in wb.sheetnames
        overview = wb["概览"]
        assert overview["A1"].value == "仪表盘名称"
        assert overview["B1"].value == "经营日报"


# ===================== API 鉴权 =====================


class TestExportAPIAuth:
    async def test_chart_csv_requires_auth(self, app, client):
        resp = await client.get(f"{PREFIX}/charts/abc/csv")
        assert resp.json()["code"] == Code.INVALID_TOKEN

    async def test_charts_excel_requires_auth(self, app, client):
        resp = await client.post(f"{PREFIX}/charts/excel", json={"chartIds": ["abc"]})
        assert resp.json()["code"] == Code.INVALID_TOKEN

    async def test_dashboard_excel_requires_auth(self, app, client):
        resp = await client.post(f"{PREFIX}/dashboards/abc/excel")
        assert resp.json()["code"] == Code.INVALID_TOKEN
```

- [ ] **Step 2: 运行测试**

Run: `uv run pytest tests/test_bi_export.py -v`
Expected: 通过（Task 2 的 services_export 已实现）

---

## Task 4: API 路由 export.py + 挂载 + 权限

**Files:**
- Create: `app/business/bi/api/export.py`
- Modify: `app/business/bi/api/__init__.py`
- Modify: `app/business/bi/init_data.py`

- [ ] **Step 1: 创建 `api/export.py`**

```python
"""BiExport API 路由 — 报表导出（CSV / Excel）。

按钮码：
- ``B_BI_CHART_EXPORT`` —— 图表导出（chart_csv / charts_excel）
- ``B_BI_DASHBOARD_EXPORT`` —— 仪表盘导出（dashboard_excel）

行级隔离：tenant_id = 当前用户，越权返回 4140/4141。
响应均为文件流（text/csv 或 xlsx），带 Content-Disposition 附件名。
"""

from __future__ import annotations

import urllib.parse

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.business.bi.models import BiChart, BiDashboard
from app.business.bi.services_export import (
    build_chart_csv,
    build_charts_excel,
    build_dashboard_excel,
)
from app.core.exceptions import BizError
from app.utils import Code, DependAuth, SqidPath, decode_id, get_current_user_id, require_buttons

router = APIRouter(prefix="/export", tags=["BI报表导出"])

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _attachment(filename: str) -> str:
    """构造 Content-Disposition（RFC 5987 编码中文名）。"""
    quoted = urllib.parse.quote(filename)
    return f"attachment; filename*=UTF-8''{quoted}"


async def _get_owned_chart(chart_id: int, user_id: int) -> BiChart:
    chart = await BiChart.get_or_none(id=chart_id, tenant_id=user_id, deleted_at__isnull=True)
    if not chart:
        raise BizError(Code.BI_EXPORT_CHART_NOT_FOUND, "图表不存在或无权导出")
    return chart


@router.get(
    "/charts/{chart_id}/csv",
    summary="导出图表 CSV",
    name="bi.export.chart_csv",
    dependencies=[DependAuth, require_buttons("B_BI_CHART_EXPORT")],
)
async def export_chart_csv_endpoint(chart_id: SqidPath):
    """单图表 CSV（基于结果快照）。"""
    user_id = get_current_user_id()
    chart = await _get_owned_chart(chart_id, user_id)
    if not chart.result_snapshot or not chart.result_snapshot.get("rows"):
        raise BizError(Code.BI_EXPORT_NO_SNAPSHOT, "图表无结果快照")
    raw = build_chart_csv(chart)
    return StreamingResponse(
        iter([raw]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": _attachment(f"{chart.name}.csv")},
    )


@router.post(
    "/charts/excel",
    summary="批量导出图表 Excel",
    name="bi.export.charts_excel",
    dependencies=[DependAuth, require_buttons("B_BI_CHART_EXPORT")],
)
async def export_charts_excel_endpoint(obj_in: dict):
    """批量图表 Excel：body {chartIds: [sqid, ...]}，每图表一个 Sheet。"""
    user_id = get_current_user_id()
    ids = [decode_id(s) for s in (obj_in.get("chartIds") or [])]
    if not ids:
        raise BizError(Code.BI_EXPORT_CHART_NOT_FOUND, "chartIds 不能为空")
    charts = []
    for cid in ids:
        chart = await _get_owned_chart(cid, user_id)
        charts.append(chart)
    raw = build_charts_excel(charts)
    return StreamingResponse(
        iter([raw]),
        media_type=XLSX_MEDIA,
        headers={"Content-Disposition": _attachment(f"charts-{len(charts)}.xlsx")},
    )


@router.post(
    "/dashboards/{dashboard_id}/excel",
    summary="导出仪表盘 Excel",
    name="bi.export.dashboard_excel",
    dependencies=[DependAuth, require_buttons("B_BI_DASHBOARD_EXPORT")],
)
async def export_dashboard_excel_endpoint(dashboard_id: SqidPath):
    """仪表盘 Excel：概览 Sheet + 每图表一个 Sheet（只含布局引用的图表）。"""
    user_id = get_current_user_id()
    dashboard = await BiDashboard.get_or_none(
        id=dashboard_id, tenant_id=user_id, deleted_at__isnull=True
    )
    if not dashboard:
        raise BizError(Code.BI_EXPORT_DASHBOARD_NOT_FOUND, "仪表盘不存在或无权导出")

    # 收集布局引用的图表（去重 + 归属校验）
    # chartId 是 sqid 字符串（DashboardItemSchema.chartId: str），decode 失败跳过
    chart_ids = list({item.get("chartId") for item in (dashboard.layout or {}).get("items", [])})
    charts = []
    for cid in chart_ids:
        try:
            cid_int = decode_id(cid)
        except (ValueError, TypeError):
            continue
        chart = await BiChart.get_or_none(
            id=cid_int, tenant_id=user_id, deleted_at__isnull=True
        )
        if chart:
            charts.append(chart)

    raw = build_dashboard_excel(dashboard, charts)
    return StreamingResponse(
        iter([raw]),
        media_type=XLSX_MEDIA,
        headers={"Content-Disposition": _attachment(f"{dashboard.name}.xlsx")},
    )
```

> 注意：`layout.items[].chartId` 是 sqid 字符串（前端存储），需 decode 后查询；若存的是 int 也可兼容（先尝试 decode，失败按 int 处理——见 Step 1 补丁）。仪表盘 layout 的 chartId 实际以 sqid 字符串存储（由前端 encode），后端解码方式与图表接口保持一致：`decode_id`。

- [ ] **Step 2: `api/__init__.py` 挂载**

```python
from app.business.bi.api.export import router as export_router
# ...
router.include_router(export_router)
```

- [ ] **Step 3: `init_data.py` 权限**

菜单按钮：`bi_charts` 菜单追加 `B_BI_CHART_EXPORT`，`bi_dashboards` 菜单追加 `B_BI_DASHBOARD_EXPORT`。

```python
# charts 菜单 buttons 追加
{"button_code": "B_BI_CHART_EXPORT", "button_desc": "导出图表"},
# dashboards 菜单 buttons 追加
{"button_code": "B_BI_DASHBOARD_EXPORT", "button_desc": "导出仪表盘"},
```

`BI_ALL_BUTTONS` 追加：
```python
    "B_BI_CHART_EXPORT",
    "B_BI_DASHBOARD_EXPORT",
```

`BI_ANALYST_BUTTONS` 追加：
```python
    "B_BI_CHART_EXPORT",
    "B_BI_DASHBOARD_EXPORT",
```

`BI_ADMIN_APIS` 追加：
```python
    # export（报表导出）
    "bi.export.chart_csv",
    "bi.export.charts_excel",
    "bi.export.dashboard_excel",
```

`BI_ANALYST_APIS` 追加同样的 3 个 route_key。

- [ ] **Step 4: 运行测试**

Run: `uv run pytest tests/test_bi_export.py -v`
Expected: 全部通过

---

## Task 5: 前端 service API + 测试

**Files:**
- Create: `web/src/service/api/bi-export.ts`
- Create: `web/src/service/api/__tests__/bi-export.test.ts`

- [ ] **Step 1: 创建 `bi-export.ts`**（仿 `bi-audit.ts` 的 blob 模式）

```typescript
import { request } from '../request';

/** 导出单图表 CSV（Blob 下载） */
export function fetchBiChartCsvExport(chartId: string) {
  return request<Blob, 'blob'>({
    url: `/business/bi/export/charts/${chartId}/csv`,
    method: 'get',
    responseType: 'blob'
  });
}

/** 批量导出图表 Excel（Blob 下载） */
export function fetchBiChartsExcelExport(data: { chartIds: string[] }) {
  return request<Blob, 'blob'>({
    url: '/business/bi/export/charts/excel',
    method: 'post',
    data,
    responseType: 'blob'
  });
}

/** 导出仪表盘 Excel（Blob 下载） */
export function fetchBiDashboardExcelExport(dashboardId: string) {
  return request<Blob, 'blob'>({
    url: `/business/bi/export/dashboards/${dashboardId}/excel`,
    method: 'post',
    responseType: 'blob'
  });
}
```

- [ ] **Step 2: 创建 `__tests__/bi-export.test.ts`**（仿 bi-masking.test.ts 模式，mock `../../request`）

覆盖 3 个函数：URL、method、data、responseType: 'blob'。

- [ ] **Step 3: 跑 vitest**

Run: `cd web && pnpm test`
Expected: 新增测试通过

---

## Task 6: 前端 PDF 导出工具

**Files:**
- Modify: `web/package.json`（新增 `jspdf`）
- Create: `web/src/views/bi/shared/export-pdf.ts`

- [ ] **Step 1: 安装 jspdf**

Run: `cd web && pnpm add jspdf`

- [ ] **Step 2: 创建 `export-pdf.ts`**

```typescript
import { jsPDF } from 'jspdf';

const PAGE_WIDTH = 210; // A4 mm
const PAGE_HEIGHT = 297;
const MARGIN = 12;

function pageFooter(doc: jsPDF, pageNo: number) {
  doc.setFontSize(9);
  doc.setTextColor(120);
  doc.text(`第 ${pageNo} 页`, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 8, { align: 'right' });
}

/**
 * 单图表 PDF：一张图表图片一页。
 * @param title 图表名
 * @param dataUrl ECharts getDataURL 结果（data:image/png;base64,...）
 */
export function exportChartPdf(title: string, dataUrl: string) {
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  addChartPage(doc, title, dataUrl, 1);
  doc.save(`${title}.pdf`);
}

/**
 * 仪表盘 PDF：多图表逐页拼接。
 * @param title 仪表盘名
 * @param items 每个图表 { title, dataUrl }
 */
export function exportDashboardPdf(title: string, items: { title: string; dataUrl: string }[]) {
  if (!items.length) return;
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  items.forEach((item, index) => {
    if (index > 0) doc.addPage();
    addChartPage(doc, item.title, item.dataUrl, index + 1);
  });
  doc.save(`${title}.pdf`);
}

function addChartPage(doc: jsPDF, title: string, dataUrl: string, pageNo: number) {
  const img = new Image();
  img.src = dataUrl;
  const naturalW = img.width || 800;
  const naturalH = img.height || 400;
  const maxW = PAGE_WIDTH - MARGIN * 2;
  const maxH = PAGE_HEIGHT - MARGIN * 2 - 18;
  const scale = Math.min(maxW / naturalW, maxH / naturalH);
  const w = naturalW * scale;
  const h = naturalH * scale;
  const x = (PAGE_WIDTH - w) / 2;
  const y = MARGIN + 14;

  doc.setFontSize(14);
  doc.setTextColor(31);
  doc.text(title, PAGE_WIDTH / 2, 14, { align: 'center' });
  doc.addImage(dataUrl, 'PNG', x, y, w, h);
  pageFooter(doc, pageNo);
}
```

> 说明：`addChartPage` 中通过 `new Image()` 读取自然尺寸以等比缩放。实际 ECharts getDataURL 已带固定宽高，也可直接按 canvas 宽高计算——实现时用 `getDataURL({ pixelRatio: 2 })` 的 canvas 尺寸即可。

- [ ] **Step 3: typecheck**

Run: `cd web && pnpm typecheck`
Expected: 通过

---

## Task 7: 图表详情页导出按钮

**Files:**
- Modify: `web/src/views/bi/chart-detail/[id].vue`

- [ ] **Step 1: 修改 script**

- `useEcharts` 解构 `chart`（shallowRef<ECharts>）用于 getDataURL
- 新增导出处理：

```typescript
function exportChartCsv() {
  if (!chart.value?.id) return;
  const { data: blob, error } = await fetchBiChartCsvExport(chart.value.id);
  triggerBlobDownload(blob, `${chart.value.name}.csv`);
}

function exportChartExcel() {
  if (!chart.value?.id) return;
  const { data: blob, error } = await fetchBiChartsExcelExport({ chartIds: [chart.value.id] });
  triggerBlobDownload(blob, `${chart.value.name}.xlsx`);
}

function exportChartPdf() {
  const inst = chartRef && getChartInstance();  // 通过 useEcharts 的 chart shallowRef
  if (!inst) { window.$message?.warning(...); return; }
  const url = inst.getDataURL({ pixelRatio: 2, backgroundColor: '#fff' });
  exportChartPdfFn(chart.value?.name || 'chart', url);
}
```

> 用 `chart.value?.getDataURL({ pixelRatio: 2, backgroundColor: '#fff' })`（useEcharts 返回的 chart 即为 ECharts 实例）。

- [ ] **Step 2: 模板加「导出」NDropdown**

在操作区（刷新/分享按钮附近）加：

```vue
<NDropdown
  :options="exportOptions"
  :disabled="!chart?.resultSnapshot?.rows?.length"
  @select="handleExportSelect"
>
  <NButton size="small" ghost type="primary">
    <template #icon><icon-ic-round-download class="text-icon" /></template>
    {{ $t('page.bi.export.export') }}
  </NButton>
</NDropdown>
```

`exportOptions`：
```typescript
const exportOptions = [
  { label: $t('page.bi.export.csv'), key: 'csv' },
  { label: $t('page.bi.export.excel'), key: 'excel' },
  { label: $t('page.bi.export.pdf'), key: 'pdf' }
];
```

- [ ] **Step 3: lint + typecheck**

Run: `cd web && pnpm lint && pnpm typecheck`

---

## Task 8: 仪表盘详情页导出按钮

**Files:**
- Modify: `web/src/views/bi/shared/dashboard-chart-card.vue`（暴露 getChartDataURL）
- Modify: `web/src/views/bi/dashboards/detail/[id].vue`（导出下拉 + 收集图表 dataURL）

- [ ] **Step 1: `dashboard-chart-card.vue` 暴露实例方法**

`defineComponent` setup 中使用 context.expose（项目约定，不用 defineExpose）：

```typescript
setup(p, { emit, expose }) {
  // ... 现有逻辑（option / useEcharts）
  expose({
    /** 返回图表 PNG dataURL；未渲染或无快照返回 null */
    getChartDataURL(): string | null {
      const inst = chartRef.value;  // useEcharts 返回的 chart shallowRef
      if (!inst || !snapshot.value?.rows?.length) return null;
      return inst.getDataURL({ pixelRatio: 2, backgroundColor: '#ffffff' });
    }
  });
  // ...
}
```

- [ ] **Step 2: `[id].vue` 收集图表实例**

- 维护 `chartCardRefs = new Map<string, InstanceType<typeof DashboardChartCard>>()`
- gridstack 挂载 DashboardChartCard 时记录 ref；移除时删除
- 导出 PDF：

```typescript
function exportDashboardPdf() {
  const items: { title: string; dataUrl: string }[] = [];
  viewLayout.value.forEach(item => {
    const inst = chartCardRefs.get(item.chartId);
    const url = inst?.getChartDataURL?.();
    if (url) items.push({ title: refreshItems.value[item.chartId]?.chartMeta?.name ?? 'chart', dataUrl: url });
  });
  if (!items.length) { window.$message?.warning($t('page.bi.export.noChart')); return; }
  exportDashboardPdfFn(dashboardName.value || 'dashboard', items);
}

function exportDashboardExcel() {
  const { data: blob, error } = await fetchBiDashboardExcelExport(dashboardId.value);
  triggerBlobDownload(blob, `${dashboardName.value || 'dashboard'}.xlsx`);
}
```

- [ ] **Step 3: 模板加导出 NDropdown**（查看模式操作区，刷新按钮旁）

```vue
<NDropdown :options="exportOptions" @select="handleExportSelect">
  <NButton size="small" ghost type="primary">
    <template #icon><icon-ic-round-download class="text-icon" /></template>
    {{ $t('page.bi.export.export') }}
  </NButton>
</NDropdown>
```

`exportOptions`：Excel / PDF（仪表盘不做单图表 CSV）。

- [ ] **Step 4: lint + typecheck**

Run: `cd web && pnpm lint && pnpm typecheck`

---

## Task 9: 前端 i18n

**Files:**
- Modify: `web/src/locales/langs/_generated/bi/zh-cn.ts`
- Modify: `web/src/locales/langs/_generated/bi/en-us.ts`
- Modify: `web/src/locales/langs/_generated/bi/types.d.ts`

- [ ] **Step 1: zh-cn.ts 追加 `export:` 命名空间**

```typescript
    export: {
      export: '导出',
      csv: 'CSV',
      excel: 'Excel',
      pdf: 'PDF',
      noChart: '暂无可导出的图表',
      exportSuccess: '导出成功',
      exportFailed: '导出失败'
    },
```

- [ ] **Step 2: en-us.ts 追加对应英文**

```typescript
    export: {
      export: 'Export',
      csv: 'CSV',
      excel: 'Excel',
      pdf: 'PDF',
      noChart: 'No chart to export',
      exportSuccess: 'Export succeeded',
      exportFailed: 'Export failed'
    },
```

- [ ] **Step 3: types.d.ts 追加**

```typescript
    export: {
      export: string;
      csv: string;
      excel: string;
      pdf: string;
      noChart: string;
      exportSuccess: string;
      exportFailed: string;
    };
```

- [ ] **Step 4: lint**

Run: `cd web && pnpm lint`

---

## Task 10: 端到端门禁验证

**Files:** 无（验证任务）

- [ ] **Step 1: 后端门禁**

Run: `just check`
Expected: ruff + basedpyright + pytest 全绿

- [ ] **Step 2: 前端门禁**

Run: `cd web && pnpm lint && pnpm typecheck && pnpm test`
Expected: 全绿

- [ ] **Step 3: 运行时验证**

Run: `just run backend`

```bash
curl -s http://localhost:9999/api/v1/business/bi/export/charts/abc/csv
# 期望 code: 2100
curl -s http://localhost:9999/api/v1/business/bi/export/dashboards/abc/excel -X POST
# 期望 code: 2100
```

- [ ] **Step 4: 关闭后端 + 释放端口**

```bash
lsof -ti:9999 | xargs kill -9 2>/dev/null
```

- [ ] **Step 5: 最终提交（含 D-2 + E 全部改动，用户确认后）**

```bash
git add -A
git commit -m "feat(bi): report export center (batch E) + subscription push (batch D-2)"
```

---

## Self-Review

### Spec 覆盖检查

| Spec 要求 | 对应 Task |
|-----------|-----------|
| openpyxl 依赖 + 错误码 4140-4142 + 配置 | Task 1 |
| CSV / Excel 生成服务 | Task 2 |
| 后端测试（CSV 内容/转义/空行、Excel 多 Sheet/截断/概览、鉴权） | Task 3 |
| 3 个导出 API + 挂载 + 按钮/API 权限 | Task 4 |
| 前端 service + 测试 | Task 5 |
| jspdf 依赖 + PDF 导出工具 | Task 6 |
| 图表详情页导出按钮（CSV/Excel/PDF） | Task 7 |
| 仪表盘详情页导出（Excel/PDF）+ card expose | Task 8 |
| i18n（zh/en/types） | Task 9 |
| just check 全绿 + 运行时 2100 | Task 10 |

### 占位符扫描

- 无 "TBD" / "TODO"
- Task 7/8 前端代码为骨架，需结合现有页面变量名（chart、dashboardName、viewLayout 等）微调

### 类型一致性

- `build_chart_csv(chart) -> bytes` / `build_charts_excel(charts) -> bytes` / `build_dashboard_excel(dashboard, charts) -> bytes` — 前后一致
- 前端 `fetchBiChartCsvExport / fetchBiChartsExcelExport / fetchBiDashboardExcelExport` 与后端路由对应
- PDF 工具 `exportChartPdf(title, dataUrl)` / `exportDashboardPdf(title, items)` — Task 6 定义，Task 7/8 使用

### 风险与注意

- **dashboard layout chartId 格式**：需确认 `layout.items[].chartId` 是 sqid 字符串还是 int。前端存储时 `chart.id` 为 sqid（encode 后）。后端导出时应先 `decode_id`，兼容 int 兜底。
- **Excel 中文字体**：openpyxl 生成的 xlsx 不嵌入字体，Excel 客户端本地渲染，无字体部署问题（与 reportlab 不同）。
- **PDF 依赖下载**：jspdf 为纯前端库，无构建风险。
