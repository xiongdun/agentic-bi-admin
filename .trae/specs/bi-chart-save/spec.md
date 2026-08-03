# BI 图表保存（BiChart）— Spec 文档

> **批次**：差异化第一梯队 · 批次 A
> **前置依赖**：无（基础能力，Dashboard 依赖它）
> **文档版本**：v1.0 · 2026-07-31

---

## 1. 背景与目标

### 1.1 现状问题

当前 BI 模块的图表只存在于 [BiChatMessage.sql_result](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/app/business/bi/models.py) 中，是会话内的临时数据：

- 用户在智能对话里问"上个月销售趋势"，得到图表，关掉会话就找不回来
- SQL 工作台跑出的结果同样无法复用
- 无法把多次查询的图表组装到一起对比查看
- 无法把图表分享给没有账号的同事

### 1.2 目标

把会话/工作台里的临时图表变成**可复用资产**：

1. 用户可把任意图表"保存"为独立实体（BiChart）
2. 提供图表列表页，支持搜索、按标签筛选
3. 保存的图表可刷新数据（重跑 SQL）或离线查看结果快照
4. 支持生成免登录的分享链接

### 1.3 非目标（本批次不做）

- Dashboard 仪表盘（批次 C）
- 定时报表推送（批次 D）
- 图表版本管理（保留为远期）
- 图表评论/协作

---

## 2. 用户场景

### 场景 1：从对话保存图表

> 张三在智能对话问"给我看下本月各产品线销售额对比"，得到柱状图。他点击图表右上角的"保存"按钮，填入名称"本月产品线销售额"和标签"销售"，图表保存到他的图表库。

### 场景 2：从 SQL 工作台保存图表

> 李四在 SQL 工作台手写了一条复杂分析 SQL，跑出结果后切换到图表 tab，选了折线图。他点击"保存"按钮，图表连同 SQL 一起保存。

### 场景 3：刷新已保存图表

> 王五打开图表库，找到上周保存的"本月产品线销售额"。因为已过了几天，他点击"刷新"按钮，系统重跑 SQL，图表更新为最新数据。

### 场景 4：分享图表给外部同事

> 赵六把保存的"Q3 区域销售分布"饼图开启了分享，生成链接发给没有账号的合作伙伴。对方打开链接看到只读图表，无需登录。

### 场景 5：离线查看（数据源不可用）

> 数据源正在维护，孙七打开图表库查看"上月库存周转率"。虽然无法刷新，但结果快照仍可正常显示，页面提示"数据源不可用，显示的是 {时间} 的快照"。

---

## 3. 数据模型

### 3.1 新建模型：BiChart

在 [app/business/bi/models.py](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/app/business/bi/models.py) 的 `conversation` 子模块之后新增 `chart` 子模块。

```python
# ==================== chart 子模块 ====================


class BiChart(BaseModel, AuditMixin, SoftDeleteMixin):
    """保存的图表（可来自对话或 SQL 工作台）。"""

    id = fields.IntField(primary_key=True, description="主键ID")
    name = fields.CharField(max_length=100, description="图表标题")
    description = fields.TextField(null=True, blank=True, description="图表说明")
    datasource_id: int
    datasource: fields.ForeignKeyRelation[BiDatasource] = fields.ForeignKeyField(
        "app_system.BiDatasource",
        related_name="charts",
        on_delete=fields.CASCADE,
        description="所属数据源",
    )
    chart_type = fields.CharField(max_length=20, description="图表类型：bar/line/pie/scatter/area/radar/funnel/gauge/heatmap")
    x_col = fields.CharField(max_length=100, null=True, blank=True, description="X 轴字段名")
    y_col = fields.CharField(max_length=100, null=True, blank=True, description="Y 轴字段名")
    sql_text = fields.TextField(description="来源 SQL（用于刷新数据）")
    # 结果快照：JSON 结构与 BiChatMessage.sql_result 一致（columns + rows + rowCount + elapsedMs）
    # 保存时最多保留前 1000 行（配置项 BI_CHART_SNAPSHOT_MAX_ROWS）
    result_snapshot = fields.JSONField(description="结果快照（最多 1000 行）")
    tags = fields.CharField(max_length=500, null=True, blank=True, description="标签（逗号分隔，如 销售,月报）")
    is_public = fields.BooleanField(default=False, description="是否开启外部分享")
    share_token = fields.CharField(max_length=32, null=True, blank=True, unique=True, description="外部分享 token（sqid 编码）")
    snapshot_at = fields.DatetimeField(description="结果快照的生成时间")
    tenant_id = fields.IntField(default=0, description="租户ID（行级 data_scope 作用域）")

    class Meta:
        table = "biz_bi_chart"
        manager = SoftDeleteManager()
```

