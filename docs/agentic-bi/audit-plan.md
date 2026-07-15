# 审计面板 实施计划

**目标：** 把 `bi_audit` 菜单从"敬请期待"占位页升级为完整的 BI 审计中心，覆盖全 BI 域 CRUD 操作埋点、只读分页查询 + 详情钻取、按天趋势/按时段热力图、CSV 导出、可配保留期自动清理。

**架构：**
- 后端复用已有 `bi_audit_log` 表，新增 `bi_audit_sql` 关联表存储原始 SQL（方案 B）
- 新建 `app/business/bi/services/audit.py` 集中 CRUD 埋点 helper + 分页/统计/导出查询
- 新建 `app/business/bi/api/audit.py` 暴露 REST 端点
- 在现有 datasource / llm / metadata / grant 等 service 的 create/update/delete 后调用 `record_audit()`
- 前端 `web/src/views/bi/audit/index.vue` 三段式：KPI 卡片 + 过滤表格 + 详情 Drawer + Tab 切换（列表 / 趋势 / 热力图）
- 启动时通过 `init_data.py` 注册新按钮 `B_BI_AUDIT_EXPORT` + 自动清理定时任务

**技术栈：** FastAPI + Tortoise ORM + Vue3 + Naive UI + ECharts（热力图/趋势图）

---

## 文件清单

### 后端新建
| 文件 | 职责 |
|---|---|
| `app/business/bi/models/audit.py` | `BiAuditSql` 模型（原始 SQL 关联表） |
| `app/business/bi/services/audit.py` | `record_audit()` helper + 分页查询 + 统计 + CSV 导出 + 清理 |
| `app/business/bi/api/audit.py` | REST 端点（list / detail / stats / heatmap / export） |
| `app/business/bi/schemas/audit.py` | 审计相关请求/响应 schema |

### 后端修改
| 文件 | 改动 |
|---|---|
| `app/business/bi/models/__init__.py` | 导出 `BiAuditSql` |
| `app/business/bi/models/security.py` | `AuditLog` 增加 `audit_sql` FK 关联（nullable） |
| `app/business/bi/schemas/__init__.py` | 导出 audit schema |
| `app/business/bi/api/__init__.py` | 注册 audit_router |
| `app/business/bi/module.py` | include audit_router |
| `app/business/bi/services/datasource.py` | create/update/delete 后调 `record_audit()` |
| `app/business/bi/services/llm_api.py` | provider/model CRUD 后调 `record_audit()` |
| `app/business/bi/services/metadata_api.py` | sync 后调 `record_audit()` |
| `app/business/bi/sandbox/pipeline.py` | `_write_audit_log` 改为调 `record_audit()`，同时写 `BiAuditSql` |
| `app/business/bi/init_data.py` | 注册 `B_BI_AUDIT_EXPORT` 按钮 + R_BI_AUDITOR 角色 |
| `app/core/init_app.py` | guard 排除 `/api/v1/business/bi/audit` 路径（CSV body 会触发误判） |

### 前端新建
| 文件 | 职责 |
|---|---|
| `web/src/views/bi/audit/index.vue` | 主页面 |
| `web/src/views/bi/audit/modules/audit-detail-drawer.vue` | 详情抽屉 |
| `web/src/views/bi/audit/modules/audit-trend-chart.vue` | 按天趋势图 |
| `web/src/views/bi/audit/modules/audit-heatmap.vue` | 时段热力图 |

### 前端修改
| 文件 | 改动 |
|---|---|
| `web/src/service/api/bi.ts` | 新增 `fetchBiAuditList / fetchBiAuditDetail / fetchBiAuditStats / fetchBiAuditHeatmap / exportBiAuditCsv` |
| `web/src/typings/api/bi.d.ts` | 新增 `AuditLog` / `AuditSearchParams` / `AuditStats` / `HeatmapPoint` 等类型 |
| `web/src/locales/langs/zh-cn.ts` | 审计面板 i18n |
| `web/src/locales/langs/en-us.ts` | 审计面板 i18n |

### 数据库迁移
- `migrations/app_system/0004_audit_sql.py`（自动生成）

---

## Task 1: BiAuditSql 模型 + AuditLog 关联 + 迁移

