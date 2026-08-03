# BI 仪表盘（BiDashboard）— Spec 文档

> **批次**：差异化第一梯队 · 批次 C
> **前置依赖**：批次 A（BiChart 图表保存）— Dashboard 引用 BiChart 作为图表单元
> **文档版本**：v1.0 · 2026-08-03

---

## 1. 背景与目标

### 1.1 现状问题

批次 A 已落地 `BiChart` 图表保存能力，用户可把对话/SQL 工作台里的临时图表变成可复用资产。但当前图表是孤立的：

- 用户无法把多个相关图表组装到一起对比查看（如"销售概览"= 月度趋势 + 区域分布 + Top10 产品）
- 每次查看需逐个打开图表详情页，无法一屏总览
- 无法按业务主题组织图表（如"经营日报"、"库存监控"）

### 1.2 目标

把孤立的 BiChart 组装成**仪表盘**：

1. 用户创建仪表盘，从图表库选择多个 BiChart 添加到画布
2. 12 列栅格布局，支持拖拽排序与 resize 调整尺寸
3. 打开仪表盘时全量刷新所有图表数据，单图表失败时显示"刷新失败"占位
4. 仪表盘按行级 `tenant_id` 隔离，仅登录用户可见

### 1.3 非目标（本批次不做）

- 仪表盘模板/复制
- 仪表盘版本历史
- 仪表盘级权限分享（指定用户可见）
- 免登录外部分享（与 BiChart 严格区分）
- 全局时间过滤器（每个图表按自己保存的 SQL 独立执行）
- 自动定时刷新（cron 刷新，远期）

---

## 2. 关键决策记录

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 布局引擎 | 12 列栅格 + 拖拽 + resize | 体验与复杂度平衡，适合 v0.1 |
| 栅格库 | `gridstack.js@13` | 官方活跃维护，0 依赖，提供 Vue 绑定；vue-grid-layout 在 Vue 3 生态已停更 |
| layout 存储 | JSON `items[]` 字段 | Dashboard 是"整体文档"语义，item 无独立生命周期，JSON 足够且扩展性不输子表 |
| 详情/编辑路由 | 一个路由 `?mode=edit` 切换 | 避免数据重复加载，模式切换流畅 |
| 数据刷新 | 打开时全量刷新 | 体验好，失败时清晰告知用户 |
| 失败降级 | 不返回旧快照，直接告知失败 | 与 BiChart 设计一致，避免误导用户 |
| 共享范围 | 仅内部（登录可见） | 与 BiChart 外部分享区分，简化实现 |
| 全局过滤器 | 不做 | v0.1 边界清晰，避免 SQL AST 注入复杂度 |

---

## 3. 用户场景

### 场景 1：创建经营日报仪表盘

> 张三刚做完月度复盘，想把关键图表组装到一起。他点击"仪表盘"菜单 → "新建"，输入名称"经营日报"、说明"每月更新"。创建后跳转到编辑页，从左侧抽屉的图表库选择"月度销售趋势"、"区域分布"、"Top10 产品"三个图表添加到画布，拖拽调整位置和大小，点击"保存"。

### 场景 2：查看仪表盘

> 李四打开"经营日报"仪表盘，系统自动全量刷新所有图表。其中"区域分布"图表的数据源正在维护，刷新失败，卡片显示"刷新失败"占位，其他图表正常展示最新数据。

### 场景 3：编辑现有仪表盘

> 王五想给"经营日报"加一个新图表。他打开仪表盘，点击"编辑"按钮切换到编辑模式（不自动刷新），从左侧抽屉选择"客户留存率"图表添加，调整位置后点击"保存"。

### 场景 4：移除已删除图表

> 赵六删除了"Top10 产品"图表。第二天打开"经营日报"仪表盘，对应卡片显示"图表已删除，请编辑移除"。他点击"编辑"，删除该卡片，保存。

---

## 4. 数据模型

### 4.1 BiDashboard 模型

新增 `BiDashboard` 模型（表名 `biz_bi_dashboard`）：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | IntField(PK) | 主键ID |
| name | CharField(max=100) | 仪表盘名称 |
| description | TextField(null) | 说明 |
| layout | JSONField | 布局：`{"items": [{chartId, x, y, w, h}]}` |
| tenant_id | IntField(default=0) | 租户ID（行级 data_scope 作用域，存 user.id） |

继承 `BaseModel + AuditMixin + SoftDeleteMixin`，`Meta.table = "biz_bi_dashboard"`，`Meta.manager = SoftDeleteManager()`。

### 4.2 layout JSON 结构

```json
{
  "items": [
    {
      "chartId": "abc123",   // BiChart 的 SQID 编码（字符串）
      "x": 0,                 // 列位置 0-11
      "y": 0,                 // 行位置 0-N
      "w": 6,                 // 宽度 1-12
      "h": 2                  // 高度 1-6（h=1 约 100px）
    },
    {
      "chartId": "def456",
      "x": 6,
      "y": 0,
      "w": 6,
      "h": 2
    }
  ]
}
```

