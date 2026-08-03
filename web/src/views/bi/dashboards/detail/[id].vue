<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { NButton, NDrawer, NDrawerContent, NEmpty, NInput, NSpace, NSpin, NTag, NTooltip } from 'naive-ui';
import { GridStack } from 'gridstack';
import type { GridStackNode, GridStackWidget } from 'gridstack';
import { createApp, type App as VueApp } from 'vue';
import 'gridstack/dist/gridstack.min.css';
import { fetchBiChartList } from '@/service/api/bi-chart';
import {
  fetchBiDashboardDetail,
  fetchPreviewBiDashboard,
  fetchRefreshBiDashboard,
  fetchUpdateBiDashboard
} from '@/service/api/bi-dashboard';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';
import DashboardChartCard from '../../shared/dashboard-chart-card.vue';

defineOptions({ name: 'BiDashboardDetail' });

const route = useRoute();
const router = useRouter();
const { hasAuth } = useAuth();

const dashboardId = computed(() => route.params.id as string);
const isEditMode = computed(() => route.query.mode === 'edit');

const loading = ref<boolean>(false);
const refreshing = ref<boolean>(false);
const saving = ref<boolean>(false);

// 仪表盘元信息
const dashboardName = ref<string>('');
const dashboardDesc = ref<string>('');

// 编辑模式 layout（可拖拽修改）
const editLayout = ref<Api.Bi.BiDashboardItem[]>([]);
// 编辑模式表单
const editName = ref<string>('');
const editDesc = ref<string>('');

// 查看模式：刷新结果（按 chartId 索引）
const refreshItems = ref<Record<string, Api.Bi.BiDashboardRefreshItem>>({});
const viewLayout = ref<Api.Bi.BiDashboardItem[]>([]);
const totalElapsedMs = ref<number>(0);

// 编辑模式：预览（用 BiChart 已有快照，按 chartId 索引）
const previewItems = ref<Record<string, Api.Bi.BiDashboardPreviewItem>>({});

// gridstack 实例与挂载的 Vue 应用
const gridRef = ref<HTMLElement>();
let grid: GridStack | null = null;
const mountedApps = new Map<string, VueApp>();

// 图表选择器抽屉
const showChartPicker = ref<boolean>(false);
const chartList = ref<Api.Bi.BiChart[]>([]);
const chartLoading = ref<boolean>(false);
const existingChartIds = computed(() => new Set(editLayout.value.map(i => i.chartId)));

// ---------------- 数据加载 ----------------

async function loadViewMode() {
  loading.value = true;
  try {
    const { data: detail, error: e1 } = await fetchBiDashboardDetail(dashboardId.value);
    if (e1 || !detail) return;
    dashboardName.value = detail.name;
    dashboardDesc.value = detail.description || '';
    viewLayout.value = detail.layout.items || [];

    // 查看模式：全量刷新
    const { data: refreshData, error: e2 } = await fetchRefreshBiDashboard(dashboardId.value);
    if (!e2 && refreshData) {
      refreshItems.value = {};
      refreshData.items.forEach(item => {
        refreshItems.value[item.chartId] = item;
      });
      totalElapsedMs.value = refreshData.totalElapsedMs;
    }
  } finally {
    loading.value = false;
  }
}

async function loadEditMode() {
  loading.value = true;
  try {
    const { data: detail, error: e1 } = await fetchBiDashboardDetail(dashboardId.value);
    if (e1 || !detail) return;
    dashboardName.value = detail.name;
    dashboardDesc.value = detail.description || '';
    editName.value = detail.name;
    editDesc.value = detail.description || '';
    editLayout.value = (detail.layout.items || []).map(i => ({ ...i }));

    // 编辑模式：预览不刷新
    const { data: previewData, error: e2 } = await fetchPreviewBiDashboard(dashboardId.value);
    if (!e2 && previewData) {
      previewItems.value = {};
      previewData.items.forEach(item => {
        previewItems.value[item.chartId] = item;
      });
    }
  } finally {
    loading.value = false;
  }
}

async function loadDashboard() {
  if (isEditMode.value) {
    await loadEditMode();
  } else {
    await loadViewMode();
  }
}

// ---------------- gridstack 渲染 ----------------

