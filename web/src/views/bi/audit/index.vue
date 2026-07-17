<script setup lang="tsx">
import { computed, h, onMounted, ref, watch } from 'vue';
import {
  NButton,
  NCard,
  NDataTable,
  NDatePicker,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NGrid,
  NGi,
  NInput,
  NSelect,
  NSpace,
  NStatistic,
  NTabPane,
  NTabs,
  NTag
} from 'naive-ui';
import { useEcharts } from '@/hooks/common/echarts';
import type { ECOption } from '@/hooks/common/echarts';
import { useAuth } from '@/hooks/business/auth';
import {
  exportBiAuditCsv,
  fetchBiAuditDetail,
  fetchBiAuditHeatmap,
  fetchBiAuditList,
  fetchBiAuditStats,
  fetchBiAuditTrend
} from '@/service/api';

const { hasAuth } = useAuth();

const PAGE_SIZE = 20;

const activeTab = ref<'list' | 'trend' | 'heatmap'>('list');

// ===== KPI 状态 =====
const stats = ref<Api.Bi.AuditStats>({
  total: 0,
  success: 0,
  failed: 0,
  totalExportRows: 0,
  activeUsers: 0,
  avgCostMs: 0
});
const statsLoading = ref(false);

async function loadStats() {
  statsLoading.value = true;
  try {
    const { data, error } = await fetchBiAuditStats();
    if (!error && data) stats.value = data;
  } finally {
    statsLoading.value = false;
  }
}

// ===== 列表状态 =====
const search = ref<Api.Bi.AuditSearchParams>({
  current: 1,
  size: PAGE_SIZE
});
const list = ref<Api.Bi.AuditLog[]>([]);
const total = ref(0);
const listLoading = ref(false);
const timeRange = ref<[number, number] | null>(null);
const userIdInput = ref<string>('');

function setTimeRange(v: number | [number, number] | null) {
  timeRange.value = Array.isArray(v) ? (v as [number, number]) : null;
}

function applyUserId() {
  const n = Number(userIdInput.value);
  search.value.userId = Number.isFinite(n) && userIdInput.value !== '' ? n : undefined;
}

const actionOptions: { label: string; value: string }[] = [
  { label: '查询 query', value: 'query' },
  { label: '导出 export', value: 'export' },
  { label: '元数据同步 metadata_sync', value: 'metadata_sync' },
  { label: '数据源创建 datasource_create', value: 'datasource_create' },
  { label: '数据源更新 datasource_update', value: 'datasource_update' },
  { label: '数据源删除 datasource_delete', value: 'datasource_delete' },
  { label: '提供商创建 provider_create', value: 'provider_create' },
  { label: '提供商更新 provider_update', value: 'provider_update' },
  { label: '提供商删除 provider_delete', value: 'provider_delete' },
  { label: '模型创建 model_create', value: 'model_create' },
  { label: '模型更新 model_update', value: 'model_update' },
  { label: '模型删除 model_delete', value: 'model_delete' }
];

const statusOptions: { label: string; value: string }[] = [
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' }
];

async function loadList() {
  listLoading.value = true;
  applyUserId();
  try {
    const params: Api.Bi.AuditSearchParams = { ...search.value };
    if (timeRange.value) {
      params.startTime = new Date(timeRange.value[0]).toISOString();
      params.endTime = new Date(timeRange.value[1]).toISOString();
    }
    const { data, error } = await fetchBiAuditList(params);
    if (!error && data) {
      list.value = data.records ?? [];
      total.value = data.total ?? 0;
    }
  } finally {
    listLoading.value = false;
  }
}

function handleReset() {
  search.value = { current: 1, size: PAGE_SIZE };
  timeRange.value = null;
  loadList();
}

function statusType(s: string | null | undefined): 'success' | 'error' | 'default' {
  if (s === 'success') return 'success';
  if (s === 'failed') return 'error';
  return 'default';
}

// 状态列渲染（成功/失败根据 action + detail.status 综合判断）
function rowStatus(row: Api.Bi.AuditLog): string | null {
  if (row.status) return row.status;
  // 没 status 的 action（CRUD）默认 success
  return 'success';
}