### 3.2 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | CharField(100) | 图表标题，必填 |
| `description` | TextField | 图表说明，选填 |
| `datasource_id` | FK → BiDatasource | 数据源，用于刷新时建连接 |
| `chart_type` | CharField(20) | 9 种图表类型之一（与前端 chart-config.ts 对齐） |
| `x_col` / `y_col` | CharField(100) | X/Y 轴字段名（可空，pie/funnel 等可能只用一个） |
| `sql_text` | TextField | 来源 SQL，必填，用于刷新 |
| `result_snapshot` | JSONField | 结果快照，结构 `{columns, rows, rowCount, elapsedMs}`，最多 1000 行 |
| `tags` | CharField(500) | 逗号分隔标签字符串，前端自动补全 |
| `is_public` | BooleanField | 是否开启分享，默认 false |
| `share_token` | CharField(32) | sqid 编码的分享 token，`is_public=true` 时生成 |
| `snapshot_at` | DatetimeField | 快照生成时间，用于显示"数据更新于 xxx" |
| `tenant_id` | IntField | 行级权限作用域 |

### 3.3 不新建的模型

- **不建独立标签表**：用 `tags` 字符串字段 + 前端自动补全（从现有图表的 tags 字段聚合去重）
- **不建 BiChartVersion**：本批次不做版本管理

---

## 4. API 设计

### 4.1 路由清单

在 [app/business/bi/api/__init__.py](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/app/business/bi/api/__init__.py) 新增 `chart_router`，新增文件 [app/business/bi/api/chart.py](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/app/business/bi/api/chart.py)。

所有路由走 `auth="permission"`（由 module.py 统一挂 `DependPermission`），写接口追加 `require_buttons(...)`。

| 方法 | 路径 | 路由 name | 按钮码 | 说明 |
|---|---|---|---|---|
| GET | `/charts` | `bi.chart.list` | — | 分页列表（支持搜索/标签筛选） |
| POST | `/charts` | `bi.chart.create` | `B_BI_CHART_CREATE` | 保存图表 |
| GET | `/charts/{id}` | `bi.chart.detail` | — | 图表详情（含结果快照） |
| PUT | `/charts/{id}` | `bi.chart.update` | `B_BI_CHART_EDIT` | 更新元数据（名称/描述/标签/图表类型） |
| DELETE | `/charts/{id}` | `bi.chart.delete` | `B_BI_CHART_DELETE` | 软删除 |
| POST | `/charts/{id}/refresh` | `bi.chart.refresh` | `B_BI_CHART_EDIT` | 重跑 SQL 刷新结果快照 |
| POST | `/charts/{id}/share` | `bi.chart.share.enable` | `B_BI_CHART_EDIT` | 开启分享，生成 share_token |
| DELETE | `/charts/{id}/share` | `bi.chart.share.disable` | `B_BI_CHART_EDIT` | 关闭分享，清除 share_token |
| GET | `/charts/tags` | `bi.chart.tags` | — | 获取所有标签（用于自动补全） |
| GET | `/share/{token}` | `bi.chart.share.view` | — | **免登录**查看分享图表 |

### 4.2 请求/响应 Schema

在 [app/business/bi/schemas.py](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/app/business/bi/schemas.py) 新增：