function destroyGrid() {
  // 先卸载挂载的 Vue 应用
  mountedApps.forEach(app => app.unmount());
  mountedApps.clear();
  // 销毁 gridstack
  if (grid) {
    grid.destroy(false);
    grid = null;
  }
}

function renderGrid() {
  if (!gridRef.value) return;
  destroyGrid();

  const items = isEditMode.value ? editLayout.value : viewLayout.value;

  grid = GridStack.init(
    {
      column: 12,
      margin: 8,
      cellHeight: 80,
      staticGrid: !isEditMode.value,
      disableDrag: !isEditMode.value,
      disableResize: !isEditMode.value,
      acceptWidgets: false,
      float: false
    },
    gridRef.value
  );

  if (!items.length) {
    return;
  }

  const widgets: GridStackWidget[] = items.map(item => ({
    id: item.chartId,
    x: item.x,
    y: item.y,
    w: item.w,
    h: item.h,
    content: `<div class="dashboard-item-content" data-chart-id="${item.chartId}"></div>`
  }));

  if (!grid) return;
  grid.load(widgets);

  // 监听布局变化（仅编辑模式）
  if (isEditMode.value) {
    grid.on('change', (_event: unknown, nodes: GridStackNode[]) => {
      nodes.forEach(node => {
        const id = String(node.id);
        const existing = editLayout.value.find(i => i.chartId === id);
        if (existing) {
          existing.x = node.x ?? existing.x;
          existing.y = node.y ?? existing.y;
          existing.w = node.w ?? existing.w;
          existing.h = node.h ?? existing.h;
        }
      });
    });
    grid.on('removed', (_event: unknown, nodes: GridStackNode[]) => {
      const removedIds = new Set(nodes.map(n => String(n.id)));
      editLayout.value = editLayout.value.filter(i => !removedIds.has(i.chartId));
      // 清理已删除项的 Vue 应用
      removedIds.forEach(id => {
        const app = mountedApps.get(id);
        if (app) {
          app.unmount();
          mountedApps.delete(id);
        }
      });
    });
  }

  // 挂载 Vue 组件到每个 grid item 的内容容器
  nextTick(() => {
    mountChartCards();
  });
}

function mountChartCards() {
  if (!gridRef.value) return;
  const containers = gridRef.value.querySelectorAll<HTMLElement>('.dashboard-item-content');
  containers.forEach(container => {
    const chartId = container.dataset.chartId;
    if (!chartId) return;
    // 已挂载则跳过
    if (mountedApps.has(chartId)) return;

    const item = isEditMode.value ? (previewItems.value[chartId] ?? null) : (refreshItems.value[chartId] ?? null);

    const app = createApp(DashboardChartCard, {
      chartId,
      item: item ?? null,
      isEditMode: isEditMode.value,
      onRemove: (id: string) => removeChart(id)
    });
    app.mount(container);
    mountedApps.set(chartId, app);
  });
}

// ---------------- 编辑模式操作 ----------------

async function loadCharts() {
  chartLoading.value = true;
  try {
    const { data, error } = await fetchBiChartList({ current: 1, size: 200 });
    if (!error && data) {
      chartList.value = data.records;
    }
  } finally {
    chartLoading.value = false;
  }
}

function addChart(chart: Api.Bi.BiChart) {
  if (existingChartIds.value.has(chart.id)) {
    window.$message?.warning($t('page.bi.dashboard.addChart'));
    return;
  }
  const newItem: Api.Bi.BiDashboardItem = {
    chartId: chart.id,
    x: 0,
    y: 0,
    w: 6,
    h: 3
  };
  editLayout.value.push(newItem);

  // 同步 previewItems：从图表列表拿快照
  previewItems.value[chart.id] = {
    chartId: chart.id,
    chartMeta: {
      name: chart.name,
      chartType: chart.chartType,
      xCol: chart.xCol ?? null,
      yCol: chart.yCol ?? null
    },
    resultSnapshot: chart.resultSnapshot
  };

  if (grid) {
    grid.addWidget({
      id: newItem.chartId,
      x: newItem.x,
      y: newItem.y,
      w: newItem.w,
      h: newItem.h,
      content: `<div class="dashboard-item-content" data-chart-id="${newItem.chartId}"></div>`
    });
    nextTick(() => {
      mountChartCards();
    });
  }
  showChartPicker.value = false;
}