**文件：**
- 创建：`app/business/bi/models/audit.py`
- 修改：`app/business/bi/models/security.py` L90-120（AuditLog 加 FK）
- 修改：`app/business/bi/models/__init__.py`（导出 BiAuditSql）
- 迁移：自动生成

### BiAuditSql 模型设计

```python
# app/business/bi/models/audit.py
from __future__ import annotations
from tortoise import fields
from app.core.base_model import BaseModel


class BiAuditSql(BaseModel):
    """原始 SQL 文本存储（与 AuditLog 1:1）。

    独立表避免审计列表查询加载大 SQL 文本；
    保留期清理时按 audit_log.created_at 级联。
    """

    id = fields.BigIntField(primary_key=True, description="ID")
    audit_log: fields.OneToOneRelation = fields.OneToOneField(
        "app_system.AuditLog",
        related_name="audit_sql",
        on_delete=fields.CASCADE,
        description="关联审计日志",
    )
    audit_log_id: int
    sql_text = fields.TextField(description="原始 SQL 文本")
    sql_hash = fields.CharField(max_length=64, db_index=True, description="SQL 哈希")

    class Meta:
        table = "bi_audit_sql"
        table_description = "BI 审计原始 SQL"
```

### AuditLog 修改

在 `AuditLog` 中新增字段：
```python
    audit_sql: fields.OneToOneNullableRelation = fields.OneToOneField(
        "app_system.BiAuditSql",
        related_name="audit_log",
        null=True,
        blank=True,
        on_delete=fields.SET_NULL,
        description="原始 SQL 关联",
    )
    audit_sql_id: int | None
```

- [ ] 创建 `app/business/bi/models/audit.py`
- [ ] 修改 `app/business/bi/models/security.py` 给 AuditLog 加 `audit_sql` FK
- [ ] 修改 `app/business/bi/models/__init__.py` 导出 `BiAuditSql`
- [ ] 跑 `just mm` 生成迁移，检查 SQL
- [ ] 跑 `just check` 验证

---

## Task 2: audit service — record_audit helper + 查询/统计/导出/清理

**文件：**
- 创建：`app/business/bi/services/audit.py`

### 2.1 record_audit helper

```python
async def record_audit(
    *,
    action: str,
    user_id: int | None = None,
    tenant_id: int | None = None,
    datasource_id: int | None = None,
    sql_text: str | None = None,
    sql_hash: str | None = None,
    row_count: int | None = None,
    cost_ms: int | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    detail: dict | None = None,
) -> None:
    """统一的审计写入入口。失败只 warn 不抛。

    - 有 sql_text 时同时写 BiAuditSql 并关联
    - user_id / tenant_id 缺省时从 CTX 取
    """
```

### 2.2 分页查询

```python
async def search_audit_logs(
    *,
    current: int = 1,
    size: int = 20,
    user_id: int | None = None,
    datasource_id: int | None = None,
    action: str | None = None,
    status: str | None = None,  # success / failed
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    keyword: str | None = None,  # 搜 sql_hash / ip
) -> tuple[list[dict], int]:
    ...
```

### 2.3 详情

```python
async def get_audit_detail(audit_id: int) -> dict | None:
    """返回审计记录 + 关联的原始 SQL（如有）。"""
```

### 2.4 统计

```python
async def get_audit_stats(
    *,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> dict:
    """返回 KPI：total / success / failed / total_export_rows / active_users / avg_cost_ms"""
```

### 2.5 按天趋势

```python
async def get_daily_trend(
    *,
    days: int = 30,
    action: str | None = None,
) -> list[dict]:
    """返回 [{date: '2026-07-01', count: 120, success: 100, failed: 20}, ...]"""
```

### 2.6 时段热力图

```python
async def get_hourly_heatmap(
    *,
    days: int = 30,
) -> list[dict]:
    """返回 [{day_of_week: 0-6, hour: 0-23, count: N}, ...] 共 168 格"""
```

### 2.7 CSV 导出

```python
async def export_audit_csv(
    *,
    user_id: int | None = None,
    datasource_id: int | None = None,
    action: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> str:
    """生成 CSV 字符串。列：时间/用户/Action/数据源/SQL摘要/行数/耗时/状态/IP"""
```