```python
class BiChartCreateSchema(SchemaBase):
    name: str = Field(max_length=100, description="图表标题")
    description: str | None = Field(None, description="图表说明")
    datasource_id: SqidId = Field(description="数据源 ID")
    chart_type: str = Field(max_length=20, description="图表类型")
    x_col: str | None = Field(None, description="X 轴字段")
    y_col: str | None = Field(None, description="Y 轴字段")
    sql_text: str = Field(description="来源 SQL")
    result_snapshot: dict = Field(description="结果快照（columns/rows/rowCount/elapsedMs）")
    tags: str | None = Field(None, description="标签（逗号分隔）")
    snapshot_at: datetime = Field(description="快照生成时间")


class BiChartUpdateSchema(SchemaBase, make_optional=True):
    """所有字段可选，未传字段保留原值。"""
    name: str
    description: str | None
    chart_type: str
    x_col: str | None
    y_col: str | None
    tags: str | None


class BiChartListQuery(PageQueryBase):
    name: str | None = Field(None, description="按名称模糊搜索")
    tags: str | None = Field(None, description="按标签筛选（精确匹配某一个标签）")
    datasource_id: SqidId | None = Field(None, description="按数据源筛选")


class BiChartOutSchema(SchemaBase):
    id: SqidId
    name: str
    description: str | None
    datasource_id: SqidId
    chart_type: str
    x_col: str | None
    y_col: str | None
    sql_text: str
    result_snapshot: dict
    tags: str | None
    is_public: bool
    share_token: str | None
    snapshot_at: datetime
    created_at: datetime
    updated_at: datetime
```

### 4.3 关键接口行为

#### POST `/charts`（保存图表）

1. 校验 `datasource_id` 存在且属于当前租户（行级权限自动过滤）
2. 校验 `sql_text` 走 [whitelist.validate_sql](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/app/business/bi/sandbox/whitelist.py)（防止保存恶意 SQL）
3. 截断 `result_snapshot.rows` 到前 1000 行（配置项 `BI_CHART_SNAPSHOT_MAX_ROWS`），标记 `is_truncated`
4. 写入 `BiChart`，`share_token=None`，`is_public=False`
5. 写 `radar_log` 记录保存行为
6. 返回 `BiChartOutSchema`

#### POST `/charts/{id}/refresh`（刷新数据）

1. 加载 BiChart，校验 `datasource_id` 可用（调 [executor.test_connection](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/app/business/bi/sandbox/executor.py)）
2. 数据源不可用 → 返回 `BizError(4200, "数据源不可用，无法刷新")`，前端降级显示快照
3. 走完整校验链：`validate_sql` → `inject_tenant_filter` → `execute_sql`
4. 用新结果覆盖 `result_snapshot`，更新 `snapshot_at`
5. 返回更新后的 `BiChartOutSchema`

#### GET `/share/{token}`（免登录查看）

1. **不走 `DependPermission`**，在 module.py 的 `BusinessRouter` 中单独挂载，或用 `auth=None`
2. 按 `share_token` 查 `BiChart`，校验 `is_public=True`
3. 不返回 `sql_text`（分享页不暴露 SQL），只返回渲染图表所需字段
4. 记录访问日志（IP + token，不含用户 ID）

---

## 5. 权限设计

### 5.1 按钮码

在 [app/business/bi/init_data.py](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/app/business/bi/init_data.py) 的 `BI_MENU_CHILDREN` 新增"图表库"菜单 + 按钮码：

```python
{
    "menu_name": "图表库",
    "route_name": "bi_charts",
    "route_path": "/bi/charts",
    "component": "view.bi_charts",
    "icon": "mdi:chart-multiple",
    "order": 5,
    "buttons": [
        {"button_code": "B_BI_CHART_CREATE", "button_desc": "保存图表"},
        {"button_code": "B_BI_CHART_EDIT", "button_desc": "编辑图表"},
        {"button_code": "B_BI_CHART_DELETE", "button_desc": "删除图表"},
    ],
},
```

### 5.2 角色权限

更新 `INIT_DATA` 中的角色定义：

- `R_BI_ANALYST`：增加 `B_BI_CHART_CREATE` / `B_BI_CHART_EDIT` / `B_BI_CHART_DELETE`
- `R_BI_VIEWER`（只读角色，如果存在）：只加 `bi.chart.list` / `bi.chart.detail` / `bi.chart.tags` API 权限，不加按钮码

