<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue';
import type { DataTableColumns, DropdownOption, SelectOption } from 'naive-ui';
import * as monaco from 'monaco-editor';
import { useEcharts } from '@/hooks/common/echarts';
import type { ECOption } from '@/hooks/common/echarts';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';
import {
  fetchBiSqlExplain,
  fetchBiSqlFormat,
  fetchBiSqlGenerateSelect,
  fetchBiSqlPreview,
  fetchBiSqlRun
} from '@/service/api/bi-sql';
import { fetchBiDatasourceList, fetchBiTableDetail, fetchBiTableList } from '@/service/api/bi';

defineOptions({ name: 'BiSqlWorkbench' });

const { hasAuth } = useAuth();
const canRun = computed(() => hasAuth('B_BI_SQL_RUN'));

const editorContainer = ref<HTMLElement>();
const editor = shallowRef<monaco.editor.IStandaloneCodeEditor | null>(null);
const sqlContent = ref<string>('SELECT * FROM users LIMIT 10;');
const datasourceId = ref<string>('');
const datasources = ref<Api.Bi.BiDatasource[]>([]);
const tables = ref<Api.Bi.BiTable[]>([]);
const tableSearch = ref<string>('');
const result = ref<Api.Bi.SqlExecutionResult | null>(null);
const loading = ref<boolean>(false);

const explainVisible = ref<boolean>(false);
const explainResult = ref<Api.Bi.SqlExplainResult | null>(null);

const sidebarCollapsed = ref<boolean>(false);

const currentPage = ref<number>(1);
const pageSize = ref<number>(50);
const pageSizes = [20, 50, 100, 200];

type ChartType = 'bar' | 'line' | 'pie' | 'scatter';
const activeTab = ref<'table' | 'chart'>('table');
const chartType = ref<ChartType>('bar');
const chartXAxis = ref<string>('');
const chartYAxis = ref<string>('');

const structureVisible = ref<boolean>(false);
const structureLoading = ref<boolean>(false);
const structureDetail = ref<Api.Bi.BiTableDetail | null>(null);

const contextMenuShow = ref<boolean>(false);
const contextMenuX = ref<number>(0);
const contextMenuY = ref<number>(0);
const contextMenuTable = ref<Api.Bi.BiTable | null>(null);

const datasourceOptions = computed<SelectOption[]>(() =>
  datasources.value.map(d => ({
    label: `${d.name} (${d.dbType})`,
    value: d.id
  }))
);

const filteredTables = computed(() => {
  if (!tableSearch.value.trim()) return tables.value;
  const keyword = tableSearch.value.trim().toLowerCase();
  return tables.value.filter(t => {
    const nameMatch = t.name.toLowerCase().includes(keyword);
    const commentMatch = t.comment?.toLowerCase().includes(keyword) ?? false;
    return nameMatch || commentMatch;
  });
});

const resultColumns = computed<DataTableColumns<Record<string, any>>>(() => {
  if (!result.value?.columns?.length) return [];
  return result.value.columns.map(col => ({
    key: col,
    title: col,
    minWidth: 140,
    ellipsis: { tooltip: true }
  }));
});

const totalRows = computed(() => result.value?.rowCount ?? result.value?.rows?.length ?? 0);

const numericColumns = computed(() => {
  if (!result.value?.columns?.length || !result.value?.rows?.length) return [];
  return result.value.columns.filter(col =>
    result.value!.rows.every(row => {
      const val = row[col];
      return (
        val === null ||
        val === undefined ||
        typeof val === 'number' ||
        (typeof val === 'string' && val !== '' && !Number.isNaN(Number(val)))
      );
    })
  );
});

const columnOptions = computed<SelectOption[]>(() => {
  if (!result.value?.columns?.length) return [];
  return result.value.columns.map(col => ({ label: col, value: col }));
});

const chartTypeOptions: SelectOption[] = [
  { label: $t('page.bi.metrics.chartTypes.bar'), value: 'bar' },
  { label: $t('page.bi.metrics.chartTypes.line'), value: 'line' },
  { label: $t('page.bi.metrics.chartTypes.pie'), value: 'pie' },
  { label: $t('page.bi.metrics.chartTypes.scatter'), value: 'scatter' }
];