### 2.8 自动清理

```python
async def cleanup_old_audit_logs(retention_days: int = 90) -> int:
    """删除超过保留期的审计日志（级联 bi_audit_sql）。返回删除条数。"""
```

- [ ] 创建 `app/business/bi/services/audit.py`，实现以上 8 个函数
- [ ] 修改 `app/business/bi/sandbox/pipeline.py` 的 `_write_audit_log` 改为调 `record_audit(action="query" or "export", sql_text=sql, ...)`
- [ ] 修改 `app/business/bi/services/datasource.py` 的 create/update/delete 后调 `record_audit(action="datasource_create/update/delete", detail={...})`
- [ ] 修改 `app/business/bi/services/llm_api.py` 的 provider/model CRUD 后调 `record_audit(action="provider_create/update/delete/model_create/update/delete", detail={...})`
- [ ] 修改 `app/business/bi/services/metadata_api.py` 的 sync 后调 `record_audit(action="metadata_sync", detail={...})`
- [ ] 跑 `just check`

---

## Task 3: audit schema

**文件：**
- 创建：`app/business/bi/schemas/audit.py`
- 修改：`app/business/bi/schemas/__init__.py`

```python
class AuditSearch(PageQueryBase):
    user_id: int | None = None
    datasource_id: int | None = None
    action: str | None = None
    status: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    keyword: str | None = None

class AuditLogOut(SchemaBase):
    id: int
    user_id: int
    tenant_id: int
    action: str
    datasource_id: int | None = None
    sql_hash: str | None = None
    row_count: int | None = None
    cost_ms: int | None = None
    ip: str | None = None
    user_agent: str | None = None
    detail: dict | None = None
    status: str | None = None  # 从 detail.status 提取
    created_at: str | None = None

class AuditDetailOut(SchemaBase):
    log: AuditLogOut
    sql_text: str | None = None

class AuditStatsOut(SchemaBase):
    total: int
    success: int
    failed: int
    total_export_rows: int
    active_users: int
    avg_cost_ms: float

class DailyTrendItem(SchemaBase):
    date: str
    count: int
    success: int
    failed: int

class HeatmapPoint(SchemaBase):
    day_of_week: int
    hour: int
    count: int

class AuditStatsQuery(SchemaBase):
    start_time: datetime | None = None
    end_time: datetime | None = None

class TrendQuery(SchemaBase):
    days: int = 30
    action: str | None = None
```

- [ ] 创建 schema 文件
- [ ] 修改 `schemas/__init__.py` 导出
- [ ] 跑 `just check`

---

## Task 4: audit API

**文件：**
- 创建：`app/business/bi/api/audit.py`
- 修改：`app/business/bi/api/__init__.py`
- 修改：`app/business/bi/module.py`
- 修改：`app/core/init_app.py`（guard 排除 `/api/v1/business/bi/audit`）

端点设计：

```python
router = APIRouter(prefix="/audit")

# 分页查询
@router.get("/logs", dependencies=[require_buttons("B_BI_AUDIT_VIEW")])
async def list_logs(obj_in: AuditSearch = Depends()):
    ...

# 详情
@router.get("/logs/{item_id}", dependencies=[require_buttons("B_BI_AUDIT_VIEW")])
async def get_log(item_id: SqidPath):
    ...

# KPI 统计
@router.get("/stats", dependencies=[require_buttons("B_BI_AUDIT_VIEW")])
async def get_stats(query: AuditStatsQuery = Depends()):
    ...

# 按天趋势
@router.get("/trend", dependencies=[require_buttons("B_BI_AUDIT_VIEW")])
async def get_trend(query: TrendQuery = Depends()):
    ...

# 时段热力图
@router.get("/heatmap", dependencies=[require_buttons("B_BI_AUDIT_VIEW")])
async def get_heatmap(days: int = 30):
    ...

# CSV 导出
@router.get("/export", dependencies=[require_buttons("B_BI_AUDIT_EXPORT")])
async def export_csv(
    user_id: int | None = None,
    datasource_id: int | None = None,
    action: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
):
    """返回 StreamingResponse，content_type=text/csv"""
```

