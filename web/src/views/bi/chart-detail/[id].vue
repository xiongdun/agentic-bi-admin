<script setup lang="tsx">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { NButton, NCode, NCollapse, NCollapseItem, NDropdown, NPopconfirm, NSpace, NSpin, NTag } from 'naive-ui';
import {
  fetchBiChart,
  fetchDeleteBiChart,
  fetchDisableBiChartShare,
  fetchEnableBiChartShare,
  fetchRefreshBiChart
} from '@/service/api/bi-chart';
import { fetchBiChartCsvExport, fetchBiChartsExcelExport } from '@/service/api/bi-export';
import { fetchBiDatasourceList } from '@/service/api/bi';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';
import { useEcharts, type ECOption } from '@/hooks/common/echarts';
import { buildChartOption, type ChartType } from '../shared/chart-config';
import { exportChartPdf } from '../shared/export-pdf';

defineOptions({ name: 'BiChartDetail' });

const route = useRoute();
const router = useRouter();
const { hasAuth } = useAuth();

const loading = ref<boolean>(false);
const refreshing = ref<boolean>(false);
const chart = ref<Api.Bi.BiChart | null>(null);
const datasourceMap = ref<Record<string, Api.Bi.BiDatasource>>({});

const chartId = computed(() => route.params.id as string);

const chartOption = computed<ECOption>(() => {
  if (!chart.value?.resultSnapshot?.rows?.length || !chart.value.xCol || !chart.value.yCol) {
    return {} as ECOption;
  }
  return buildChartOption(
    {
      columns: chart.value.resultSnapshot.columns,
      rows: chart.value.resultSnapshot.rows
    },
    (chart.value.chartType as ChartType) || 'bar',
    chart.value.xCol,
    chart.value.yCol
  );
});

const {
  domRef: chartRef,
  chart: chartInstance,
  setOptions: setChartOptions
} = useEcharts(() => ({}) as ECOption, {
  onRender: instance => {
    if (Object.keys(chartOption.value).length) {
      instance.setOption({ ...chartOption.value, backgroundColor: 'transparent' });
    }
  }
});

const shareLink = computed(() => {
  if (!chart.value?.isPublic || !chart.value.shareToken) return '';
  return `${window.location.origin}/bi/share/${chart.value.shareToken}`;
});

function datasourceName(id: string): string {
  return datasourceMap.value[id]?.name || id;
}

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

function parseTags(tags: string | null | undefined): string[] {
  if (!tags) return [];
  return tags
    .split(',')
    .map(t => t.trim())
    .filter(Boolean);
}