### 5.3 行级权限

- BiChart 继承 `AuditMixin`，自动带 `created_by` 字段
- 角色的 `data_scope` 控制可见范围：
  - `all`：看全部图表
  - `scope`：按 `tenant_id` 过滤
  - `self`：只看自己创建的（`created_by == current_user_id`）
  - `custom`：自定义 scope_id

### 5.4 分享页权限

- 完全免登录，只校验 `share_token` 有效性 + `is_public=True`
- 不走 RBAC，不消耗 API 权限配额

---

## 6. 前端设计

### 6.1 新增页面

#### `/bi/charts` — 图表库列表页

文件：[web/src/views/bi/charts/index.vue](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/web/src/views/bi/charts/index.vue)

- 顶部搜索栏：名称输入框 + 标签下拉（多选） + 数据源筛选
- 主体：卡片网格（响应式，每行 2-4 个），每张卡片显示：
  - 图表缩略图（用 ECharts 渲染 result_snapshot）
  - 名称 + 标签
  - 数据源名称 + 快照时间
  - 操作：打开 / 刷新 / 编辑 / 删除 / 分享
- 分页

#### `/bi/charts/{id}` — 图表详情页

文件：[web/src/views/bi/charts/detail.vue](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/web/src/views/bi/charts/detail.vue)

- 顶部：名称 + 标签 + "数据更新于 {snapshot_at}"
- 操作栏：刷新 / 编辑 / 分享 / 导出 PNG / 导出 CSV
- 主体：大尺寸图表（复用 [chart-config.ts](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/web/src/views/bi/shared/chart-config.ts) 的 `buildChartOption`）
- 底部可折叠：SQL 代码块（用 NCode 展示）

#### `/bi/share/{token}` — 分享页（免登录）

文件：[web/src/views/bi/share/[token].vue](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/web/src/views/bi/share/[token].vue)

- 简化布局：只显示图表 + 名称 + 快照时间
- 不显示 SQL、不显示操作按钮
- 路由配置 `meta.public = true`，不走登录守卫

### 6.2 修改现有页面

#### 智能对话 [message-renderer.vue](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/web/src/views/bi/chat/modules/message-renderer.vue)

在图表 tab 的工具栏（已有"导出 PNG"按钮旁边）新增"保存"按钮：

```vue
<NButton size="tiny" ghost @click="saveChart(msg)">
  <template #icon><icon-ic-round-save class="text-icon" /></template>
  {{ $t('page.bi.chart.save') }}
</NButton>
```

点击后弹出表单（NModal），填入名称/标签，确认后调 `POST /charts`。

#### SQL 工作台 [index.vue](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/web/src/views/bi/sql-workbench/index.vue)

同上，在图表 tab 工具栏加"保存"按钮。

### 6.3 前端 API 层

新增文件 [web/src/service/api/bi-chart.ts](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/web/src/service/api/bi-chart.ts)：

```typescript
/** 保存图表 */
export function fetchCreateChart(data: Api.Bi.BiChartCreate) {
  return request<Api.Bi.BiChart>(`/bi/charts`, { method: 'post', data });
}

/** 图表分页列表 */
export function fetchChartList(params: Api.Bi.BiChartListQuery) {
  return request<Api.Bi.BiChartPage>(`/bi/charts`, { method: 'get', params });
}

/** 图表详情 */
export function fetchChartDetail(id: string) {
  return request<Api.Bi.BiChart>(`/bi/charts/${id}`, { method: 'get' });
}

/** 刷新图表数据 */
export function refreshChart(id: string) {
  return request<Api.Bi.BiChart>(`/bi/charts/${id}/refresh`, { method: 'post' });
}

/** 开启分享 */
export function enableChartShare(id: string) {
  return request<{ shareToken: string }>(`/bi/charts/${id}/share`, { method: 'post' });
}

/** 关闭分享 */
export function disableChartShare(id: string) {
  return request(`/bi/charts/${id}/share`, { method: 'delete' });
}

/** 获取标签列表（自动补全） */
export function fetchChartTags() {
  return request<string[]>(`/bi/charts/tags`, { method: 'get' });
}

/** 免登录查看分享图表 */
export function fetchSharedChart(token: string) {
  return request<Api.Bi.BiChartShared>(`/bi/share/${token}`, { method: 'get' });
}
```