- [ ] 创建 `app/business/bi/api/audit.py`
- [ ] 在 `api/__init__.py` 注册
- [ ] 在 `module.py` include audit_router
- [ ] 在 `init_app.py` 的 guard `excluded_paths` 加 `/api/v1/business/bi/audit`
- [ ] 跑 `just check` + 手测 `/api/v1/business/bi/audit/logs`

---

## Task 5: init_data 更新 — 新按钮 + 审计员角色 + 清理定时任务

**文件：**
- 修改：`app/business/bi/init_data.py`

### 5.1 新增按钮
在 `bi_audit` 菜单的 `buttons` 里追加：
```python
{"button_code": "B_BI_AUDIT_EXPORT", "button_desc": "导出审计"},
```

### 5.2 新增 R_BI_AUDITOR 角色
```python
{
    "role_code": "R_BI_AUDITOR",
    "role_name": "BI 审计员",
    "data_scope": "all",
    "menus": ["bi", "bi_audit"],
    "buttons": ["B_BI_AUDIT_VIEW", "B_BI_AUDIT_EXPORT"],
}
```

### 5.3 自动清理定时任务
在 `init()` 里注册每小时跑一次的清理任务（保留 90 天，可配 `.env: BI_AUDIT_RETENTION_DAYS`）。

- [ ] init_data.py 加 `B_BI_AUDIT_EXPORT` 按钮
- [ ] init_data.py 加 `R_BI_AUDITOR` 角色
- [ ] init() 注册清理定时任务
- [ ] `.env.example` 加 `BI_AUDIT_RETENTION_DAYS=90`
- [ ] 跑 `just mm && just check`

---

## Task 6: 前端类型定义 + API service

**文件：**
- 修改：`web/src/typings/api/bi.d.ts`
- 修改：`web/src/service/api/bi.ts`

### 6.1 类型定义
```typescript
declare namespace Api.Bi {
  interface AuditLog {
    id: string;
    userId: number;
    tenantId: number;
    action: string;
    datasourceId: string | null;
    datasourceName?: string | null;
    sqlHash: string | null;
    rowCount: number | null;
    costMs: number | null;
    ip: string | null;
    userAgent: string | null;
    detail: Record<string, any> | null;
    status: string | null;
    createdAt: string;
  }

  interface AuditSearchParams {
    current: number;
    size: number;
    userId?: number;
    datasourceId?: string;
    action?: string;
    status?: string;
    startTime?: string;
    endTime?: string;
    keyword?: string;
  }

  interface AuditStats {
    total: number;
    success: number;
    failed: number;
    totalExportRows: number;
    activeUsers: number;
    avgCostMs: number;
  }

  interface DailyTrendItem {
    date: string;
    count: number;
    success: number;
    failed: number;
  }

  interface HeatmapPoint {
    dayOfWeek: number;
    hour: number;
    count: number;
  }

  interface AuditDetail {
    log: AuditLog;
    sqlText: string | null;
  }
}
```

### 6.2 API service
```typescript
export function fetchBiAuditList(data: Api.Bi.AuditSearchParams) {
  return request<Api.Common.PageResponse<Api.Bi.AuditLog>>({
    url: '/business/bi/audit/logs',
    method: 'get',
    params: data
  });
}

export function fetchBiAuditDetail(id: string) { ... }
export function fetchBiAuditStats(params?) { ... }
export function fetchBiAuditTrend(days: number) { ... }
export function fetchBiAuditHeatmap(days: number) { ... }
export function exportBiAuditCsv(params?) {
  // blob 下载
}
```

- [ ] 修改 `bi.d.ts` 加审计相关类型
- [ ] 修改 `bi.ts` 加 5 个 API 函数
- [ ] 跑 `pnpm typecheck`

---

## Task 7: 前端审计页面

**文件：**
- 创建：`web/src/views/bi/audit/index.vue`
- 创建：`web/src/views/bi/audit/modules/audit-detail-drawer.vue`
- 创建：`web/src/views/bi/audit/modules/audit-trend-chart.vue`
- 创建：`web/src/views/bi/audit/modules/audit-heatmap.vue`
- 修改：`web/src/locales/langs/zh-cn.ts` + `en-us.ts`