function buildChartOptions(): ECOption {
  if (!result.value?.rows?.length || !chartXAxis.value || !chartYAxis.value) {
    return {} as ECOption;
  }

  const rows = result.value.rows;
  const xCol = chartXAxis.value;
  const yCol = chartYAxis.value;

  if (chartType.value === 'pie') {
    return {
      tooltip: { trigger: 'item' },
      legend: { orient: 'vertical', left: 'left' },
      series: [
        {
          type: 'pie',
          radius: '60%',
          name: yCol,
          data: rows.map(row => ({ name: String(row[xCol] ?? ''), value: Number(row[yCol]) || 0 }))
        }
      ]
    } as ECOption;
  }

  if (chartType.value === 'scatter') {
    return {
      tooltip: { trigger: 'item' },
      xAxis: { type: 'value', name: xCol },
      yAxis: { type: 'value', name: yCol },
      series: [
        {
          type: 'scatter',
          name: yCol,
          data: rows.map(row => [Number(row[xCol]) || 0, Number(row[yCol]) || 0])
        }
      ]
    } as ECOption;
  }

  return {
    tooltip: { trigger: 'axis' },
    legend: { data: [yCol] },
    xAxis: { type: 'category', data: rows.map(row => String(row[xCol] ?? '')) },
    yAxis: { type: 'value' },
    series: [
      {
        type: chartType.value,
        name: yCol,
        data: rows.map(row => Number(row[yCol]) || 0)
      }
    ]
  } as ECOption;
}

const latestChartOptions = ref<ECOption>({} as ECOption);
const { domRef: chartRef, setOptions: setChartOptions } = useEcharts(() => ({}) as ECOption, {
  onRender: instance => {
    if (Object.keys(latestChartOptions.value).length) {
      instance.setOption({ ...latestChartOptions.value, backgroundColor: 'transparent' });
    }
  }
});

function refreshChart() {
  if (!result.value?.rows?.length || !chartXAxis.value || !chartYAxis.value) {
    latestChartOptions.value = {} as ECOption;
    return;
  }
  latestChartOptions.value = buildChartOptions();
  nextTick(() => setChartOptions(latestChartOptions.value));
}

function autoDetectChartColumns() {
  if (!result.value?.columns?.length) {
    chartXAxis.value = '';
    chartYAxis.value = '';
    return;
  }
  const cols = result.value.columns;
  const xCol = cols[0];
  const numericCols = numericColumns.value;
  const yCol = numericCols.find(c => c !== xCol) ?? numericCols[0] ?? cols[1] ?? xCol;
  chartXAxis.value = xCol;
  chartYAxis.value = yCol;
}

onMounted(async () => {
  if (editorContainer.value) {
    editor.value = monaco.editor.create(editorContainer.value, {
      value: sqlContent.value,
      language: 'sql',
      theme: 'vs',
      automaticLayout: true,
      minimap: { enabled: false },
      fontSize: 14,
      lineNumbers: 'on',
      scrollBeyondLastLine: false,
      tabSize: 2,
      wordWrap: 'on'
    });
    editor.value.onDidChangeModelContent(() => {
      sqlContent.value = editor.value?.getValue() ?? '';
    });
  }
  await loadDatasources();
});

onBeforeUnmount(() => {
  editor.value?.dispose();
  editor.value = null;
});

async function loadDatasources() {
  const { data } = await fetchBiDatasourceList({ current: 1, size: 100 });
  if (data?.records?.length) {
    datasources.value = data.records;
    if (!datasourceId.value) {
      datasourceId.value = datasources.value[0].id;
      await loadTables();
    }
  }
}

async function loadTables() {
  if (!datasourceId.value) {
    tables.value = [];
    return;
  }
  const { data } = await fetchBiTableList({ datasourceId: datasourceId.value, current: 1, size: 1000 });
  tables.value = data?.records ?? [];
}

async function handleDatasourceChange() {
  await loadTables();
}