### 6.4 类型定义

在 `web/src/typings/api/bi.d.ts` 新增：

```typescript
declare namespace Api {
  namespace Bi {
    type ChartType = 'bar' | 'line' | 'pie' | 'scatter' | 'area' | 'radar' | 'funnel' | 'gauge' | 'heatmap';

    interface BiChartCreate {
      name: string;
      description?: string;
      datasourceId: string;
      chartType: ChartType;
      xCol?: string;
      yCol?: string;
      sqlText: string;
      resultSnapshot: ChatSqlResult;
      tags?: string;
      snapshotAt: string;
    }

    interface BiChart {
      id: string;
      name: string;
      description?: string;
      datasourceId: string;
      chartType: ChartType;
      xCol?: string;
      yCol?: string;
      sqlText: string;
      resultSnapshot: ChatSqlResult;
      tags?: string;
      isPublic: boolean;
      shareToken?: string;
      snapshotAt: string;
      createdAt: string;
      updatedAt: string;
    }

    interface BiChartShared {
      /** 分享页不返回 sqlText */
      name: string;
      chartType: ChartType;
      xCol?: string;
      yCol?: string;
      resultSnapshot: ChatSqlResult;
      snapshotAt: string;
    }

    interface BiChartListQuery {
      page: number;
      pageSize: number;
      name?: string;
      tags?: string;
      datasourceId?: string;
    }

    type BiChartPage = PageResponse<BiChart>;
  }
}
```

### 6.5 国际化

在 [web/src/locales/langs/_generated/bi/zh-cn.ts](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/web/src/locales/langs/_generated/bi/zh-cn.ts) 新增 `chart` 段：

```typescript
chart: {
  title: '图表库',
  save: '保存',
  saveAs: '保存为图表',
  saveSuccess: '图表保存成功',
  refresh: '刷新',
  refreshSuccess: '数据已刷新',
  refreshFailed: '刷新失败，数据源可能不可用',
  share: '分享',
  enableShare: '开启分享',
  disableShare: '关闭分享',
  shareLink: '分享链接',
  shareLinkCopied: '链接已复制',
  snapshotAt: '数据更新于 {time}',
  dataSourceUnavailable: '数据源不可用，显示的是 {time} 的快照',
  empty: '暂无保存的图表',
  searchPlaceholder: '搜索图表名称',
  tagsLabel: '标签',
  tagsPlaceholder: '输入标签，逗号分隔',
  tagFilter: '按标签筛选',
  nameRequired: '请输入图表名称',
  confirmDelete: '确定删除该图表吗？',
  sharedTitle: 'AgenticBI · 分享图表',
},
```

英文同步在 `en-us.ts` 添加。

---

## 7. 后端实现细节

### 7.1 services 层

新增文件 [app/business/bi/services_chart.py](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/app/business/bi/services_chart.py)（与主 services.py 分离，避免单文件过大）：