### 4.3 layout 校验规则

- `items[]` 长度 ≤ `BI_DASHBOARD_MAX_ITEMS`（默认 30）
- 每个 item `w ∈ 1-12`，`h ∈ 1-6`
- `chartId` 必须是当前租户的有效 BiChart（创建/更新时校验，软删的不算有效）
- `x ≥ 0`，`y ≥ 0`，`x + w ≤ 12`

---

## 5. API 设计

### 5.1 路由清单

路由前缀：`/api/v1/business/bi/dashboards`

| route_name | 方法+路径 | 说明 | 权限按钮 |
|------------|-----------|------|----------|
| bi.dashboards.create | POST `/dashboards` | 创建仪表盘 | B_BI_DASHBOARD_CREATE |
| bi.dashboards.list | POST `/dashboards/search` | 分页列表 | B_BI_DASHBOARD_VIEW |
| bi.dashboards.get | GET `/dashboards/{id}` | 详情（含 layout） | B_BI_DASHBOARD_VIEW |
| bi.dashboards.update | PUT `/dashboards/{id}` | 更新名称/说明/layout | B_BI_DASHBOARD_EDIT |
| bi.dashboards.delete | DELETE `/dashboards/{id}` | 删除（软删） | B_BI_DASHBOARD_DELETE |
| bi.dashboards.refresh | POST `/dashboards/{id}/refresh` | 全量刷新所有图表数据 | B_BI_DASHBOARD_VIEW |
| bi.dashboards.preview | GET `/dashboards/{id}/preview` | 仅读快照（不刷新，编辑模式用） | B_BI_DASHBOARD_VIEW |

> route_name 遵循 `bi.<resource>.<action>` 三段式，与 BiChart/BiQueryTask 一致。

### 5.2 创建/更新请求 Schema

```python
class BiDashboardCreateSchema(SchemaBase):
    name: str = Field(..., max_length=100, description="仪表盘名称")
    description: str | None = Field(None, description="说明")
    layout: dict = Field(default_factory=lambda: {"items": []}, description="布局")

class BiDashboardUpdateSchema(make_optional(BiDashboardCreateSchema)):
    pass
```

### 5.3 刷新响应

```json
{
  "code": 200,
  "msg": "刷新完成",
  "data": {
    "items": [
      {
        "chartId": "abc123",
        "status": "success",
        "resultSnapshot": {"columns": [...], "rows": [...], "rowCount": 100, "elapsedMs": 234, "isTruncated": false},
        "chartMeta": {"name": "月度销售趋势", "chartType": "line", "xCol": "month", "yCol": "amount"},
        "snapshotAt": "2026-08-03T10:00:00"
      },
      {
        "chartId": "def456",
        "status": "failed",
        "errorMessage": "数据源连接超时",
        "chartMeta": {"name": "区域分布", "chartType": "pie", "xCol": "region", "yCol": "sales"}
      },
      {
        "chartId": "ghi789",
        "status": "deleted",
        "chartMeta": null
      }
    ],
    "totalElapsedMs": 1234
  }
}
```

> 失败时**不返回** `resultSnapshot`，前端显示"刷新失败"占位。
> `chartMeta` 从 BiChart 读取（名称/类型/轴字段），即使刷新失败也能显示卡片标题。

### 5.4 预览响应

```json
{
  "code": 200,
  "data": {
    "id": "abc",
    "name": "经营日报",
    "description": "...",
    "layout": {"items": [...]},
    "items": [
      {
        "chartId": "abc123",
        "chartMeta": {"name": "...", "chartType": "line", "xCol": "...", "yCol": "..."},
        "resultSnapshot": {...}  // BiChart 已保存的快照，不重跑
      }
    ]
  }
}
```

---

## 6. 刷新机制

### 6.1 后端刷新服务（`services_dashboard.py`）

```
async def refresh_dashboard(dashboard_id, user_id) -> RefreshResult:
    dashboard = await BiDashboard.get_or_none(id=..., tenant_id=user_id, deleted_at__isnull=True)
    if not dashboard: raise BizError(NOT_FOUND)

    items = dashboard.layout["items"]
    chart_ids = [decode_id(i["chartId"]) for i in items]
    charts = await BiChart.filter(id__in=chart_ids, tenant_id=user_id, deleted_at__isnull=True)
    chart_map = {c.id: c for c in charts}

    semaphore = asyncio.Semaphore(BI_DASHBOARD_REFRESH_CONCURRENCY)  # 默认 5
    async def refresh_one(item):
        async with semaphore:
            chart = chart_map.get(decode_id(item["chartId"]))
            if not chart: return {"chartId": item["chartId"], "status": "deleted", "chartMeta": None}
            try:
                snapshot = await _rerun_chart_sql(chart, timeout=BI_DASHBOARD_REFRESH_TIMEOUT)
                return {"chartId": item["chartId"], "status": "success",
                        "resultSnapshot": snapshot, "chartMeta": _chart_meta(chart),
                        "snapshotAt": datetime.now().isoformat()}
            except Exception as e:
                return {"chartId": item["chartId"], "status": "failed",
                        "errorMessage": str(e), "chartMeta": _chart_meta(chart)}

    results = await asyncio.gather(*[refresh_one(i) for i in items])
    return {"items": results, "totalElapsedMs": ...}
```