async function handleExecute() {
  if (!sqlContent.value.trim() || !datasourceId.value) return;
  loading.value = true;
  try {
    const { data, error } = await fetchBiSqlRun({ sql: sqlContent.value, datasourceId: datasourceId.value });
    if (!error && data) {
      result.value = data;
      currentPage.value = 1;
      autoDetectChartColumns();
      refreshChart();
      window.$message?.success($t('page.bi.sql-workbench.result'));
    }
  } finally {
    loading.value = false;
  }
}

async function handleFormat() {
  if (!sqlContent.value.trim()) return;
  const { data } = await fetchBiSqlFormat({ sql: sqlContent.value });
  if (data?.sql) {
    sqlContent.value = data.sql;
    editor.value?.setValue(data.sql);
    window.$message?.success($t('common.updateSuccess'));
  }
}

async function handleExplain() {
  if (!sqlContent.value.trim()) return;
  const { data } = await fetchBiSqlExplain({ sql: sqlContent.value });
  if (data) {
    explainResult.value = data;
    explainVisible.value = true;
  }
}

function handleClear() {
  sqlContent.value = '';
  editor.value?.setValue('');
  result.value = null;
  chartXAxis.value = '';
  chartYAxis.value = '';
  latestChartOptions.value = {} as ECOption;
}

async function handlePreviewTable(table: Api.Bi.BiTable) {
  if (!datasourceId.value) return;
  loading.value = true;
  try {
    const { data, error } = await fetchBiSqlPreview(datasourceId.value, table.name);
    if (!error && data) {
      result.value = data;
      currentPage.value = 1;
      activeTab.value = 'table';
      autoDetectChartColumns();
      refreshChart();
    }
  } finally {
    loading.value = false;
  }
}

async function handleGenerateSelect(table: Api.Bi.BiTable) {
  if (!datasourceId.value) return;
  const { data } = await fetchBiSqlGenerateSelect(datasourceId.value, table.name);
  if (data?.sql) {
    sqlContent.value = data.sql;
    editor.value?.setValue(data.sql);
    window.$message?.success($t('common.updateSuccess'));
  }
}

async function handleViewStructure(table: Api.Bi.BiTable) {
  structureVisible.value = true;
  structureLoading.value = true;
  structureDetail.value = null;
  try {
    const { data } = await fetchBiTableDetail(table.id);
    structureDetail.value = data ?? null;
  } finally {
    structureLoading.value = false;
  }
}

const tableMenuOptions = computed<DropdownOption[]>(() => [
  { label: $t('page.bi.sql-workbench.viewStructure'), key: 'structure' },
  { label: $t('page.bi.sql-workbench.generateSelect'), key: 'select' },
  { label: $t('page.bi.sql-workbench.preview'), key: 'preview' }
]);

function handleTableContextMenu(e: MouseEvent, table: Api.Bi.BiTable) {
  e.preventDefault();
  contextMenuTable.value = table;
  contextMenuX.value = e.clientX;
  contextMenuY.value = e.clientY;
  contextMenuShow.value = true;
}

function handleContextMenuSelect(key: string) {
  contextMenuShow.value = false;
  const table = contextMenuTable.value;
  if (!table) return;
  if (key === 'structure') {
    handleViewStructure(table);
  } else if (key === 'select') {
    handleGenerateSelect(table);
  } else if (key === 'preview') {
    handlePreviewTable(table);
  }
}

const paginationProps = computed(() => ({
  page: currentPage.value,
  pageSize: pageSize.value,
  itemCount: totalRows.value,
  pageSizes,
  showSizePicker: true,
  prefix: (info: { itemCount: number | undefined }) => $t('datatable.itemCount', { total: info.itemCount ?? 0 }),
  onUpdatePage: (p: number) => {
    currentPage.value = p;
  },
  onUpdatePageSize: (ps: number) => {
    pageSize.value = ps;
  }
}));

