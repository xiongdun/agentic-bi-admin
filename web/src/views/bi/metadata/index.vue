<script setup lang="tsx">
import { computed, onMounted, ref, type VNode } from 'vue';
import { useRouter } from 'vue-router';
import { NButton, NPopconfirm, NSpace, NTag, NText } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { statusTypeRecord } from '@/constants/business';
import {
  fetchBiDatasourceList,
  fetchDeleteBiDatasource,
  fetchSyncBiDatasource,
  fetchTestBiDatasource
} from '@/service/api/bi';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';
import DatasourceOperateModal from './modules/datasource-operate-modal.vue';

defineOptions({ name: 'BiMetadata' });

const router = useRouter();
const { hasAuth } = useAuth();

const datasources = ref<Api.Bi.BiDatasource[]>([]);

const testingId = ref<string | null>(null);
const syncingId = ref<string | null>(null);

const dbTypeTagType: Record<string, 'success' | 'info' | 'warning' | 'error' | 'default'> = {
  postgresql: 'success',
  mysql: 'info',
  clickhouse: 'warning',
  trino: 'error',
  sqlite: 'default'
};

const dsColumns = computed<DataTableColumns<Api.Bi.BiDatasource>>(() => [
  {
    key: 'name',
    title: $t('page.bi.metadata.datasource'),
    minWidth: 160,
    render: row => <span class="font-500">{row.name}</span>
  },
  {
    key: 'dbType',
    title: $t('page.bi.metadata.dbType'),
    width: 130,
    render: row => <NTag size="small" type={dbTypeTagType[row.dbType] || 'default'}>{row.dbType}</NTag>
  },
  {
    key: 'host',
    title: $t('page.bi.metadata.host'),
    minWidth: 180,
    render: row => (
      <NText>
        {row.host}
        <NText depth={3} class="ml-4px">
          :{row.port}
        </NText>
      </NText>
    )
  },
  { key: 'database', title: $t('page.bi.metadata.database'), minWidth: 140 },
  { key: 'username', title: $t('page.bi.metadata.username'), minWidth: 120 },
  {
    key: 'statusType',
    title: $t('page.bi.audit.status'),
    width: 90,
    align: 'center',
    render: row => (
      <NTag size="small" type={row.statusType === '1' ? 'success' : 'warning'}>
        {row.statusType ? $t(statusTypeRecord[row.statusType]) : '-'}
      </NTag>
    )
  },
  {
    key: 'fmtLastSyncedAt',
    title: $t('page.bi.metadata.lastSyncedAt'),
    minWidth: 160,
    render: row => row.fmtLastSyncedAt || '-'
  },
  {
    key: 'actions',
    title: $t('common.action'),
    width: 280,
    fixed: 'right',
    render: row => {
      const buttons: VNode[] = [
        <NButton size="tiny" type="primary" onClick={() => handleViewDetail(row)}>
          {$t('common.view')}
        </NButton>
      ];
      if (hasAuth('B_BI_DS_EDIT')) {
        buttons.push(
          <NButton size="tiny" ghost type="primary" onClick={() => handleEditDs(row)}>
            {$t('common.edit')}
          </NButton>
        );
      }
      if (hasAuth('B_BI_DS_TEST')) {
        buttons.push(
          <NButton
            size="tiny"
            ghost
            type="info"
            loading={testingId.value === row.id}
            onClick={() => handleTestDs(row)}
          >
            {$t('page.bi.metadata.testConnection')}
          </NButton>
        );
      }
      if (hasAuth('B_BI_DS_SYNC')) {
        buttons.push(
          <NPopconfirm onPositiveClick={() => handleSyncDs(row)}>
            {{
              trigger: () => (
                <NButton
                  size="tiny"
                  ghost
                  type="warning"
                  loading={syncingId.value === row.id}
                  disabled={syncingId.value === row.id}
                >
                  {$t('page.bi.metadata.syncMetadata')}
                </NButton>
              ),
              default: () => $t('page.bi.metadata.syncMetadataConfirm')
            }}
          </NPopconfirm>
        );
      }
      if (hasAuth('B_BI_DS_DELETE')) {
        buttons.push(
          <NPopconfirm onPositiveClick={() => handleDeleteDs(row)}>
            {{
              trigger: () => (
                <NButton size="tiny" ghost type="error">
                  {$t('common.delete')}
                </NButton>
              ),
              default: () => $t('common.confirmDelete')
            }}
          </NPopconfirm>
        );
      }
      return <NSpace size={4} wrap={false}>{buttons}</NSpace>;
    }
  }
]);