```python
"""BiChart 业务服务。"""

from __future__ import annotations

from datetime import datetime

from app.utils import BizError, Code, get_current_user_id, log, radar_log

from .models import BiChart, BiDatasource
from .sandbox.executor import execute_sql, test_connection
from .sandbox.tenant import inject_tenant_filter
from .sandbox.whitelist import validate_sql

# 配置项：结果快照最大行数
CHART_SNAPSHOT_MAX_ROWS = 1000


async def create_chart(schema, tenant_id: int) -> BiChart:
    """保存图表。"""
    # 1. 校验数据源存在且属于当前租户
    datasource = await BiDatasource.get_or_none(id=schema.datasource_id, tenant_id=tenant_id, deleted_at__isnull=True)
    if not datasource:
        raise BizError(Code.not_found, "数据源不存在")

    # 2. 校验 SQL 走白名单
    validate_sql(schema.sql_text, datasource.db_type)

    # 3. 截断结果快照
    snapshot = _truncate_snapshot(schema.result_snapshot, CHART_SNAPSHOT_MAX_ROWS)

    # 4. 创建
    chart = await BiChart.create(
        name=schema.name,
        description=schema.description,
        datasource_id=schema.datasource_id,
        chart_type=schema.chart_type,
        x_col=schema.x_col,
        y_col=schema.y_col,
        sql_text=schema.sql_text,
        result_snapshot=snapshot,
        tags=schema.tags,
        snapshot_at=schema.snapshot_at,
        tenant_id=tenant_id,
        created_by=get_current_user_id(),
    )
    radar_log("bi.chart.create", extra={"chart_id": chart.id, "name": chart.name})
    return chart


async def refresh_chart(chart_id: int, tenant_id: int) -> BiChart:
    """重跑 SQL 刷新结果快照。"""
    chart = await _get_owned_chart(chart_id, tenant_id)

    # 1. 测试数据源连通性
    datasource = await chart.datasource
    ok, err = await test_connection(datasource)
    if not ok:
        raise BizError(Code.bi_datasource_unavailable, f"数据源不可用：{err}")

    # 2. 校验 + 行级注入 + 执行
    validate_sql(chart.sql_text, datasource.db_type)
    sql = inject_tenant_filter(chart.sql_text, tenant_id=tenant_id)
    result = await execute_sql(datasource, sql)

    # 3. 覆盖快照
    chart.result_snapshot = _truncate_snapshot(result.__dict__, CHART_SNAPSHOT_MAX_ROWS)
    chart.snapshot_at = datetime.now()
    await chart.save(update_fields=["result_snapshot", "snapshot_at", "updated_at"])
    radar_log("bi.chart.refresh", extra={"chart_id": chart.id})
    return chart


async def enable_share(chart_id: int, tenant_id: int) -> str:
    """开启分享，返回 share_token。"""
    from app.utils import encode_id
    chart = await _get_owned_chart(chart_id, tenant_id)
    if not chart.share_token:
        chart.share_token = encode_id(chart.id)  # sqid 编码
    chart.is_public = True
    await chart.save(update_fields=["share_token", "is_public", "updated_at"])
    return chart.share_token


def _truncate_snapshot(snapshot: dict, max_rows: int) -> dict:
    """截断结果快照到 max_rows 行。"""
    rows = snapshot.get("rows", [])
    if len(rows) > max_rows:
        snapshot = {**snapshot, "rows": rows[:max_rows], "rowCount": max_rows, "isTruncated": True}
    return snapshot
```

### 7.2 分享页路由特殊处理

分享页 `/share/{token}` 免登录，**不能走 module.py 的 `auth="permission"`**。两种实现方式：

**方式 A（推荐）**：在 `BusinessRouter` 加 `public_routes` 参数，autodiscover 识别后单独挂载到主 app（不带 DependPermission）。

**方式 B**：在 [app/system/api/route.py](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/app/system/api/route.py) 的公开路由中转发。

一期采用**方式 A**，需要扩展 [app/core/business.py](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/app/core/business.py) 的 `BusinessRouter` 类，新增 `public_router` 字段。

### 7.3 配置项

在 [app/business/bi/config.py](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/app/business/bi/config.py) 的 `BusinessSettings` 新增：

```python
bi_chart_snapshot_max_rows: int = 1000
"""图表结果快照最大行数。"""
```

---

## 8. 测试要求

### 8.1 后端测试

在 [tests/conftest.py](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/tests/conftest.py) 的 `TEST_TORTOISE_ORM` 注册 `app.business.bi.models`（当前未注册，BI 模块零后端测试，本批次一并补上）。

