# BI 报表导出中心（Report Export Center）Spec — Batch E

> **批次**：差异化第一梯队 · 批次 E
> **前置依赖**：批次 A（BiChart 图表保存）— 导出基于 BiChart.result_snapshot
> **文档版本**：v1.0 · 2026-08-04

---

## 1. 背景与目标

### 1.1 现状问题

BI 模块已具备图表保存（批次 A）、仪表盘（批次 C）、异步查询（批次 B）等能力，但**缺少统一的报表导出**：

- 图表只能在前端导出 PNG / CSV（聊天场景），无 Excel 输出
- 仪表盘只能看，无法导出成文件归档 / 汇报
- 图表列表页无法批量导出

### 1.2 目标

提供「报表导出中心」能力，把 BI 资产导出为办公文件：

1. **单图表导出**：CSV（后端）、Excel（后端）、PDF（前端，保留 ECharts 视觉）
2. **仪表盘导出**：Excel（后端，多 Sheet：概览 + 每图表一个 Sheet）、PDF（前端，每图表一页）
3. 所有导出基于**图表结果快照**（≤ 1000 行），不重跑 SQL，离线快速生成
4. 导出受按钮权限控制，行级隔离（只能导出自己有权限的图表/仪表盘）

### 1.3 非目标（本批次不做）

- 导出历史记录表 / 导出中心列表页（纯即时下载，无记录）
- 后端生成 PDF（前端生成保留图表视觉一致性）
- 实时重跑 SQL 导出（快照已足够，且避免连接池压力）
- 邮件 / 飞书发送报表
- 定时导出任务（与批次 D 订阅推送合并，留后续迭代）

---

## 2. 用户场景

### 场景 1：单图表导出 CSV / Excel

分析师小李在图表详情页看到「月度销售趋势」，点「导出」下拉选择 Excel，
浏览器下载 `销售趋势.xlsx`（含一个数据 Sheet），可用于二次加工。

### 场景 2：仪表盘导出 Excel（多 Sheet）

小李打开「经营日报」仪表盘详情页，点「导出 Excel」，
得到 `经营日报.xlsx`：第一个 Sheet 是概览（名称/描述/图表数/导出时间），
后面每个图表一个 Sheet（表头 + 数据行）。

### 场景 3：仪表盘导出 PDF（汇报用）

小李把「经营日报」导出为 PDF，每个图表一页（保留 ECharts 视觉），
可直接用于周会汇报。

---

## 3. 功能需求

### 3.1 后端

| 功能 | 说明 |
|------|------|
| 单图表 CSV | `GET /export/charts/{chart_id}/csv`，基于 result_snapshot 生成 UTF-8 BOM CSV |
| 批量图表 Excel | `POST /export/charts/excel`，body `{chartIds: [...]}`，每图表一个 Sheet |
| 仪表盘 Excel | `POST /export/dashboards/{dashboard_id}/excel`，概览 Sheet + 每图表 Sheet |
| 行级隔离 | 所有接口按 `tenant_id`（= user.id）校验归属，越权返回 404 |
| 快照校验 | 图表无 result_snapshot 或 rows 为空 → 业务错误 4142 |

### 3.2 前端

| 功能 | 说明 |
|------|------|
| 图表详情页导出按钮 | 下拉：CSV / Excel / PDF（按 `B_BI_CHART_EXPORT` 权限显示） |
| 仪表盘详情页导出按钮 | 下拉：Excel / PDF（按 `B_BI_DASHBOARD_EXPORT` 权限显示） |
| PDF 生成 | jsPDF + ECharts `getDataURL`（pixelRatio 2），单图表一页，仪表盘逐图表分页 |
| 下载方式 | 后端返回 StreamingResponse，前端用 blob + a.click 下载；PDF 前端直接生成 |

---

## 4. 架构设计

### 4.1 技术选型

- **后端 Excel**：`openpyxl`（新增依赖），内存生成 xlsx bytes，StreamingResponse 返回
- **后端 CSV**：Python 标准库 `csv`，UTF-8 BOM（兼容 Excel 中文）
- **前端 PDF**：`jspdf`（新增依赖）+ ECharts `getDataURL`
- **前端下载**：现有 `request` 库的 `isReturnBlob` 模式或原生 fetch + blob

### 4.2 依赖变更

| 位置 | 变更 |
|------|------|
| `pyproject.toml` | 新增 `openpyxl>=3.1.0` |
| `web/package.json` | 新增 `jspdf` |

### 4.3 数据模型

**无新表**。复用 `BiChart`（result_snapshot / name / chart_type / x_col / y_col）与 `BiDashboard`（name / description / layout.items）。

### 4.4 快照数据结构（复用）

```
result_snapshot = {
  "columns": ["m", "s", ...],   # list[str]
  "rows": [{"m": "1月", "s": 100}, ...],  # list[dict[str, Any]]
  "rowCount": N,
  "elapsedMs": N,
  "isTruncated": bool?           # 截断时存在
}
```

Excel/CSV 导出时按 `columns` 顺序取 `rows[i][col]`。

---

## 5. API 设计

统一前缀 `/api/v1/business/bi/export`，`auth="permission"`（module.py 已全局应用），各接口追加按钮依赖。

### 5.1 单图表 CSV

```
GET /export/charts/{chart_id}/csv
name: bi.export.chart_csv
依赖: B_BI_CHART_EXPORT
响应: text/csv; charset=utf-8, Content-Disposition: attachment; filename="{chart_name}.csv"
```

### 5.2 批量图表 Excel