const columns = computed(() => [
  {
    key: 'createdAt',
    title: '时间',
    width: 170,
    render: (r: Api.Bi.AuditLog) => (r.createdAt ? r.createdAt.replace('T', ' ').slice(0, 19) : '-')
  },
  { key: 'userId', title: '用户', width: 80, render: (r: Api.Bi.AuditLog) => String(r.userId) },
  {
    key: 'action',
    title: 'Action',
    width: 180,
    render: (r: Api.Bi.AuditLog) => h(NTag, { size: 'small', type: 'info' }, () => r.action)
  },
  {
    key: 'status',
    title: '状态',
    width: 80,
    render: (r: Api.Bi.AuditLog) =>
      h(NTag, { size: 'small', type: statusType(rowStatus(r)) }, () => rowStatus(r) || '-')
  },
  { key: 'datasourceName', title: '数据源', width: 140, render: (r: Api.Bi.AuditLog) => r.datasourceName || '-' },
  {
    key: 'sqlHash',
    title: 'SQL 摘要',
    width: 140,
    render: (r: Api.Bi.AuditLog) => (r.sqlHash ? r.sqlHash.slice(0, 12) : '-')
  },
  { key: 'rowCount', title: '行数', width: 80, render: (r: Api.Bi.AuditLog) => r.rowCount ?? '-' },
  {
    key: 'costMs',
    title: '耗时',
    width: 80,
    render: (r: Api.Bi.AuditLog) => (r.costMs != null ? `${r.costMs}ms` : '-')
  },
  { key: 'ip', title: 'IP', width: 130, render: (r: Api.Bi.AuditLog) => r.ip || '-' },
  {
    key: 'op',
    title: '操作',
    width: 80,
    fixed: 'right' as const,
    render: (r: Api.Bi.AuditLog) =>
      h(NButton, { size: 'tiny', type: 'primary', text: true, onClick: () => openDetail(r) }, () => '查看')
  }
]);

// ===== 详情 Drawer =====
const drawerShow = ref(false);
const detailLoading = ref(false);
const detail = ref<Api.Bi.AuditDetail | null>(null);

async function openDetail(row: Api.Bi.AuditLog) {
  drawerShow.value = true;
  detailLoading.value = true;
  try {
    const { data, error } = await fetchBiAuditDetail(row.id);
    if (!error) detail.value = data ?? null;
  } finally {
    detailLoading.value = false;
  }
}

function handleCopy(text: string) {
  navigator.clipboard?.writeText(text);
  window.$message?.success('已复制');
}

// ===== 趋势 =====
const trendLoading = ref(false);
const trend = ref<Api.Bi.DailyTrendItem[]>([]);

const trendOption = computed<ECOption>(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['总数', '成功', '失败'], top: 0 },
  grid: { left: 50, right: 30, top: 40, bottom: 30 },
  xAxis: { type: 'category', data: trend.value.map(t => t.date) },
  yAxis: { type: 'value' },
  series: [
    {
      name: '总数',
      type: 'line',
      smooth: true,
      data: trend.value.map(t => t.count),
      itemStyle: { color: '#2080f0' }
    },
    {
      name: '成功',
      type: 'line',
      smooth: true,
      data: trend.value.map(t => t.success),
      itemStyle: { color: '#18a058' }
    },
    {
      name: '失败',
      type: 'line',
      smooth: true,
      data: trend.value.map(t => t.failed),
      itemStyle: { color: '#d03050' }
    }
  ]
}));

const { domRef: trendChartRef, updateOptions: updateTrendChart } = useEcharts(() => trendOption.value, {
  onRender() {}
});

async function loadTrend() {
  trendLoading.value = true;
  try {
    const { data, error } = await fetchBiAuditTrend({ days: 30 });
    if (!error && data) trend.value = data;
    await updateTrendChart();
  } finally {
    trendLoading.value = false;
  }
}

// ===== 热力图 =====
const heatmapLoading = ref(false);
const heatmap = ref<Api.Bi.HeatmapPoint[]>([]);

const DAY_LABELS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];

