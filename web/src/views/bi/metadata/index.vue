<script setup lang="tsx">
import { computed, ref, watch } from 'vue';
import { NButton, NCard, NEmpty, NPopconfirm, NSelect, NSpace, NTag } from 'naive-ui';
import {
  fetchBiDatasourceList,
  fetchBiTableList,
  fetchBootstrapBiDemo,
  fetchDeleteBiDatasource,
  fetchSyncBiDatasource,
  fetchTestBiDatasource
} from '@/service/api';
import { defaultTransform, useNaivePaginatedTable } from '@/hooks/common/table';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';
import DatasourceOperateModal from './modules/datasource-operate-modal.vue';
import ColumnDetailDrawer from './modules/column-detail-drawer.vue';

const { hasAuth } = useAuth();

const DS_PAGE_SIZE = 50;

// ===== 数据源 =====
const dsSearchParams = ref<Api.Bi.DatasourceSearchParams>({
  current: 1,
  size: DS_PAGE_SIZE,
  name: null,
  type: null
});

const {
  columns: dsColumns,
  data: dsData,
  loading: dsLoading,
  getData: getDsData
} = useNaivePaginatedTable({
  api: () => fetchBiDatasourceList(dsSearchParams.value),
  transform: response => defaultTransform(response),
  showTotal: false,
  initialPageSize: DS_PAGE_SIZE,
  onPaginationParamsChange: params => {
    dsSearchParams.value.current = params.page ?? 1;
    dsSearchParams.value.size = params.pageSize ?? DS_PAGE_SIZE;
  },
  columns: () => [
    {
      key: 'index',
      title: '#',
      width: 56,
      render: (_, index) => index + 1
    },
    {
      key: 'name',
      title: $t('page.bi.metadata.datasource.name'),
      minWidth: 160,
      render: row => (
        <NSpace align="center" size={4}>
          <span>{row.name}</span>
          {row.isDefault && <NTag type="primary" size="small">Default</NTag>}
        </NSpace>
      )
    },
    {
      key: 'type',
      title: $t('page.bi.metadata.datasource.type'),
      width: 110,
      render: row => $t(`page.bi.metadata.datasource.typeLabel.${row.type}`)
    },
    {
      key: 'database',
      title: $t('page.bi.metadata.datasource.database'),
      minWidth: 160,
      render: row => row.database || '-'
    },
    {
      key: 'lastSyncedAt',
      title: $t('page.bi.metadata.datasource.lastSyncedAt'),
      width: 170,
      render: row => row.lastSyncedAt ?? $t('page.bi.metadata.datasource.notSynced')
    },
    {
      key: 'op',
      title: $t('common.action'),
      width: 320,
      fixed: 'right',
      render: row => (
        <NSpace size={8}>
          {hasAuth('B_BI_DS_TEST') && (
            <NButton size="tiny" onClick={() => handleTest(row)}>
              {$t('page.bi.metadata.datasource.test')}
            </NButton>
          )}
          {hasAuth('B_BI_DS_SYNC') && (
            <NButton size="tiny" type="primary" ghost onClick={() => handleSync(row)}>
              {$t('page.bi.metadata.datasource.sync')}
            </NButton>
          )}
          {hasAuth('B_BI_DS_CREATE') && (
            <NButton size="tiny" onClick={() => handleEditDs(row)}>
              {$t('common.modify')}
            </NButton>
          )}
          {hasAuth('B_BI_DS_DELETE') && (
            <NPopconfirm onPositiveClick={() => handleDeleteDs(row)}>
              {{
                trigger: () => (
                  <NButton size="tiny" type="error" ghost>
                    {$t('common.delete')}
                  </NButton>
                ),
                default: () => $t('common.confirmDelete')
              }}
            </NPopconfirm>
          )}
        </NSpace>
      )
    }
  ]
});

// ===== 表清单 =====
const filterDsId = ref<string | null>(null);

const tableSearchParams = ref<Api.Bi.BiTableSearchParams>({
  current: 1,
  size: 50,
  datasourceId: null,
  name: null
});

const {
  columns: tableColumns,
  data: tableData,
  loading: tableLoading,
  getData: getTableData
} = useNaivePaginatedTable({
  api: () => fetchBiTableList(tableSearchParams.value),
  transform: response => defaultTransform(response),
  showTotal: false,
  initialPageSize: 50,
  onPaginationParamsChange: params => {
    tableSearchParams.value.current = params.page ?? 1;
    tableSearchParams.value.size = params.pageSize ?? 50;
  },
  columns: () => [
    {
      key: 'name',
      title: $t('page.bi.metadata.table.name'),
      minWidth: 180,
      render: row => (
        <NButton text type="primary" onClick={() => openColumnDrawer(row)}>
          {row.name}
        </NButton>
      )
    },
    {
      key: 'schemaName',
      title: $t('page.bi.metadata.table.schemaName'),
      width: 120,
      render: row => row.schemaName ?? '-'
    },
    {
      key: 'columnCount',
      title: $t('page.bi.metadata.table.columnCount'),
      width: 90,
      render: row => row.columnCount
    },
    {
      key: 'version',
      title: $t('page.bi.metadata.table.version'),
      width: 90,
      render: row => `v${row.version}`
    },
    {
      key: 'lastSyncedAt',
      title: $t('page.bi.metadata.table.lastSyncedAt'),
      width: 170,
      render: row => row.lastSyncedAt ?? '-'
    },
    {
      key: 'op',
      title: $t('common.action'),
      width: 110,
      render: row => (
        <NButton size="tiny" type="primary" ghost onClick={() => openColumnDrawer(row)}>
          {$t('page.bi.metadata.table.viewColumns')}
        </NButton>
      )
    }
  ]
});