### 6.2 关键设计

- **复用 BiChart 的 SQL 重跑逻辑**：将 `services_chart.py` 中现有的 SQL 重跑代码抽出为共享函数 `_rerun_chart_sql(chart, timeout)`，BiChart 的 refresh 和 Dashboard 的 refresh 共用
- **并发上限 5**（`BI_DASHBOARD_REFRESH_CONCURRENCY`），避免数据源过载
- **单图表超时 25s**（`BI_DASHBOARD_REFRESH_TIMEOUT`，复用同步软超时配置）
- **失败不降级**：返回 `status: "failed" + errorMessage`，不返回旧快照
- **deleted 状态**：BiChart 已软删，返回 `status: "deleted" + chartMeta: null`，前端显示占位

### 6.3 刷新时机

| 时机 | 调用接口 |
|------|----------|
| 进入详情页（查看模式） | 自动调 `/refresh` |
| 用户点"刷新"按钮 | 手动调 `/refresh` |
| 编辑模式 | 调 `/preview`（不刷新，避免编辑时干扰） |

---

## 7. 前端设计

### 7.1 页面结构（2 个路由）

| 路由 | 文件 | 说明 |
|------|------|------|
| `/bi/dashboards` | `views/bi/dashboards/index.vue` | 仪表盘列表（卡片网格，搜索/新建/删除） |
| `/bi/dashboards/:id` | `views/bi/dashboards/detail/[id].vue` | 仪表盘详情（查看 + 编辑模式合一） |

路由名：`bi_dashboards` / `bi_dashboard-detail`（连字符风格与 BiChart 一致）。

### 7.2 详情页交互

**两种模式**（`?mode=edit` 切换）：

- **查看模式**（默认）：
  - 进入时自动调 `/refresh` 全量刷新
  - gridstack `static: true`（不可拖拽/resize）
  - 每个卡片显示图表（复用 `buildChartOption` + `useEcharts`）
  - 失败卡片显示"刷新失败"占位 + 错误信息
  - deleted 卡片显示"图表已删除，请编辑移除"
  - 顶部"刷新"按钮 + "编辑"按钮

- **编辑模式**（`?mode=edit`）：
  - 进入时调 `/preview`（不刷新，用已有快照）
  - gridstack `static: false`（可拖拽 + resize）
  - 左侧抽屉弹出 BiChart 选择器（搜索 + 标签筛选，复用 `fetchBiChartList`）
  - 点击图表添加到画布（默认 w=6, h=2）
  - "保存"按钮批量提交 layout + 名称/说明
  - "取消"按钮回到查看模式

### 7.3 栅格实现（gridstack.js）

```typescript
import { GridStack } from 'gridstack';

// 初始化
const grid = GridStack.init({
  column: 12,
  rowHeight: 100,
  margin: 8,
  staticGrid: !isEditMode,  // 查看模式锁定
  acceptWidgets: true,
}, gridRef.value);

// 监听变化
grid.on('change', (event, items) => {
  layout.items = items.map(i => ({chartId: i.id, x: i.x, y: i.y, w: i.w, h: i.h}));
});
```

### 7.4 组件复用

- 图表渲染：`shared/chart-config.ts` 的 `buildChartOption` + `hooks/common/echarts` 的 `useEcharts`
- BiChart 选择器：复用 `fetchBiChartList` API + `ChartThumbnail` 组件（从 `charts/index.vue` 抽出为共享组件）
- 保存弹窗：不复用（Dashboard 无需 save-chart-modal）

### 7.5 列表页

- 卡片网格（NGrid `cols="1 s:2 m:3 l:4"`）
- 每张卡片：dashboard 名称 + 图表数量 + 更新时间
- 搜索（名称模糊）+ 新建按钮（弹窗输入名称/说明，创建后跳详情页 `?mode=edit`）

---

## 8. 菜单与权限

### 8.1 菜单（`init_data.py`）

在 `BI_MENU_CHILDREN` 中新增：

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

### 8.2 角色权限分配