const heatmapOption = computed<ECOption>(() => {
  // 7*24 → ECharts heatmap data
  const data: [number, number, number][] = heatmap.value.map(p => [p.hour, p.dayOfWeek, p.count]);
  const maxCount = heatmap.value.reduce((m, p) => (p.count > m ? p.count : m), 0);
  return {
    tooltip: {
      position: 'top',
      formatter: (params: any) =>
        `${DAY_LABELS[params.data[1]]} ${params.data[0]}:00 - ${params.data[0] + 1}:00<br/>次数: ${params.data[2]}`
    },
    grid: { left: 60, right: 20, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: Array.from({ length: 24 }, (_, i) => `${i}`), splitArea: { show: true } },
    yAxis: { type: 'category', data: DAY_LABELS, splitArea: { show: true } },
    visualMap: {
      min: 0,
      max: Math.max(maxCount, 1),
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: { color: ['#f0f9ff', '#0ea5e9', '#1e40af'] }
    },
    series: [
      {
        name: '请求量',
        type: 'heatmap',
        data,
        emphasis: { itemStyle: { borderColor: '#000', borderWidth: 1 } }
      }
    ]
  };
});

const { domRef: heatmapChartRef, updateOptions: updateHeatmapChart } = useEcharts(() => heatmapOption.value, {
  onRender() {}
});

async function loadHeatmap() {
  heatmapLoading.value = true;
  try {
    const { data, error } = await fetchBiAuditHeatmap({ days: 30 });
    if (!error && data) heatmap.value = data;
    await updateHeatmapChart();
  } finally {
    heatmapLoading.value = false;
  }
}

watch(activeTab, t => {
  if (t === 'trend') loadTrend();
  if (t === 'heatmap') loadHeatmap();
});