// ===== 数据源表单 =====
const operateModalRef = ref<InstanceType<typeof DatasourceOperateModal> | null>(null);
const editingDs = ref<Api.Bi.Datasource | null>(null);

function handleAddDs() {
  editingDs.value = null;
  operateModalRef.value?.open();
}

function handleEditDs(row: Api.Bi.Datasource) {
  editingDs.value = row;
  operateModalRef.value?.open(row);
}

async function handleDeleteDs(row: Api.Bi.Datasource) {
  const { error } = await fetchDeleteBiDatasource(row.id);
  if (!error) {
    window.$message?.success($t('common.deleteSuccess'));
    getDsData();
    getTableData();
  }
}

async function handleTest(row: Api.Bi.Datasource) {
  const { data, error } = await fetchTestBiDatasource(row.id);
  if (error) return;
  if (data?.ok) {
    window.$message?.success($t('page.bi.metadata.datasource.testOk'));
  } else {
    window.$message?.error(`${$t('page.bi.metadata.datasource.testFailed')}: ${data?.error ?? '-'}`);
  }
}

async function handleSync(row: Api.Bi.Datasource) {
  const { data, error } = await fetchSyncBiDatasource(row.id);
  if (error) return;
  window.$message?.success(
    $t('page.bi.metadata.datasource.syncSuccess', {
      tables: data?.tables ?? 0,
      columns: data?.columns ?? 0
    })
  );
  getDsData();
  getTableData();
}

async function handleBootstrapDemo() {
  const { error } = await fetchBootstrapBiDemo();
  if (error) return;
  window.$message?.success(`${$t('page.bi.metadata.datasource.demoBootstrap')} ✓`);
  getDsData();
  getTableData();
}

function onDsSubmitted() {
  getDsData();
  getTableData();
}

// ===== 列详情 =====
const drawerRef = ref<InstanceType<typeof ColumnDetailDrawer> | null>(null);
const activeTable = ref<Api.Bi.BiTable | null>(null);

function openColumnDrawer(row: Api.Bi.BiTable) {
  activeTable.value = row;
  drawerRef.value?.open(row.id);
}

const dsOptions = computed(() =>
  (dsData.value ?? []).map(d => ({
    label: `${d.name} (${d.type})`,
    value: d.id
  }))
);

watch(filterDsId, val => {
  tableSearchParams.value.datasourceId = val;
  tableSearchParams.value.current = 1;
  getTableData();
});
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-12px">
    <!-- 数据源 -->
    <NCard :bordered="false" size="small" class="card-wrapper" :title="$t('page.bi.metadata.datasource.title')">
      <template #header-extra>
        <NSpace>
          <NPopconfirm @positive-click="handleBootstrapDemo">
            <template #trigger>
              <NButton type="primary" ghost>
                {{ $t('page.bi.metadata.datasource.demoBootstrap') }}
              </NButton>
            </template>
            {{ $t('page.bi.metadata.datasource.demoConfirm') }}
          </NPopconfirm>
          <NButton v-if="hasAuth('B_BI_DS_CREATE')" type="primary" @click="handleAddDs">
            {{ $t('page.bi.metadata.datasource.add') }}
          </NButton>
        </NSpace>
      </template>

      <NEmpty v-if="!dsLoading && !(dsData && dsData.length)" :description="$t('page.bi.metadata.datasource.empty')" />

      <NDataTable
        v-else
        :columns="dsColumns"
        :data="dsData || []"
        :loading="dsLoading"
        :row-key="row => row.id"
        size="small"
        :scroll-x="900"
        :pagination="false"
      />
    </NCard>

    <!-- 表清单 -->
    <NCard :bordered="false" size="small" class="card-wrapper" :title="$t('page.bi.metadata.table.title')">
      <template #header-extra>
        <NSpace>
          <NSelect
            v-model:value="filterDsId"
            :options="dsOptions"
            :placeholder="$t('page.bi.metadata.table.filterDatasource')"
            clearable
            style="width: 240px"
          />
          <NButton @click="getTableData">{{ $t('page.bi.metadata.table.refresh') }}</NButton>
        </NSpace>
      </template>

      <NEmpty
        v-if="!tableLoading && !(tableData && tableData.length)"
        :description="$t('page.bi.metadata.table.empty')"
      />

      <NDataTable
        v-else
        :columns="tableColumns"
        :data="tableData || []"
        :loading="tableLoading"
        :row-key="row => row.id"
        size="small"
        :scroll-x="800"
        :pagination="false"
      />
    </NCard>

    <DatasourceOperateModal ref="operateModalRef" :editing="editingDs" @submitted="onDsSubmitted" />
    <ColumnDetailDrawer ref="drawerRef" :table="activeTable" />
  </div>
</template>