| 角色 | 菜单 | 按钮 |
|------|------|------|
| BI管理员（R_BI_ADMIN） | bi_dashboards, bi_dashboard-detail | 全部 4 个 |
| 数据分析师（R_BI_ANALYST） | bi_dashboards, bi_dashboard-detail | 全部 4 个（可创建/管理自己的仪表盘） |

### 8.3 行级隔离

- 所有查询带 `tenant_id=user.id`
- 数据分析师 `data_scope=scope`，仅看自己的仪表盘
- BI管理员 `data_scope=all`，看全部仪表盘

---

## 9. 配置项

### 9.1 `.env.example` 新增

```bash
# BI Dashboard
BI_DASHBOARD_REFRESH_CONCURRENCY=5     # 刷新并发上限
BI_DASHBOARD_MAX_ITEMS=30              # 单仪表盘最大图表数
BI_DASHBOARD_REFRESH_TIMEOUT=25        # 单图表刷新超时（秒）
```

### 9.2 `config.py` 新增

```python
BI_DASHBOARD_REFRESH_CONCURRENCY: int = 5
BI_DASHBOARD_MAX_ITEMS: int = 30
BI_DASHBOARD_REFRESH_TIMEOUT: int = 25
```

---

## 10. 边界约束与验收清单

### 10.1 边界约束

1. **layout 校验**：`items[]` 长度 ≤ 30；每个 item `w ∈ 1-12`，`h ∈ 1-6`；`chartId` 必须是当前租户的有效 BiChart；`x + w ≤ 12`
2. **删除联动**：BiChart 软删时**不级联删 Dashboard**，刷新时返回 `status: "deleted"`，前端提示用户编辑移除
3. **不做外部分享**：无 share_token 字段，无公开路由（与 BiChart 严格区分）
4. **不做全局过滤器**：每个图表按自己保存的 SQL 独立执行
5. **行级隔离**：所有查询带 `tenant_id=user.id`
6. **失败不降级**：刷新失败时不返回旧快照，直接告知用户失败

### 10.2 验收清单

- [ ] BiDashboard 模型 + 迁移文件
- [ ] 7 个 API 路由（create/list/get/update/delete/refresh/preview）
- [ ] layout JSON 校验（长度/范围/chartId 有效性）
- [ ] 全量刷新服务（并发上限 5，单图表超时 25s，失败不降级）
- [ ] 前端列表页（搜索/新建/删除）
- [ ] 前端详情页（查看/编辑模式切换，gridstack 栅格）
- [ ] BiChart 选择器抽屉（搜索/标签筛选）
- [ ] 失败/deleted 占位卡片
- [ ] 菜单 + 按钮码 + 角色权限（init_data.py）
- [ ] 配置项（.env.example + config.py）
- [ ] i18n（zh-cn / en-us）
- [ ] 测试覆盖（模型/服务/API/前端 vitest）
- [ ] `just check` 全绿

---

## 11. 影响范围

### 11.1 新增文件

**后端**（`app/business/bi/`）：
- `models.py` — 新增 `BiDashboard` 模型
- `schemas_dashboard.py` — Dashboard schemas
- `services_dashboard.py` — Dashboard 服务（含 refresh）
- `api/dashboard.py` — Dashboard 路由
- `migrations/app_system/0005_add_bi_dashboard.py` — 迁移（承接 0001-0004）

**前端**（`web/src/`）：
- `views/bi/dashboards/index.vue` — 列表页
- `views/bi/dashboards/detail/[id].vue` — 详情/编辑页
- `service/api/bi-dashboard.ts` — API 服务
- `typings/api/bi.d.ts` — 新增 Dashboard 类型
- `locales/langs/_generated/bi/` — i18n

### 11.2 修改文件

- `app/business/bi/init_data.py` — 新增菜单/按钮/角色权限；同步更新 `BI_ALL_BUTTONS` / `BI_ALL_MENUS` / `BI_ADMIN_APIS` / `BI_ANALYST_MENUS` / `BI_ANALYST_BUTTONS` / `BI_ANALYST_APIS` 聚合列表
- `app/business/bi/api/__init__.py` — 聚合 dashboard 路由
- `app/business/bi/config.py` — 新增配置项
- `app/business/bi/services_chart.py` — 抽出 `_rerun_chart_sql` 为共享函数（最小改动）
- `.env.example` — 新增配置项
- `web/package.json` — 新增 `gridstack` 依赖
- `web/src/router/elegant/routes.ts` — 自动生成
- `web/src/typings/api/bi.d.ts` — 新增类型

### 11.3 不动

- `app/core/*`、`app/system/*`
- BiChart 相关代码（仅将 `services_chart.py` 的 SQL 重跑逻辑抽出为共享函数 `_rerun_chart_sql`，最小改动）
- 已有的 BiQueryTask 代码

### 11.4 Breaking Changes

无（纯新增模块）。