const structureColumnColumns = computed<DataTableColumns<Api.Bi.BiColumn>>(() => [
  { key: 'name', title: $t('page.bi.metadata.columnName'), minWidth: 140 },
  { key: 'dataType', title: $t('page.bi.metadata.dataType'), minWidth: 120 },
  {
    key: 'isPrimary',
    title: $t('page.bi.metadata.isPrimary'),
    width: 80,
    align: 'center',
    render: row => (row.isPrimary ? '✓' : '')
  },
  {
    key: 'isNullable',
    title: $t('page.bi.metadata.isNullable'),
    width: 80,
    align: 'center',
    render: row => (row.isNullable ? '✓' : '')
  },
  { key: 'defaultValue', title: $t('page.bi.metadata.defaultValue'), minWidth: 100 },
  { key: 'comment', title: $t('page.bi.metadata.columnComment'), minWidth: 140 }
]);

const structureIndexColumns = computed<DataTableColumns<Api.Bi.BiIndex>>(() => [
  { key: 'name', title: $t('page.bi.metadata.indexName'), minWidth: 140 },
  { key: 'indexType', title: $t('page.bi.metadata.indexType'), minWidth: 100 },
  { key: 'columns', title: $t('page.bi.metadata.indexColumns'), minWidth: 160, render: row => row.columns.join(', ') },
  {
    key: 'isUnique',
    title: $t('page.bi.metadata.isUnique'),
    width: 80,
    align: 'center',
    render: row => (row.isUnique ? '✓' : '')
  }
]);

watch([chartType, chartXAxis, chartYAxis], () => {
  if (activeTab.value === 'chart') refreshChart();
});

watch(activeTab, tab => {
  if (tab === 'chart') nextTick(refreshChart);
});

watch(pageSize, () => {
  currentPage.value = 1;
});
</script>