function formatSnapshotAt(iso: string): string {
  if (!iso) return '-';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

async function loadDatasources() {
  const { data } = await fetchBiDatasourceList({ current: 1, size: 999 });
  if (data?.records) {
    const map: Record<string, Api.Bi.BiDatasource> = {};
    data.records.forEach(d => {
      map[d.id] = d;
    });
    datasourceMap.value = map;
  }
}

async function loadDetail() {
  loading.value = true;
  try {
    const { data } = await fetchBiChart(chartId.value);
    if (data) {
      chart.value = data;
    }
  } finally {
    loading.value = false;
  }
}

async function handleRefresh() {
  if (!chart.value) return;
  refreshing.value = true;
  try {
    const { data, error } = await fetchRefreshBiChart(chart.value.id);
    if (!error && data) {
      chart.value = data;
      window.$message?.success($t('page.bi.chart.refreshSuccess'));
      // 触发图表重绘
      if (Object.keys(chartOption.value).length) {
        setChartOptions(chartOption.value);
      }
    }
  } finally {
    refreshing.value = false;
  }
}

async function handleToggleShare() {
  if (!chart.value) return;
  if (chart.value.isPublic) {
    const { error } = await fetchDisableBiChartShare(chart.value.id);
    if (!error) {
      chart.value.isPublic = false;
      chart.value.shareToken = null;
      window.$message?.success($t('page.bi.chart.disableShare'));
    }
  } else {
    const { data, error } = await fetchEnableBiChartShare(chart.value.id);
    if (!error && data) {
      chart.value.isPublic = true;
      chart.value.shareToken = data.shareToken;
      window.$message?.success($t('page.bi.chart.enableShare'));
    }
  }
}

async function copyShareLink() {
  if (!shareLink.value) return;
  try {
    await navigator.clipboard.writeText(shareLink.value);
    window.$message?.success($t('page.bi.chart.copySuccess'));
  } catch {
    window.$message?.error($t('common.error'));
  }
}

function exportPng() {
  // 复用图表实例导出 PNG
  const inst = (chartRef.value as any)?.getEchartsInstance?.();
  if (!inst) return;
  const url = inst.getDataURL({ pixelRatio: 2, backgroundColor: '#fff' });
  const a = document.createElement('a');
  a.href = url;
  a.download = `bi-chart-${chart.value?.id}.png`;
  a.click();
}

const exportOptions = [
  { label: $t('page.bi.export.csv'), key: 'csv' },
  { label: $t('page.bi.export.excel'), key: 'excel' },
  { label: $t('page.bi.export.pdf'), key: 'pdf' }
];

/** 触发 Blob 下载（a.click + revokeObjectURL） */
function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

async function handleExportSelect(key: string) {
  if (!chart.value) return;
  try {
    if (key === 'csv') {
      const { data: blob, error } = await fetchBiChartCsvExport(chart.value.id);
      if (error || !blob) return;
      triggerBlobDownload(blob, `${chart.value.name}.csv`);
    } else if (key === 'excel') {
      const { data: blob, error } = await fetchBiChartsExcelExport({ chartIds: [chart.value.id] });
      if (error || !blob) return;
      triggerBlobDownload(blob, `${chart.value.name}.xlsx`);
    } else if (key === 'pdf') {
      const inst = chartInstance.value;
      if (!inst) {
        window.$message?.warning($t('page.bi.export.noChart'));
        return;
      }
      const url = inst.getDataURL({ pixelRatio: 2, backgroundColor: '#fff' });
      await exportChartPdf(chart.value.name || 'chart', url);
    }
    window.$message?.success($t('page.bi.export.exportSuccess'));
  } catch {
    window.$message?.error($t('page.bi.export.exportFailed'));
  }
}

async function handleDelete() {
  if (!chart.value) return;
  const { error } = await fetchDeleteBiChart({ id: chart.value.id });
  if (!error) {
    window.$message?.success($t('common.deleteSuccess'));
    router.push({ name: 'bi_charts' });
  }
}

onMounted(() => {
  loadDatasources();
  loadDetail();
});
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <NCard :bordered="false" size="small" class="card-wrapper">
      <NSpin :show="loading">
        <template v-if="chart">
          <!-- 顶部信息 + 操作 -->
          <div class="flex flex-wrap items-center justify-between gap-12px">
            <div class="flex flex-col gap-4px">
              <div class="flex items-center gap-8px">
                <h2 class="m-0 text-20px font-600">{{ chart.name }}</h2>
                <NTag v-if="chart.isPublic" size="small" type="success">
                  {{ $t('page.bi.chart.publicLabel') }}
                </NTag>
                <NTag v-else size="small" type="default">
                  {{ $t('page.bi.chart.privateLabel') }}
                </NTag>
              </div>
              <div class="flex flex-wrap items-center gap-8px text-12px text-gray-500">
                <NTag size="small" type="primary">{{ chartTypeLabel(chart.chartType) }}</NTag>
                <span>{{ $t('page.bi.chart.datasource') }}: {{ datasourceName(chart.datasourceId) }}</span>
                <span>·</span>
                <span>{{ $t('page.bi.chart.snapshotAt') }}: {{ formatSnapshotAt(chart.snapshotAt) }}</span>
                <span>·</span>
                <span>{{ chart.resultSnapshot?.rowCount ?? 0 }} {{ $t('page.bi.chart.rowCount') }}</span>
                <span v-if="chart.resultSnapshot?.isTruncated" class="text-orange-500">
                  · {{ $t('page.bi.chart.truncated') }}
                </span>
              </div>
              <div v-if="chart.description" class="text-13px opacity-70">{{ chart.description }}</div>
              <div v-if="parseTags(chart.tags).length" class="flex flex-wrap gap-4px">
                <NTag v-for="tag in parseTags(chart.tags)" :key="tag" size="small" type="info" round>
                  {{ tag }}
                </NTag>
              </div>
            </div>
            <NSpace :size="8" wrap>
              <NButton size="small" @click="router.push({ name: 'bi_charts' })">
                <template #icon><icon-ic-round-arrow-back class="text-icon" /></template>
                {{ $t('page.bi.chart.backToList') }}
              </NButton>
              <NButton
                v-if="hasAuth('B_BI_CHART_REFRESH')"
                size="small"
                type="primary"
                ghost
                :loading="refreshing"
                @click="handleRefresh"
              >
                <template #icon><icon-ic-round-refresh class="text-icon" /></template>
                {{ $t('page.bi.chart.refresh') }}
              </NButton>
              <NButton size="small" @click="exportPng">
                <template #icon><icon-ic-round-download class="text-icon" /></template>
                {{ $t('page.bi.chart.exportPng') }}
              </NButton>
              <NDropdown
                v-if="hasAuth('B_BI_CHART_EXPORT')"
                :options="exportOptions"
                :disabled="!chart?.resultSnapshot?.rows?.length"
                @select="handleExportSelect"
              >
                <NButton size="small" type="primary" ghost>
                  <template #icon><icon-ic-round-download class="text-icon" /></template>
                  {{ $t('page.bi.export.export') }}
                </NButton>
              </NDropdown>
              <NButton
                v-if="hasAuth('B_BI_CHART_SHARE')"
                size="small"
                :type="chart.isPublic ? 'warning' : 'success'"
                ghost
                @click="handleToggleShare"
              >
                <template #icon>
                  <icon-ic-round-share v-if="!chart.isPublic" class="text-icon" />
                  <icon-ic-round-lock v-else class="text-icon" />
                </template>
                {{ chart.isPublic ? $t('page.bi.chart.disableShare') : $t('page.bi.chart.enableShare') }}
              </NButton>
              <NPopconfirm v-if="hasAuth('B_BI_CHART_DELETE')" @positive-click="handleDelete">
                <template #trigger>
                  <NButton size="small" type="error" ghost>
                    <template #icon><icon-ic-round-delete class="text-icon" /></template>
                    {{ $t('common.delete') }}
                  </NButton>
                </template>
                {{ $t('page.bi.chart.deleteConfirm') }}
              </NPopconfirm>
            </NSpace>
          </div>

          <!-- 分享链接 -->
          <div v-if="shareLink" class="mt-12px flex items-center gap-8px">
            <NCode :code="shareLink" word-wrap class="flex-1" />
            <NButton size="small" type="primary" @click="copyShareLink">
              <template #icon><icon-ic-round-content-copy class="text-icon" /></template>
              {{ $t('page.bi.chart.copyLink') }}
            </NButton>
          </div>

          <!-- 图表 -->
          <div class="mt-16px">
            <div ref="chartRef" class="h-400px w-full" />
          </div>

          <!-- SQL（可折叠） -->
          <NCollapse class="mt-16px">
            <NCollapseItem :title="$t('page.bi.chart.sqlText')" name="sql">
              <NCode :code="chart.sqlText" language="sql" word-wrap />
            </NCollapseItem>
          </NCollapse>
        </template>
        <NEmpty v-else-if="!loading" :description="$t('common.noData')" class="py-80px" />
      </NSpin>
    </NCard>
  </div>
</template>
