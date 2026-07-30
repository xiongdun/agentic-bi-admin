<script setup lang="tsx">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import type { DataTableColumns } from 'naive-ui';
import { NButton, NPopconfirm, NSpace, NTag } from 'naive-ui';
import { statusTypeRecord } from '@/constants/business';
import {
  fetchBiDatasource,
  fetchBiTableDetail,
  fetchBiTableList,
  fetchDeleteBiDatasource,
  fetchSyncBiDatasource,
  fetchTestBiDatasource
} from '@/service/api/bi';
import { useAuth } from '@/hooks/business/auth';
import { useAppStore } from '@/store/modules/app';
import { $t } from '@/locales';
import DatasourceOperateModal from '../metadata/modules/datasource-operate-modal.vue';
import ColumnDetailDrawer from '../metadata/modules/column-detail-drawer.vue';

defineOptions({ name: 'BiMetadataDetail' });

const route = useRoute();
const router = useRouter();
const { hasAuth } = useAuth();
const appStore = useAppStore();

const datasourceId = computed(() => route.params.id as string);

const datasource = ref<Api.Bi.BiDatasource | null>(null);
const dsLoading = ref(false);

const tables = ref<Api.Bi.BiTable[]>([]);
const tablesLoading = ref(false);
const statTables = ref(0);
const statColumns = ref(0);
const statIndexes = ref(0);
const statsLoading = ref(false);
const statsCapped = ref(false);

type FlatColumn = Api.Bi.BiColumn & { tableName: string };
type FlatIndex = Api.Bi.BiIndex & { tableName: string };
const allColumns = ref<FlatColumn[]>([]);
const allIndexes = ref<FlatIndex[]>([]);

const tableSearchName = ref('');
const columnFilterTableName = ref('');
const columnFilterName = ref('');
const indexFilterTableName = ref('');

const testing = ref(false);
const syncing = ref(false);

const dbTypeTagType: Record<string, 'success' | 'info' | 'warning' | 'error' | 'default'> = {
  postgresql: 'success',
  mysql: 'info',
  clickhouse: 'warning',
  trino: 'error',
  sqlite: 'default'
};

const filteredTables = computed(() => {
  const kw = tableSearchName.value.trim().toLowerCase();
  if (!kw) return tables.value;
  return tables.value.filter(
    t => t.name.toLowerCase().includes(kw) || (t.comment?.toLowerCase().includes(kw) ?? false)
  );
});

const filteredColumns = computed(() => {
  const tn = columnFilterTableName.value.trim().toLowerCase();
  const cn = columnFilterName.value.trim().toLowerCase();
  return allColumns.value.filter(c => {
    if (tn && !c.tableName.toLowerCase().includes(tn)) return false;
    if (cn && !c.name.toLowerCase().includes(cn)) return false;
    return true;
  });
});

const filteredIndexes = computed(() => {
  const tn = indexFilterTableName.value.trim().toLowerCase();
  if (!tn) return allIndexes.value;
  return allIndexes.value.filter(i => i.tableName.toLowerCase().includes(tn));
});

const flatColumnColumns = computed<DataTableColumns<FlatColumn>>(() => [
  { key: 'tableName', title: $t('page.bi.metadata.tableName'), minWidth: 160 },
  { key: 'name', title: $t('page.bi.metadata.columnName'), minWidth: 140 },
  { key: 'dataType', title: $t('page.bi.metadata.dataType'), minWidth: 120 },
  {
    key: 'isPrimary',
    title: $t('page.bi.metadata.isPrimary'),
    align: 'center',
    width: 70,
    render: (row: FlatColumn) => (row.isPrimary ? <NTag type="success" size="small">PK</NTag> : null)
  },
  {
    key: 'isNullable',
    title: $t('page.bi.metadata.isNullable'),
    align: 'center',
    width: 70,
    render: (row: FlatColumn) => (row.isNullable ? $t('common.yesOrNo.yes') : $t('common.yesOrNo.no'))
  },
  {
    key: 'comment',
    title: $t('page.bi.metadata.columnComment'),
    minWidth: 140,
    render: (row: FlatColumn) => row.comment || '-'
  }
]);

const flatIndexColumns = computed<DataTableColumns<FlatIndex>>(() => [
  { key: 'tableName', title: $t('page.bi.metadata.tableName'), minWidth: 160 },
  { key: 'name', title: $t('page.bi.metadata.indexName'), minWidth: 160 },
  { key: 'indexType', title: $t('page.bi.metadata.indexType'), minWidth: 100 },
  {
    key: 'columns',
    title: $t('page.bi.metadata.indexColumns'),
    minWidth: 160,
    render: (row: FlatIndex) => (row.columns || []).join(', ')
  },
  {
    key: 'isUnique',
    title: $t('page.bi.metadata.isUnique'),
    align: 'center',
    width: 70,
    render: (row: FlatIndex) => (row.isUnique ? $t('common.yesOrNo.yes') : $t('common.yesOrNo.no'))
  }
]);