### 页面结构

```vue
<template>
  <div class="min-h-500px flex-col-stretch gap-12px">
    <!-- KPI 卡片 -->
    <NGrid :cols="5" :x-gap="12">
      <NGi><StatCard label="总查询" :value="stats.total" /></NGi>
      <NGi><StatCard label="总导出行" :value="stats.totalExportRows" /></NGi>
      <NGi><StatCard label="失败数" :value="stats.failed" type="error" /></NGi>
      <NGi><StatCard label="活跃用户" :value="stats.activeUsers" /></NGi>
      <NGi><StatCard label="平均耗时" :value="`${stats.avgCostMs}ms`" /></NGi>
    </NGrid>

    <!-- Tab 切换 -->
    <NCard :bordered="false" size="small">
      <NTabs v-model:value="activeTab" type="line">
        <NTabPane name="list" tab="审计列表">
          <!-- 过滤区 -->
          <NSearchForm ... />
          <!-- 表格 -->
          <NDataTable ... />
        </NTabPane>
        <NTabPane name="trend" tab="按天趋势">
          <AuditTrendChart :data="trendData" />
        </NTabPane>
        <NTabPane name="heatmap" tab="时段热力图">
          <AuditHeatmap :data="heatmapData" />
        </NTabPane>
      </NTabs>
    </NCard>

    <!-- 导出按钮 -->
    <NButton v-if="hasAuth('B_BI_AUDIT_EXPORT')" @click="handleExport">
      导出 CSV
    </NButton>

    <!-- 详情抽屉 -->
    <AuditDetailDrawer v-model:show="drawerShow" :data="detailData" />
  </div>
</template>
```

### 表格列
| 列 | 说明 |
|---|---|
| 时间 | createdAt |
| 用户 | userId → 用户名 |
| Action | action + 状态 Tag |
| 数据源 | datasourceName |
| SQL 摘要 | sqlHash 前 8 位 + 鼠标悬停显示前 100 字 |
| 行数 | rowCount |
| 耗时 | costMs |
| IP | ip |
| 操作 | [查看] → 打开 Drawer |

### 详情 Drawer 内容
- 审计基本信息（时间/用户/Action/状态/IP/UA）
- 关联数据源
- 原始 SQL（代码块 + 复制按钮）
- 执行明细（行数/耗时/sql_hash）
- detail JSON 树形展示

### 趋势图
ECharts line chart，X 轴日期，双 Y 轴（总数 + 失败数）。

### 热力图
ECharts heatmap，X 轴 24 小时，Y 轴星期 0-6，颜色深浅表示请求量。

- [ ] 创建 4 个 Vue 组件
- [ ] 修改 i18n 文件
- [ ] 跑 `pnpm typecheck` + `pnpm lint`
- [ ] 浏览器实测

---

## Task 8: 门禁 + 浏览器实测

- [ ] `just check`（后端 pytest + 前端 lint/typecheck/test 全过）
- [ ] 重启前后端服务
- [ ] 浏览器登录 → 审计面板
- [ ] 验证 KPI 卡片数据正确
- [ ] 验证列表分页 + 过滤
- [ ] 验证详情 Drawer 展示 SQL
- [ ] 验证趋势图渲染
- [ ] 验证热力图渲染
- [ ] 验证 CSV 导出下载
- [ ] 验证权限：无 B_BI_AUDIT_VIEW 看不到页面，无 B_BI_AUDIT_EXPORT 看不到导出按钮

---

## 风险点

1. **AuditLog 加 FK 到 BiAuditSql**：OneToOne 双向关系需要确认 Tortoise 的 related_name 不冲突
2. **CSV 导出大文件**：StreamingResponse + 分批查询，避免内存爆炸
3. **热力图 168 格查询**：用 GROUP BY day_of_week, hour 单次聚合，避免 N+1
4. **清理定时任务**：用项目的定时任务机制（看是否有现成 scheduler），没有则在 init() 里起 asyncio task
5. **guard 排除 `/audit`**：CSV 导出的 body 不会触发 SQL 注入误判，但 query 参数里的 keyword 可能触发，整段排除