新增 [tests/test_bi_chart.py](file:///Users/Summer/Documents/works/codes/python/agentic-bi-admin/tests/test_bi_chart.py)，覆盖：

- 创建图表（正常 + SQL 校验失败 + 数据源不存在）
- 列表查询（分页 + 名称搜索 + 标签筛选 + 行级权限过滤）
- 详情查询
- 更新图表
- 软删除
- 刷新数据（数据源可用 + 不可用降级）
- 开启/关闭分享
- 分享页免登录访问（有效 token + 无效 token + is_public=false）
- 结果快照截断（超过 1000 行）

### 8.2 前端测试

- 图表库列表页 E2E（Playwright）：打开 / 进入详情 / 搜索 / 标签筛选
- 保存图表表单提交（从对话保存 + 从工作台保存）
- 分享页访问

### 8.3 手动验收项

- [ ] 从智能对话保存图表，图表库列表出现新图表
- [ ] 从 SQL 工作台保存图表，图表库列表出现新图表
- [ ] 图表详情页显示快照数据
- [ ] 刷新按钮在数据源可用时更新数据
- [ ] 数据源不可用时显示快照 + 警告提示
- [ ] 开启分享后，用无痕窗口打开分享链接可正常看图
- [ ] 关闭分享后，原链接失效返回 404
- [ ] 行级权限生效：data_scope=self 的用户只能看自己的图表
- [ ] 结果快照超过 1000 行时截断并标记

---

## 9. 迁移与启动

### 9.1 迁移

```bash
just mm  # 生成 biz_bi_chart 表迁移并应用
```

### 9.2 启动初始化

`init_data.init()` 会自动执行 `apply_init_data(INIT_DATA)`，新增的"图表库"菜单 + 按钮码 + 角色权限在重启后自动生效。

### 9.3 前端路由

elegant-router 会根据 `web/src/views/bi/charts/` 和 `web/src/views/bi/share/` 目录自动生成路由，无需手动配置。需确认 `gen-route` 命令已跑：

```bash
cd web && pnpm gen-route
```

---

## 10. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 结果快照过大（1000 行 JSON） | 截断到 1000 行 + 字段 `isTruncated` 标记；大结果不落库只存元数据 |
| SQL 引用已删除的表 | 刷新失败时前端降级显示快照 + 警告，不阻断查看 |
| 分享页数据泄露 | 默认 `is_public=false`，需用户主动开启；分享页不返回 SQL |
| share_token 被暴力猜测 | sqid 编码（32 位），不可猜测；可后续加访问频率限制 |
| BiChatSqlResult 结构变更导致快照不兼容 | 快照存原始结构，前端 buildChartOption 做容错处理 |

---

## 11. 交付物清单

### 11.1 后端

- [ ] `app/business/bi/models.py` — 新增 `BiChart` 模型
- [ ] `app/business/bi/schemas.py` — 新增 4 个 Schema
- [ ] `app/business/bi/services_chart.py` — 新增服务层
- [ ] `app/business/bi/api/chart.py` — 新增 API 路由
- [ ] `app/business/bi/api/__init__.py` — 注册 chart_router
- [ ] `app/business/bi/init_data.py` — 新增菜单/按钮码/角色权限
- [ ] `app/business/bi/config.py` — 新增配置项
- [ ] `app/core/business.py` — 扩展 BusinessRouter 支持 public_routes（如选方式 A）
- [ ] `migrations/app_system/` — 迁移文件
- [ ] `tests/conftest.py` — 注册 bi models
- [ ] `tests/test_bi_chart.py` — 测试用例

### 11.2 前端

- [ ] `web/src/views/bi/charts/index.vue` — 列表页
- [ ] `web/src/views/bi/charts/detail.vue` — 详情页
- [ ] `web/src/views/bi/share/[token].vue` — 分享页
- [ ] `web/src/views/bi/chat/modules/message-renderer.vue` — 加"保存"按钮 + 保存表单
- [ ] `web/src/views/bi/sql-workbench/index.vue` — 加"保存"按钮 + 保存表单
- [ ] `web/src/service/api/bi-chart.ts` — API 层
- [ ] `web/src/typings/api/bi.d.ts` — 类型定义
- [ ] `web/src/locales/langs/_generated/bi/zh-cn.ts` — 中文 i18n
- [ ] `web/src/locales/langs/_generated/bi/en-us.ts` — 英文 i18n
- [ ] `web/src/locales/langs/_generated/bi/types.d.ts` — i18n 类型

### 11.3 验证

- [ ] `just check` 通过
- [ ] 手动验收 9 项全部通过