```
POST /export/charts/excel
body: { chartIds: [sqid, ...] }
name: bi.export.charts_excel
依赖: B_BI_CHART_EXPORT
响应: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
```

Sheet 结构：每图表一个 Sheet，Sheet 名 = 图表名（截断 31 字符 + 去非法字符 `[]:*?/\\`）；
第一行标题（图表名 + 类型），第三行起表头 + 数据。

### 5.3 仪表盘 Excel

```
POST /export/dashboards/{dashboard_id}/excel
name: bi.export.dashboard_excel
依赖: B_BI_DASHBOARD_EXPORT
响应: xlsx
```

Sheet 结构：
- Sheet「概览」：仪表盘名称 / 描述 / 图表数 / 导出时间
- 每图表一个 Sheet（同 5.2）

### 5.4 错误码（追加到 `app/core/code.py` BI 段）

```python
BI_EXPORT_CHART_NOT_FOUND = "4140"    # 图表不存在或越权
BI_EXPORT_DASHBOARD_NOT_FOUND = "4141"  # 仪表盘不存在或越权
BI_EXPORT_NO_SNAPSHOT = "4142"        # 图表无结果快照或 rows 为空
```

---

## 6. 权限设计

### 6.1 按钮码

| 按钮码 | 说明 | 归属菜单 |
|--------|------|----------|
| `B_BI_CHART_EXPORT` | 导出图表（CSV/Excel/PDF） | 图表库 `bi_charts` |
| `B_BI_DASHBOARD_EXPORT` | 导出仪表盘（Excel/PDF） | 仪表盘 `bi_dashboards` |

### 6.2 角色授权

- `BI_ALL_BUTTONS` 追加两个按钮码
- `BI_ANALYST_BUTTONS` 追加两个按钮码（数据分析师可导出自己权限内的图表/仪表盘）
- `BI_ADMIN_APIS` / `BI_ANALYST_APIS` 追加 3 个 route_key

### 6.3 行级隔离

- 图表：`BiChart.get_or_none(id=..., tenant_id=user_id, deleted_at__isnull=True)`
- 仪表盘：`BiDashboard.get_or_none(id=..., tenant_id=user_id, deleted_at__isnull=True)`
- 仪表盘内图表：只导出 `layout.items` 中引用的、且 `tenant_id` 归属当前用户的图表

---

## 7. 前端设计

### 7.1 新增 API 服务 `web/src/service/api/bi-export.ts`

```typescript
/** 单图表 CSV 导出 */
fetchBiChartCsvExport(chartId: string): 下载
/** 批量图表 Excel 导出 */
fetchBiChartsExcelExport(data: { chartIds: string[] }): 下载
/** 仪表盘 Excel 导出 */
fetchBiDashboardExcelExport(dashboardId: string): 下载
```

下载走 `request` 的 blob 响应 + 前端触发 `<a download>`。

### 7.2 PDF 导出工具 `web/src/views/bi/shared/export-pdf.ts`

```typescript
/** 单图表 PDF：图表 dataURL → jsPDF 单页 */
exportChartPdf(name: string, chartDataUrl: string): void
/** 仪表盘 PDF：图表 dataURL 数组 → jsPDF 逐页 */
exportDashboardPdf(name: string, items: { title: string; dataUrl: string }[]): void
```

- 依赖 `jspdf`，A4 纵向，图表图片等比缩放至页面宽度
- 页首标题 + 导出时间

### 7.3 图表详情页 `chart-detail/[id].vue`

- 操作区加「导出」`NDropdown`（CSV / Excel / PDF）
- 通过 `useEcharts` 返回的 `chart` shallowRef 拿 `getDataURL`

### 7.4 仪表盘详情页 `dashboards/detail/[id].vue`

- 查看模式操作区加「导出」`NDropdown`（Excel / PDF）
- 修改 `dashboard-chart-card.vue`：暴露 `getChartDataURL()` 方法（通过 setup context expose）
- 导出时遍历 `viewLayout` 中 status=success 的图表卡片，收集 dataURL 拼接 PDF

---

## 8. 测试策略

### 8.1 后端 `tests/test_bi_export.py`

| 用例 | 覆盖 |
|------|------|
| CSV 生成 | 内容含 BOM + 表头 + 数据行；特殊字符引号转义 |
| CSV 归属 | 他人图表 → 4140 |
| CSV 无快照 | rows 为空 → 4142 |
| 批量 Excel | 多 Sheet、Sheet 名截断、单元格值正确 |
| 仪表盘 Excel | 概览 Sheet + 每图表 Sheet |
| Excel 归属 | 他人仪表盘 → 4141 |
| API 鉴权 | 未登录 → 2100 |

### 8.2 前端

- `bi-export.test.ts`：3 个 service API 函数测试（URL / method / params）
- typecheck + lint 全绿

---

## 9. 非目标（明确不做）

- 导出历史 / 导出任务记录表
- 后端 PDF 生成（视觉一致性由前端保证）
- 实时 SQL 重跑导出
- 邮件 / 飞书推送导出文件
- 定时导出（订阅推送可扩展，本批次不合并）

---

## 10. 验收标准

1. 图表详情页可导出 CSV / Excel / PDF，文件内容与快照一致
2. 仪表盘详情页可导出 Excel（多 Sheet）/ PDF（每图表一页）
3. 越权导出返回 404 语义错误码，未登录返回 2100
4. `just check` 全绿（后端 ruff + basedpyright + pytest，前端 lint + typecheck + vitest）