function removeChart(chartId: string) {
  if (!grid) return;
  const el = gridRef.value?.querySelector<HTMLElement>(`.grid-stack-item[gs-id="${chartId}"]`);
  if (el) {
    grid.removeWidget(el, true);
  }
  // removed 事件会处理 editLayout 和 mountedApps 的清理
}

async function handleSave() {
  if (!editName.value.trim()) {
    window.$message?.warning($t('page.bi.dashboard.namePlaceholder'));
    return;
  }
  saving.value = true;
  try {
    const { error } = await fetchUpdateBiDashboard(dashboardId.value, {
      name: editName.value.trim(),
      description: editDesc.value.trim() || null,
      layout: { items: editLayout.value }
    });
    if (!error) {
      window.$message?.success($t('page.bi.dashboard.saveSuccess'));
      router.replace({ name: 'bi_dashboard-detail', params: { id: dashboardId.value } });
    }
  } finally {
    saving.value = false;
  }
}

function handleCancelEdit() {
  router.replace({ name: 'bi_dashboard-detail', params: { id: dashboardId.value } });
}

function enterEdit() {
  router.replace({ name: 'bi_dashboard-detail', params: { id: dashboardId.value }, query: { mode: 'edit' } });
}

async function handleRefresh() {
  refreshing.value = true;
  try {
    const { data, error } = await fetchRefreshBiDashboard(dashboardId.value);
    if (!error && data) {
      refreshItems.value = {};
      data.items.forEach(item => {
        refreshItems.value[item.chartId] = item;
      });
      totalElapsedMs.value = data.totalElapsedMs;
      window.$message?.success($t('page.bi.dashboard.refreshSuccess'));
      // 重新挂载图表卡片
      nextTick(() => {
        remountAllCards();
      });
    }
  } finally {
    refreshing.value = false;
  }
}

function remountAllCards() {
  // 卸载所有
  mountedApps.forEach(app => app.unmount());
  mountedApps.clear();
  // 重新挂载
  mountChartCards();
}

// ---------------- 生命周期 ----------------

onMounted(async () => {
  await loadDashboard();
  nextTick(() => {
    renderGrid();
  });
});

watch(isEditMode, async () => {
  await loadDashboard();
  nextTick(() => {
    renderGrid();
  });
});

onUnmounted(() => {
  destroyGrid();
});