// ===== CSV 导出 =====
async function handleExport() {
  try {
    const params: Api.Bi.AuditSearchParams = { ...search.value, current: 1, size: 10000 };
    if (timeRange.value) {
      params.startTime = new Date(timeRange.value[0]).toISOString();
      params.endTime = new Date(timeRange.value[1]).toISOString();
    }
    const { data: blob, error } = await exportBiAuditCsv(params);
    if (error || !blob) {
      window.$message?.error('导出失败');
      return;
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `bi_audit_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    window.$message?.success('已导出 CSV');
  } catch (e) {
    window.$message?.error('导出失败');
    console.error(e);
  }
}

// ===== 初始化 =====
onMounted(() => {
  loadStats();
  loadList();
});
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-12px">
    <!-- KPI 卡片 -->
    <NGrid :cols="5" :x-gap="12" responsive="screen" :item-responsive="true">
      <NGi span="1 m:1 l:1">
        <NCard :bordered="false" size="small" class="card-wrapper">
          <NStatistic label="总操作数" :value="stats.total" />
        </NCard>
      </NGi>
      <NGi>
        <NCard :bordered="false" size="small" class="card-wrapper">
          <NStatistic label="成功" :value="stats.success" />
        </NCard>
      </NGi>
      <NGi>
        <NCard :bordered="false" size="small" class="card-wrapper">
          <NStatistic label="失败" :value="stats.failed" />
        </NCard>
      </NGi>
      <NGi>
        <NCard :bordered="false" size="small" class="card-wrapper">
          <NStatistic label="活跃用户" :value="stats.activeUsers" />
        </NCard>
      </NGi>
      <NGi>
        <NCard :bordered="false" size="small" class="card-wrapper">
          <NStatistic label="平均耗时" :value="`${stats.avgCostMs}ms`" />
        </NCard>
      </NGi>
    </NGrid>

    <!-- Tab 切换 -->
    <NCard :bordered="false" size="small" class="card-wrapper">
      <NTabs v-model:value="activeTab" type="line" animated>
        <!-- 列表 -->
        <NTabPane name="list" tab="审计列表">
          <div class="mb-12px flex flex-wrap items-center gap-8px">
            <NDatePicker
              :value="timeRange as any"
              type="datetimerange"
              clearable
              placeholder="时间范围"
              style="width: 360px"
              @update:value="setTimeRange"
            />
            <NInput
              :value="userIdInput"
              placeholder="用户ID"
              clearable
              style="width: 120px"
              @update:value="userIdInput = $event"
              @keyup.enter="
                applyUserId();
                search.current = 1;
                loadList();
              "
            />
            <NInput
              v-model:value="search.keyword"
              placeholder="SQL哈希 / IP"
              clearable
              style="width: 180px"
              @keyup.enter="
                search.current = 1;
                loadList();
              "
            />
            <NSelect
              v-model:value="search.action"
              :options="actionOptions"
              placeholder="操作类型"
              clearable
              style="width: 220px"
            />
            <NSelect
              v-model:value="search.status"
              :options="statusOptions"
              placeholder="状态"
              clearable
              style="width: 120px"
            />
            <NButton
              type="primary"
              @click="
                search.current = 1;
                loadList();
              "
            >
              查询
            </NButton>
            <NButton @click="handleReset">重置</NButton>
            <NButton v-if="hasAuth('B_BI_AUDIT_EXPORT')" type="primary" ghost @click="handleExport">导出 CSV</NButton>
          </div>
          <NDataTable
            :columns="columns"
            :data="list"
            :loading="listLoading"
            :row-key="(r: Api.Bi.AuditLog) => r.id"
            :pagination="{
              page: search.current,
              pageSize: search.size,
              itemCount: total,
              showSizePicker: true,
              pageSizes: [20, 50, 100]
            }"
            :scroll-x="1200"
            size="small"
            @update:page="(p: number) => { search.current = p; loadList(); }"
            @update:page-size="(s: number) => { search.size = s; search.current = 1; loadList(); }"
          />
        </NTabPane>

        <!-- 趋势 -->
        <NTabPane name="trend" tab="按天趋势">
          <div ref="trendChartRef" style="width: 100%; height: 420px" />
          <NEmpty v-if="!trendLoading && trend.length === 0" description="暂无数据" />
        </NTabPane>

        <!-- 热力图 -->
        <NTabPane name="heatmap" tab="时段热力图">
          <div ref="heatmapChartRef" style="width: 100%; height: 420px" />
          <NEmpty v-if="!heatmapLoading && heatmap.length === 0" description="暂无数据" />
        </NTabPane>
      </NTabs>
    </NCard>

    <!-- 详情 Drawer -->
    <NDrawer v-model:show="drawerShow" :width="640">
      <NDrawerContent title="审计详情" :native-scrollbar="false" closable>
        <NSpin :show="detailLoading">
          <div v-if="detail" class="flex-col gap-12px">
            <NCard title="基本信息" size="small" :bordered="false">
              <div class="detail-row">
                <span class="label">时间</span>
                <span class="value">{{ detail.createdAt || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="label">用户</span>
                <span class="value">{{ detail.userId }}</span>
              </div>
              <div class="detail-row">
                <span class="label">操作</span>
                <span class="value">{{ detail.action }}</span>
              </div>
              <div class="detail-row">
                <span class="label">状态</span>
                <span class="value">{{ detail.status || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="label">数据源</span>
                <span class="value">{{ detail.datasourceName || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="label">IP</span>
                <span class="value">{{ detail.ip || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="label">UA</span>
                <span class="value">{{ detail.userAgent || '-' }}</span>
              </div>
            </NCard>

            <NCard
              v-if="detail.rowCount != null || detail.costMs != null"
              title="执行明细"
              size="small"
              :bordered="false"
            >
              <div class="detail-row">
                <span class="label">SQL 哈希</span>
                <span class="value break-all">{{ detail.sqlHash || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="label">行数</span>
                <span class="value">{{ detail.rowCount ?? '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="label">耗时</span>
                <span class="value">{{ detail.costMs != null ? detail.costMs + 'ms' : '-' }}</span>
              </div>
            </NCard>

            <NCard v-if="detail.sqlText" title="原始 SQL" size="small" :bordered="false">
              <NSpace align="center" :wrap="false" class="mb-6px">
                <NButton size="tiny" @click="handleCopy(detail.sqlText!)">复制</NButton>
              </NSpace>
              <pre class="sql-pre">{{ detail.sqlText }}</pre>
            </NCard>

            <NCard v-if="detail.detail" title="Detail" size="small" :bordered="false">
              <pre class="sql-pre">{{ JSON.stringify(detail.detail, null, 2) }}</pre>
            </NCard>
          </div>
        </NSpin>
      </NDrawerContent>
    </NDrawer>
  </div>
</template>

<style scoped>
.detail-row {
  display: flex;
  padding: 4px 0;
  font-size: 13px;
}
.detail-row .label {
  width: 80px;
  color: #999;
}
.detail-row .value {
  flex: 1;
  word-break: break-all;
}
.sql-pre {
  background: #f6f8fa;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.5;
  max-height: 360px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}
.break-all {
  word-break: break-all;
}
</style>