<template>
  <div class="h-full flex-col-stretch overflow-hidden">
    <div class="flex h-full min-h-0 gap-12px">
      <!-- 左侧：表列表 -->
      <NCard :bordered="false" size="small" class="card-wrapper sidebar-card" :class="{ collapsed: sidebarCollapsed }">
        <template #header>
          <div class="flex items-center justify-between">
            <span v-if="!sidebarCollapsed" class="text-14px font-medium">
              {{ $t('page.bi.metadata.tableList') }}
            </span>
            <NButton text size="small" @click="sidebarCollapsed = !sidebarCollapsed">
              <icon-ic-round-chevron-left v-if="!sidebarCollapsed" class="text-icon" />
              <icon-ic-round-chevron-right v-else class="text-icon" />
            </NButton>
          </div>
        </template>
        <div v-show="!sidebarCollapsed" class="flex flex-1 flex-col min-h-0 gap-8px">
          <NSelect
            v-model:value="datasourceId"
            :options="datasourceOptions"
            :placeholder="$t('page.bi.sql-workbench.selectDatasource')"
            size="small"
            @update:value="handleDatasourceChange"
          />
          <NInput v-model:value="tableSearch" size="small" clearable :placeholder="$t('common.keywordSearch')">
            <template #prefix>
              <icon-ic-round-search class="text-icon" />
            </template>
          </NInput>
          <div class="flex-1 min-h-0 overflow-auto tables-list">
            <div
              v-for="table in filteredTables"
              :key="table.id"
              class="table-item"
              @contextmenu="handleTableContextMenu($event, table)"
              @dblclick="handlePreviewTable(table)"
            >
              <icon-ic-round-table-chart class="text-icon text-gray-500" />
              <div class="min-w-0 flex-1">
                <div class="truncate text-13px font-medium">{{ table.name }}</div>
                <div v-if="table.comment" class="truncate text-11px text-gray-400">{{ table.comment }}</div>
              </div>
            </div>
            <NEmpty v-if="!filteredTables.length" size="small" :description="$t('common.noData')" class="py-12px" />
          </div>
        </div>
      </NCard>

      <!-- 右侧：编辑器 + 结果区（整体滚动） -->
      <div class="flex flex-col flex-1 min-w-0 gap-12px overflow-auto">
        <NCard :bordered="false" size="small" class="card-wrapper editor-card">
          <template #header>
            <div class="flex items-center gap-8px">
              <NButton v-if="sidebarCollapsed" text size="small" @click="sidebarCollapsed = false">
                <icon-ic-round-chevron-right class="text-icon" />
              </NButton>
              <span class="text-14px font-medium">{{ $t('page.bi.sql-workbench.title') }}</span>
            </div>
          </template>
          <template #header-extra>
            <NSpace :size="8">
              <NSelect
                v-model:value="datasourceId"
                :options="datasourceOptions"
                :placeholder="$t('page.bi.sql-workbench.selectDatasource')"
                size="small"
                style="width: 200px"
                @update:value="handleDatasourceChange"
              />
              <NButton v-if="canRun" type="primary" size="small" :loading="loading" @click="handleExecute">
                <template #icon>
                  <icon-ic-round-play-arrow class="text-icon" />
                </template>
                {{ $t('page.bi.sql-workbench.execute') }}
              </NButton>
              <NButton size="small" @click="handleFormat">
                <template #icon>
                  <icon-ic-round-auto-fix-high class="text-icon" />
                </template>
                {{ $t('page.bi.sql-workbench.format') }}
              </NButton>
              <NButton size="small" @click="handleExplain">
                <template #icon>
                  <icon-ic-round-info class="text-icon" />
                </template>
                {{ $t('page.bi.sql-workbench.explain') }}
              </NButton>
              <NButton size="small" @click="handleClear">
                <template #icon>
                  <icon-ic-round-clear class="text-icon" />
                </template>
                {{ $t('page.bi.sql-workbench.clear') }}
              </NButton>
            </NSpace>
          </template>
          <div ref="editorContainer" class="editor-container" />
        </NCard>

        <NCard :bordered="false" size="small" class="card-wrapper result-card">
          <template #header>
            <div class="flex items-center gap-12px">
              <span class="text-14px font-medium">{{ $t('page.bi.sql-workbench.result') }}</span>
              <template v-if="result">
                <NTag size="small" type="info">
                  {{ $t('page.bi.sql-workbench.rowCount', { count: totalRows }) }}
                </NTag>
                <NTag size="small" type="success">
                  {{ $t('page.bi.sql-workbench.elapsed') }}: {{ result.elapsedMs }}ms
                </NTag>
              </template>
            </div>
          </template>
          <template #header-extra>
            <NSpace v-if="result" :size="8" align="center">
              <span class="text-12px text-gray-500">{{ $t('common.view') }}</span>
              <NSelect
                v-model:value="pageSize"
                :options="pageSizes.map(s => ({ label: `${s} / 页`, value: s }))"
                size="small"
                style="width: 110px"
              />
            </NSpace>
          </template>
          <div class="result-area">
            <NTabs v-model:value="activeTab" type="line" animated>
              <NTabPane name="table" :tab="$t('page.bi.metrics.chartTypes.table')">
                <NDataTable
                  :columns="resultColumns"
                  :data="result?.rows ?? []"
                  size="small"
                  :scroll-x="1200"
                  :pagination="paginationProps"
                  :row-key="(row: Record<string, any>) => JSON.stringify(row)"
                  class="sql-result-table"
                />
              </NTabPane>
              <NTabPane name="chart" :tab="$t('page.bi.metrics.chartType')" display-directive="show">
                <div class="flex flex-col gap-8px">
                  <NSpace :size="8" align="center">
                    <NSelect v-model:value="chartType" :options="chartTypeOptions" size="small" style="width: 120px" />
                    <span class="text-12px text-gray-500">X:</span>
                    <NSelect
                      v-model:value="chartXAxis"
                      :options="columnOptions"
                      size="small"
                      style="width: 160px"
                      filterable
                    />
                    <span class="text-12px text-gray-500">Y:</span>
                    <NSelect
                      v-model:value="chartYAxis"
                      :options="columnOptions"
                      size="small"
                      style="width: 160px"
                      filterable
                    />
                  </NSpace>
                  <div ref="chartRef" class="chart-container" />
                </div>
              </NTabPane>
            </NTabs>
          </div>
        </NCard>
      </div>
    </div>

    <!-- 右键菜单 -->
    <NDropdown
      placement="bottom-start"
      trigger="manual"
      :x="contextMenuX"
      :y="contextMenuY"
      :show="contextMenuShow"
      :options="tableMenuOptions"
      @select="handleContextMenuSelect"
      @clickoutside="contextMenuShow = false"
    />

    <!-- 表结构抽屉 -->
    <NDrawer v-model:show="structureVisible" :width="720">
      <NDrawerContent :title="$t('page.bi.sql-workbench.viewStructure')" closable>
        <NSpin :show="structureLoading">
          <template v-if="structureDetail">
            <NSpace vertical :size="16">
              <div>
                <NSpace :size="12" align="center">
                  <NTag type="primary" size="small">{{ structureDetail.name }}</NTag>
                  <span v-if="structureDetail.comment" class="text-12px text-gray-500">
                    {{ structureDetail.comment }}
                  </span>
                  <NTag v-if="structureDetail.rowCount >= 0" size="small">
                    {{ $t('page.bi.metadata.rowCount') }}: {{ structureDetail.rowCount }}
                  </NTag>
                </NSpace>
              </div>
              <div>
                <div class="mb-8px text-13px font-medium">{{ $t('page.bi.metadata.columnList') }}</div>
                <NDataTable
                  :columns="structureColumnColumns"
                  :data="structureDetail.columns"
                  size="small"
                  :scroll-x="700"
                  :row-key="(row: Api.Bi.BiColumn) => row.id"
                />
              </div>
              <div v-if="structureDetail.indexes?.length">
                <div class="mb-8px text-13px font-medium">{{ $t('page.bi.metadata.indexList') }}</div>
                <NDataTable
                  :columns="structureIndexColumns"
                  :data="structureDetail.indexes"
                  size="small"
                  :scroll-x="600"
                  :row-key="(row: Api.Bi.BiIndex) => row.id"
                />
              </div>
            </NSpace>
          </template>
          <NEmpty v-else :description="$t('common.noData')" />
        </NSpin>
      </NDrawerContent>
    </NDrawer>

    <!-- 解析结果抽屉 -->
    <NDrawer v-model:show="explainVisible" :width="600">
      <NDrawerContent :title="$t('page.bi.sql-workbench.explainResult')" closable>
        <template v-if="explainResult">
          <NSpace vertical :size="12">
            <NAlert v-if="explainResult.error" type="error" :show-icon="true">{{ explainResult.error }}</NAlert>
            <div v-for="(stmt, idx) in explainResult.statements" :key="idx" class="explain-item">
              <NSpace :size="8" align="center">
                <NTag size="small" :type="stmt.type === 'SELECT' ? 'success' : 'warning'">{{ stmt.type }}</NTag>
                <span class="text-12px text-gray-500">#{{ idx + 1 }}</span>
              </NSpace>
              <pre class="explain-sql">{{ stmt.sql }}</pre>
            </div>
          </NSpace>
        </template>
        <NEmpty v-else :description="$t('common.noData')" />
      </NDrawerContent>
    </NDrawer>
  </div>
</template>

<style scoped>
.sidebar-card {
  width: 240px;
  transition: width 0.2s ease;
  flex-shrink: 0;
}

.sidebar-card.collapsed {
  width: 48px;
}

.sidebar-card :deep(.n-card-content) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.tables-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.table-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.table-item:hover {
  background-color: rgba(99, 102, 241, 0.08);
}

.editor-card :deep(.n-card-content) {
  padding: 0;
  overflow: hidden;
}

.editor-container {
  height: 260px;
  min-height: 200px;
}

.result-card :deep(.n-card-content) {
  display: flex;
  flex-direction: column;
}

.result-area {
  display: flex;
  flex-direction: column;
}

.chart-container {
  height: 400px;
  width: 100%;
}

.explain-item {
  padding: 12px;
  border: 1px solid var(--n-border-color, rgba(0, 0, 0, 0.08));
  border-radius: 6px;
  background: rgba(248, 250, 252, 0.6);
}

.explain-sql {
  margin: 8px 0 0 0;
  padding: 8px;
  color: rgb(30, 41, 59);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  background: rgba(15, 23, 42, 0.04);
  border-radius: 4px;
}
</style>