function chartTypeLabel(type: string): string {
  const labels: Record<string, App.I18n.I18nKey> = {
    bar: 'page.bi.metrics.chartTypes.bar',
    line: 'page.bi.metrics.chartTypes.line',
    area: 'page.bi.metrics.chartTypes.area',
    pie: 'page.bi.metrics.chartTypes.pie',
    scatter: 'page.bi.metrics.chartTypes.scatter',
    radar: 'page.bi.metrics.chartTypes.radar',
    funnel: 'page.bi.metrics.chartTypes.funnel',
    gauge: 'page.bi.metrics.chartTypes.gauge',
    heatmap: 'page.bi.metrics.chartTypes.heatmap'
  };
  const key = labels[type];
  return key ? $t(key) : type;
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <!-- 顶部工具栏 -->
    <NCard :bordered="false" size="small" class="card-wrapper">
      <div class="flex flex-wrap items-center justify-between gap-12px">
        <div class="flex flex-col gap-4px">
          <div class="flex items-center gap-8px">
            <NButton size="small" quaternary @click="router.push({ name: 'bi_dashboards' })">
              <template #icon><icon-ic-round-arrow-back class="text-icon" /></template>
              {{ $t('page.bi.dashboard.backToList') }}
            </NButton>
            <h2 v-if="!isEditMode" class="m-0 text-18px font-600">{{ dashboardName }}</h2>
            <NInput
              v-else
              v-model:value="editName"
              :placeholder="$t('page.bi.dashboard.namePlaceholder')"
              style="width: 240px"
              maxlength="100"
            />
          </div>
          <div class="flex items-center gap-8px text-12px text-gray-500">
            <span v-if="!isEditMode && dashboardDesc">{{ dashboardDesc }}</span>
            <NInput
              v-else-if="isEditMode"
              v-model:value="editDesc"
              :placeholder="$t('page.bi.dashboard.descPlaceholder')"
              style="width: 320px"
              size="small"
            />
            <span v-if="!isEditMode && totalElapsedMs > 0">·</span>
            <span v-if="!isEditMode && totalElapsedMs > 0">
              {{ $t('page.bi.dashboard.totalElapsed', { ms: totalElapsedMs }) }}
            </span>
          </div>
        </div>
        <NSpace :size="8" wrap>
          <template v-if="isEditMode">
            <NButton
              size="small"
              @click="
                showChartPicker = true;
                loadCharts();
              "
            >
              <template #icon><icon-ic-round-add class="text-icon" /></template>
              {{ $t('page.bi.dashboard.addChart') }}
            </NButton>
            <NButton size="small" type="primary" :loading="saving" @click="handleSave">
              <template #icon><icon-ic-round-save class="text-icon" /></template>
              {{ $t('page.bi.dashboard.save') }}
            </NButton>
            <NButton size="small" @click="handleCancelEdit">{{ $t('page.bi.dashboard.cancel') }}</NButton>
          </template>
          <template v-else>
            <NButton size="small" type="primary" ghost :loading="refreshing" @click="handleRefresh">
              <template #icon><icon-ic-round-refresh class="text-icon" /></template>
              {{ $t('page.bi.dashboard.refreshAll') }}
            </NButton>
            <NButton v-if="hasAuth('B_BI_DASHBOARD_EDIT')" size="small" type="primary" @click="enterEdit">
              <template #icon><icon-ic-round-edit class="text-icon" /></template>
              {{ $t('page.bi.dashboard.edit') }}
            </NButton>
          </template>
        </NSpace>
      </div>
    </NCard>

    <!-- 画布 -->
    <NCard :bordered="false" size="small" class="card-wrapper flex-1-hidden">
      <NSpin :show="loading || refreshing">
        <div ref="gridRef" class="grid-stack"></div>
        <NEmpty
          v-if="!loading && (isEditMode ? editLayout : viewLayout).length === 0"
          :description="$t('page.bi.dashboard.emptyLayout')"
          class="py-80px"
        />
      </NSpin>
    </NCard>

    <!-- 图表选择器抽屉 -->
    <NDrawer v-model:show="showChartPicker" :width="420">
      <NDrawerContent :title="$t('page.bi.dashboard.addChart')" closable>
        <NSpin :show="chartLoading">
          <NEmpty v-if="!chartList.length && !chartLoading" :description="$t('page.bi.chart.empty')" class="py-40px" />
          <div v-else class="flex flex-col gap-8px">
            <div
              v-for="chart in chartList"
              :key="chart.id"
              class="chart-pick-item"
              :class="{ 'chart-pick-item-disabled': existingChartIds.has(chart.id) }"
              @click="!existingChartIds.has(chart.id) && addChart(chart)"
            >
              <div class="flex items-center justify-between gap-8px">
                <div class="flex flex-col gap-2px flex-1 min-w-0">
                  <NTooltip trigger="hover">
                    <template #trigger>
                      <span class="text-14px font-500 truncate">{{ chart.name }}</span>
                    </template>
                    {{ chart.name }}
                  </NTooltip>
                  <div class="flex items-center gap-6px text-12px text-gray-500">
                    <NTag size="small" type="primary">{{ chartTypeLabel(chart.chartType) }}</NTag>
                    <span class="truncate">{{ chart.resultSnapshot?.rowCount ?? 0 }} rows</span>
                  </div>
                </div>
                <NButton v-if="!existingChartIds.has(chart.id)" size="small" type="primary" ghost quaternary>
                  <icon-ic-round-add class="text-icon" />
                </NButton>
                <NTag v-else size="small" type="success">✓</NTag>
              </div>
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
:deep(.grid-stack-item-content) {
  padding: 0;
  overflow: hidden;
}
</style>

<style>
/* 全局样式：gridstack item 内动态挂载的图表卡片 */
.dashboard-item-content {
  width: 100%;
  height: 100%;
  overflow: hidden;
}
.chart-pick-item {
  padding: 12px;
  border: 1px solid var(--n-border-color, #e0e0e6);
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.2s ease;
}
.chart-pick-item:hover {
  border-color: var(--n-color-primary, #2080f0);
}
.chart-pick-item-disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
.chart-pick-item-disabled:hover {
  border-color: var(--n-border-color, #e0e0e6);
}
</style>