async function loadDatasources() {
  const { data } = await fetchBiDatasourceList({ current: 1, size: 999 });
  if (data?.records) {
    datasources.value = data.records;
  } else {
    datasources.value = [];
  }
}

function handleViewDetail(row: Api.Bi.BiDatasource) {
  router.push({ name: 'bi_metadata-detail', params: { id: row.id } });
}

// ---- Datasource CRUD ----
const dsModalVisible = ref(false);
const dsOperateType = ref<NaiveUI.TableOperateType>('add');
const dsEditingData = ref<Api.Bi.BiDatasource | null>(null);

function handleAddDs() {
  dsOperateType.value = 'add';
  dsEditingData.value = null;
  dsModalVisible.value = true;
}

function handleEditDs(row: Api.Bi.BiDatasource) {
  dsOperateType.value = 'edit';
  dsEditingData.value = row;
  dsModalVisible.value = true;
}

async function onDsSubmitted() {
  await loadDatasources();
}

async function handleDeleteDs(row: Api.Bi.BiDatasource) {
  const { error } = await fetchDeleteBiDatasource({ id: row.id });
  if (error) return;
  window.$message?.success($t('common.deleteSuccess'));
  await loadDatasources();
}

async function handleTestDs(row: Api.Bi.BiDatasource) {
  testingId.value = row.id;
  const { data, error } = await fetchTestBiDatasource(row.id);
  testingId.value = null;
  if (error) return;
  if (data?.success) {
    window.$message?.success(`${$t('page.bi.metadata.testSuccess')} (${data.elapsedMs}ms)`);
  } else {
    window.$message?.error(`${$t('page.bi.metadata.testFailed')}: ${data?.message || ''}`);
  }
}

async function handleSyncDs(row: Api.Bi.BiDatasource) {
  syncingId.value = row.id;
  const { data, error } = await fetchSyncBiDatasource(row.id);
  syncingId.value = null;
  if (error) return;
  if (data) {
    window.$message?.success(
      `${$t('page.bi.metadata.syncSuccess')}: ${data.tablesSynced} ${$t('page.bi.metadata.tableCount').toLowerCase()} / ${data.columnsSynced} ${$t('page.bi.metadata.columnCount').toLowerCase()} / ${data.indexesSynced} ${$t('page.bi.metadata.indexCount').toLowerCase()}`
    );
    await loadDatasources();
  }
}

const dsRowProps = (row: Api.Bi.BiDatasource) => ({
  style: 'cursor: pointer;',
  onClick: (e: MouseEvent) => {
    const target = e.target as HTMLElement;
    if (target.closest('button') || target.closest('.n-popconfirm') || target.closest('.n-button')) return;
    handleViewDetail(row);
  }
});

onMounted(loadDatasources);
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <!-- Datasource List -->
    <NCard :bordered="false" size="small" class="card-wrapper" :title="$t('page.bi.metadata.datasourceList')">
      <template #header-extra>
        <NSpace :size="8" align="center">
          <NButton size="small" @click="loadDatasources">
            <template #icon><icon-ic-round-refresh class="text-icon" /></template>
            {{ $t('common.refresh') }}
          </NButton>
          <NButton v-if="hasAuth('B_BI_DS_CREATE')" size="small" type="primary" @click="handleAddDs">
            <template #icon><icon-ic-round-plus class="text-icon" /></template>
            {{ $t('page.bi.metadata.addDatasource') }}
          </NButton>
        </NSpace>
      </template>
      <NDataTable
        :columns="dsColumns"
        :data="datasources"
        size="small"
        :scroll-x="1200"
        :row-key="(row: Api.Bi.BiDatasource) => row.id"
        :row-props="dsRowProps"
        :pagination="false"
      />
    </NCard>

    <DatasourceOperateModal
      v-model:visible="dsModalVisible"
      :operate-type="dsOperateType"
      :row-data="dsEditingData"
      @submitted="onDsSubmitted"
    />
  </div>
</template>