const DETAIL_CAP = 100;

async function loadDatasource() {
  if (!datasourceId.value) return;
  dsLoading.value = true;
  const { data } = await fetchBiDatasource(datasourceId.value);
  dsLoading.value = false;
  if (data) {
    datasource.value = data;
  } else {
    router.replace({ name: 'bi_metadata' });
  }
}

async function loadTables() {
  if (!datasourceId.value) return;
  tablesLoading.value = true;
  const { data } = await fetchBiTableList({ current: 1, size: 999, datasourceId: datasourceId.value, name: null });
  tablesLoading.value = false;
  if (data?.records) {
    tables.value = data.records;
    statTables.value = data.total;
  } else {
    tables.value = [];
    statTables.value = 0;
  }
}

async function loadStatsAndColumns() {
  if (!tables.value.length) {
    statColumns.value = 0;
    statIndexes.value = 0;
    allColumns.value = [];
    allIndexes.value = [];
    return;
  }
  statsLoading.value = true;
  statsCapped.value = tables.value.length > DETAIL_CAP;
  const target = statsCapped.value ? tables.value.slice(0, DETAIL_CAP) : tables.value;
  const results = await Promise.all(target.map(t => fetchBiTableDetail(t.id)));
  let cols = 0;
  let idx = 0;
  const flatCols: FlatColumn[] = [];
  const flatIdx: FlatIndex[] = [];
  results.forEach(({ data }) => {
    if (!data) return;
    cols += data.columns?.length || 0;
    idx += data.indexes?.length || 0;
    (data.columns || []).forEach(c => flatCols.push({ ...c, tableName: data.name }));
    (data.indexes || []).forEach(ix => flatIdx.push({ ...ix, tableName: data.name }));
  });
  statColumns.value = cols;
  statIndexes.value = idx;
  allColumns.value = flatCols;
  allIndexes.value = flatIdx;
  statsLoading.value = false;
}

async function loadAll() {
  await loadDatasource();
  if (datasource.value) {
    await loadTables();
    await loadStatsAndColumns();
  }
}

function handleBack() {
  router.push({ name: 'bi_metadata' });
}

// ---- Datasource operations ----
const dsModalVisible = ref(false);
const dsOperateType = ref<NaiveUI.TableOperateType>('edit');
const dsEditingData = ref<Api.Bi.BiDatasource | null>(null);

function handleEditDs() {
  dsOperateType.value = 'edit';
  dsEditingData.value = datasource.value;
  dsModalVisible.value = true;
}

async function onDsSubmitted() {
  await loadDatasource();
}

async function handleTestDs() {
  if (!datasource.value) return;
  testing.value = true;
  const { data, error } = await fetchTestBiDatasource(datasource.value.id);
  testing.value = false;
  if (error) return;
  if (data?.success) {
    window.$message?.success(`${$t('page.bi.metadata.testSuccess')} (${data.elapsedMs}ms)`);
  } else {
    window.$message?.error(`${$t('page.bi.metadata.testFailed')}: ${data?.message || ''}`);
  }
}

async function handleSyncDs() {
  if (!datasource.value) return;
  syncing.value = true;
  const { data, error } = await fetchSyncBiDatasource(datasource.value.id);
  syncing.value = false;
  if (error) return;
  if (data) {
    window.$message?.success(
      `${$t('page.bi.metadata.syncSuccess')}: ${data.tablesSynced} ${$t('page.bi.metadata.tableCount').toLowerCase()} / ${data.columnsSynced} ${$t('page.bi.metadata.columnCount').toLowerCase()} / ${data.indexesSynced} ${$t('page.bi.metadata.indexCount').toLowerCase()}`
    );
    await loadAll();
  }
}

async function handleDeleteDs() {
  if (!datasource.value) return;
  const { error } = await fetchDeleteBiDatasource({ id: datasource.value.id });
  if (error) return;
  window.$message?.success($t('common.deleteSuccess'));
  router.replace({ name: 'bi_metadata' });
}

// ---- Table detail drawer ----
const detailVisible = ref(false);
const detailTableId = ref<string | null>(null);

function openTableDetail(table: Api.Bi.BiTable) {
  detailTableId.value = table.id;
  detailVisible.value = true;
}

watch(datasourceId, () => {
  if (datasourceId.value) loadAll();
});

onMounted(loadAll);
</script>

<template>
  <div class="h-full flex flex-col gap-16px overflow-hidden">
    <!-- Header: Back + Title + Actions (fixed) -->
    <NCard :bordered="false" size="small" class="card-wrapper shrink-0">
      <div class="flex items-center justify-between gap-12px">
        <NSpace :size="8" align="center">
          <NButton size="small" quaternary @click="handleBack">
            <template #icon><icon-ic-round-arrow-back class="text-icon" /></template>
            {{ $t('page.bi.metadata.backToList') }}
          </NButton>
          <NDivider vertical />
          <NText class="text-16px font-600">{{ $t('page.bi.metadata.datasourceDetail') }}</NText>
        </NSpace>
        <NSpace :size="8" align="center">
          <NButton v-if="hasAuth('B_BI_DS_EDIT')" size="small" ghost type="primary" @click="handleEditDs">
            <template #icon><icon-ic-round-edit class="text-icon" /></template>
            {{ $t('common.edit') }}
          </NButton>
          <NButton
            v-if="hasAuth('B_BI_DS_TEST')"
            size="small"
            ghost
            type="info"
            :loading="testing"
            @click="handleTestDs"
          >
            {{ $t('page.bi.metadata.testConnection') }}
          </NButton>
          <NPopconfirm v-if="hasAuth('B_BI_DS_SYNC')" @positive-click="handleSyncDs">
            <template #trigger>
              <NButton size="small" ghost type="warning" :loading="syncing" :disabled="syncing">
                {{ $t('page.bi.metadata.syncMetadata') }}
              </NButton>
            </template>
            {{ $t('page.bi.metadata.syncMetadataConfirm') }}
          </NPopconfirm>
          <NPopconfirm v-if="hasAuth('B_BI_DS_DELETE')" @positive-click="handleDeleteDs">
            <template #trigger>
              <NButton size="small" ghost type="error">
                {{ $t('common.delete') }}
              </NButton>
            </template>
            {{ $t('common.confirmDelete') }}
          </NPopconfirm>
        </NSpace>
      </div>
    </NCard>

    <!-- Scrollable content area -->
    <div class="flex flex-col gap-16px flex-1 min-h-0 overflow-auto">
      <!-- Basic Info -->
      <NCard :bordered="false" size="small" class="card-wrapper" :title="$t('page.bi.metadata.basicInfo')">
        <NSpin :show="dsLoading">
          <NDescriptions
            v-if="datasource"
            :column="appStore.isMobile ? 1 : 3"
            label-placement="left"
            bordered
            size="small"
          >
            <NDescriptionsItem :label="$t('page.bi.metadata.datasource')">
              <NSpace :size="6" align="center">
                <span class="font-500">{{ datasource.name }}</span>
                <NTag size="small" :type="dbTypeTagType[datasource.dbType] || 'default'">{{ datasource.dbType }}</NTag>
              </NSpace>
            </NDescriptionsItem>
            <NDescriptionsItem :label="$t('page.bi.metadata.host')">
              {{ datasource.host }}:{{ datasource.port }}
            </NDescriptionsItem>
            <NDescriptionsItem :label="$t('page.bi.metadata.database')">
              {{ datasource.database }}
            </NDescriptionsItem>
            <NDescriptionsItem :label="$t('page.bi.metadata.username')">
              {{ datasource.username }}
            </NDescriptionsItem>
            <NDescriptionsItem :label="$t('page.bi.audit.status')">
              <NTag size="small" :type="datasource.statusType === '1' ? 'success' : 'warning'">
                {{ datasource.statusType ? $t(statusTypeRecord[datasource.statusType]) : '-' }}
              </NTag>
            </NDescriptionsItem>
            <NDescriptionsItem :label="$t('page.bi.metadata.lastSyncedAt')">
              {{ datasource.fmtLastSyncedAt || '-' }}
            </NDescriptionsItem>
          </NDescriptions>
          <NEmpty v-else-if="!dsLoading" :description="$t('common.noData')" />
        </NSpin>
      </NCard>

      <!-- Stat Cards -->
      <NGrid :cols="4" :x-gap="16" :y-gap="16" responsive="screen">
        <NGi>
          <NCard :bordered="false" size="small" class="card-wrapper">
            <NStatistic :label="$t('page.bi.metadata.tableCount')" :value="statTables" />
          </NCard>
        </NGi>
        <NGi>
          <NCard :bordered="false" size="small" class="card-wrapper">
            <NSpin :show="statsLoading">
              <NStatistic
                :label="$t('page.bi.metadata.columnCount')"
                :value="statsCapped ? `>${statColumns}` : statColumns"
              />
            </NSpin>
          </NCard>
        </NGi>
        <NGi>
          <NCard :bordered="false" size="small" class="card-wrapper">
            <NSpin :show="statsLoading">
              <NStatistic
                :label="$t('page.bi.metadata.indexCount')"
                :value="statsCapped ? `>${statIndexes}` : statIndexes"
              />
            </NSpin>
          </NCard>
        </NGi>
        <NGi>
          <NCard :bordered="false" size="small" class="card-wrapper">
            <NStatistic :label="$t('page.bi.metadata.lastSyncedAt')" :value="datasource?.fmtLastSyncedAt || '-'" />
          </NCard>
        </NGi>
      </NGrid>

      <!-- Tables / Columns / Indexes Tabs -->
      <NCard :bordered="false" size="small" class="card-wrapper">
        <NTabs type="line" animated>
          <!-- Tab 1: Tables Grid -->
          <NTabPane name="tables" :tab="$t('page.bi.metadata.tableList')">
            <div class="flex items-center gap-12px mb-12px">
              <NInput
                v-model:value="tableSearchName"
                clearable
                size="small"
                class="max-w-320px"
                :placeholder="$t('page.bi.metadata.tableName')"
              >
                <template #prefix><icon-ic-round-search class="text-icon" /></template>
              </NInput>
              <span class="text-12px text-gray-400">{{ filteredTables.length }} / {{ tables.length }}</span>
            </div>
            <NSpin :show="tablesLoading">
              <NEmpty v-if="!filteredTables.length && !tablesLoading" :description="$t('common.noData')" />
              <NGrid v-else :cols="4" :x-gap="12" :y-gap="12" responsive="screen">
                <NGi v-for="t in filteredTables" :key="t.id">
                  <NCard size="small" hoverable class="cursor-pointer" @click="openTableDetail(t)">
                    <div class="flex items-center justify-between gap-8px">
                      <span class="font-500 truncate">{{ t.name }}</span>
                      <NTag v-if="t.statusType" size="small" :type="t.statusType === '1' ? 'success' : 'warning'">
                        {{ $t(statusTypeRecord[t.statusType]) }}
                      </NTag>
                    </div>
                    <div class="text-12px text-gray-400 mt-4px truncate">
                      {{ t.comment || '-' }}
                    </div>
                    <div class="flex items-center gap-12px mt-8px text-12px">
                      <span>
                        <icon-ic-round-table-chart class="text-icon" />
                        {{ t.rowCount }}
                      </span>
                    </div>
                  </NCard>
                </NGi>
              </NGrid>
            </NSpin>
          </NTabPane>

          <!-- Tab 2: Columns Flat List -->
          <NTabPane name="columns" :tab="$t('page.bi.metadata.columnList')">
            <div class="flex items-center gap-12px mb-12px">
              <NInput
                v-model:value="columnFilterTableName"
                clearable
                size="small"
                class="max-w-240px"
                :placeholder="$t('page.bi.metadata.tableName')"
              >
                <template #prefix><icon-ic-round-search class="text-icon" /></template>
              </NInput>
              <NInput
                v-model:value="columnFilterName"
                clearable
                size="small"
                class="max-w-240px"
                :placeholder="$t('page.bi.metadata.columnName')"
              >
                <template #prefix><icon-ic-round-search class="text-icon" /></template>
              </NInput>
              <span class="text-12px text-gray-400">{{ filteredColumns.length }}</span>
              <span v-if="statsCapped" class="text-12px text-warning">({{ DETAIL_CAP }}+)</span>
            </div>
            <NDataTable
              :columns="flatColumnColumns"
              :data="filteredColumns"
              size="small"
              :scroll-x="900"
              :loading="statsLoading"
              :pagination="{ pageSize: 15 }"
              :row-key="(row: FlatColumn) => row.id"
            />
          </NTabPane>

          <!-- Tab 3: Indexes Flat List -->
          <NTabPane name="indexes" :tab="$t('page.bi.metadata.indexList')">
            <div class="flex items-center gap-12px mb-12px">
              <NInput
                v-model:value="indexFilterTableName"
                clearable
                size="small"
                class="max-w-240px"
                :placeholder="$t('page.bi.metadata.tableName')"
              >
                <template #prefix><icon-ic-round-search class="text-icon" /></template>
              </NInput>
              <span class="text-12px text-gray-400">{{ filteredIndexes.length }}</span>
              <span v-if="statsCapped" class="text-12px text-warning">({{ DETAIL_CAP }}+)</span>
            </div>
            <NDataTable
              :columns="flatIndexColumns"
              :data="filteredIndexes"
              size="small"
              :scroll-x="800"
              :loading="statsLoading"
              :pagination="{ pageSize: 15 }"
              :row-key="(row: FlatIndex) => row.id"
            />
          </NTabPane>
        </NTabs>
      </NCard>
    </div>

    <DatasourceOperateModal
      v-model:visible="dsModalVisible"
      :operate-type="dsOperateType"
      :row-data="dsEditingData"
      @submitted="onDsSubmitted"
    />
    <ColumnDetailDrawer v-model:visible="detailVisible" :table-id="detailTableId" />
  </div>
</template>
