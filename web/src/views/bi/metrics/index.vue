<script setup lang="tsx">
import { computed, onMounted, reactive, ref } from 'vue';
import { NButton, NPopconfirm, NTag } from 'naive-ui';
import { statusTypeRecord } from '@/constants/business';
import { fetchBiDatasourceList } from '@/service/api/bi';
import { fetchBiMetricList, fetchDeleteBiMetric, fetchTestBiMetric } from '@/service/api/bi-metric';
import { useAppStore } from '@/store/modules/app';
import { defaultTransform, useNaivePaginatedTable, useTableOperate } from '@/hooks/common/table';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';
import MetricOperateModal from './modules/metric-operate-modal.vue';
import MetricTestModal from './modules/metric-test-modal.vue';

defineOptions({ name: 'BiMetrics' });

const appStore = useAppStore();
const { hasAuth } = useAuth();

const searchParams = reactive<Api.Bi.BiMetricSearchParams>({
  current: 1,
  size: 10,
  name: null,
  code: null,
  datasourceId: null,
  statusType: null
});

const chartTypeOptions = computed(() => [
  { label: $t('page.bi.metrics.chartTypes.table'), value: 'table' },
  { label: $t('page.bi.metrics.chartTypes.line'), value: 'line' },
  { label: $t('page.bi.metrics.chartTypes.bar'), value: 'bar' },
  { label: $t('page.bi.metrics.chartTypes.pie'), value: 'pie' },
  { label: $t('page.bi.metrics.chartTypes.scatter'), value: 'scatter' },
  { label: $t('page.bi.metrics.chartTypes.area'), value: 'area' }
]);

const chartTypeLabel = (val: string | null) => {
  if (!val) return null;
  const opt = chartTypeOptions.value.find(o => o.value === val);
  return opt ? opt.label : val;
};

const datasourceMap = ref<Record<string, Api.Bi.BiDatasource>>({});
const datasourceOptions = ref<{ label: string; value: string }[]>([]);

async function loadDatasources() {
  const { data } = await fetchBiDatasourceList({ current: 1, size: 999 });
  if (data?.records) {
    const map: Record<string, Api.Bi.BiDatasource> = {};
    data.records.forEach(d => {
      map[d.id] = d;
    });
    datasourceMap.value = map;
    datasourceOptions.value = data.records.map(d => ({ label: d.name, value: d.id }));
  }
}

onMounted(loadDatasources);

const { columns, columnChecks, data, loading, getData, getDataByPage, mobilePagination } = useNaivePaginatedTable({
  api: () => fetchBiMetricList(searchParams),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.current = params.page;
    searchParams.size = params.pageSize;
  },
  columns: () => [
    { type: 'selection', align: 'center', width: 48 },
    { key: 'index', title: $t('common.index'), width: 64, align: 'center', render: (_, index) => index + 1 },
    { key: 'name', title: $t('page.bi.metrics.name'), minWidth: 140 },
    { key: 'code', title: $t('page.bi.metrics.code'), align: 'center', minWidth: 140 },
    {
      key: 'datasourceId',
      title: $t('page.bi.metrics.datasource'),
      align: 'center',
      minWidth: 140,
      render: row => datasourceMap.value[row.datasourceId]?.name || row.datasourceId
    },
    {
      key: 'chartType',
      title: $t('page.bi.metrics.chartType'),
      align: 'center',
      minWidth: 100,
      render: row => {
        const label = chartTypeLabel(row.chartType);
        return label ? <NTag size="small">{label}</NTag> : null;
      }
    },
    {
      key: 'statusType',
      title: $t('page.bi.audit.status'),
      align: 'center',
      width: 90,
      render: row => {
        if (row.statusType === null) return null;
        const tagMap: Record<Api.Common.EnableStatus, NaiveUI.ThemeColor> = { '1': 'success', '2': 'warning' };
        return <NTag type={tagMap[row.statusType]}>{$t(statusTypeRecord[row.statusType])}</NTag>;
      }
    },
    {
      key: 'operate',
      title: $t('common.operate'),
      align: 'center',
      width: 240,
      render: row => (
        <div class="flex-center gap-8px">
          {hasAuth('B_BI_METRIC_TEST') && (
            <NButton type="info" ghost size="small" onClick={() => openTestModal(row)}>
              {$t('page.bi.metrics.test')}
            </NButton>
          )}
          {hasAuth('B_BI_METRIC_EDIT') && (
            <NButton type="primary" ghost size="small" onClick={() => edit(row.id)}>
              {$t('common.edit')}
            </NButton>
          )}
          {hasAuth('B_BI_METRIC_DELETE') && (
            <NPopconfirm onPositiveClick={() => handleDelete(row.id)}>
              {{
                default: () => $t('page.bi.metrics.deleteConfirm'),
                trigger: () => (
                  <NButton type="error" ghost size="small">
                    {$t('common.delete')}
                  </NButton>
                )
              }}
            </NPopconfirm>
          )}
        </div>
      )
    }
  ]
});

const { drawerVisible, operateType, editingData, handleAdd, handleEdit, checkedRowKeys, onDeleted } = useTableOperate(
  data,
  'id',
  getData
);

async function handleDelete(id: string) {
  const { error } = await fetchDeleteBiMetric({ id });
  if (!error) onDeleted();
}

function edit(id: string) {
  handleEdit(id);
}

const testVisible = ref(false);
const testTarget = ref<Api.Bi.BiMetric | null>(null);
const testLoading = ref(false);
const testResult = ref<Api.Bi.BiMetricTestResult | null>(null);

async function openTestModal(row: Api.Bi.BiMetric) {
  testTarget.value = row;
  testResult.value = null;
  testVisible.value = true;
  testLoading.value = true;
  const { data: result, error } = await fetchTestBiMetric(row.id);
  testLoading.value = false;
  if (!error && result) {
    testResult.value = result;
  }
}

function resetSearchParams() {
  Object.assign(searchParams, {
    current: 1,
    name: null,
    code: null,
    datasourceId: null,
    statusType: null
  });
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <NCard :bordered="false" size="small" class="card-wrapper">
      <NCollapse :default-expanded-names="['metric-search']">
        <NCollapseItem :title="$t('common.search')" name="metric-search">
          <NForm :model="searchParams" label-placement="left" :label-width="80">
            <NGrid responsive="screen" item-responsive>
              <NFormItemGi span="24 s:12 m:6" :label="$t('page.bi.metrics.name')" path="name" class="pr-24px">
                <NInput v-model:value="searchParams.name" clearable :placeholder="$t('page.bi.metrics.form.name')" />
              </NFormItemGi>
              <NFormItemGi span="24 s:12 m:6" :label="$t('page.bi.metrics.code')" path="code" class="pr-24px">
                <NInput v-model:value="searchParams.code" clearable :placeholder="$t('page.bi.metrics.form.code')" />
              </NFormItemGi>
              <NFormItemGi
                span="24 s:12 m:6"
                :label="$t('page.bi.metrics.datasource')"
                path="datasourceId"
                class="pr-24px"
              >
                <NSelect
                  v-model:value="searchParams.datasourceId"
                  :options="datasourceOptions"
                  clearable
                  :placeholder="$t('page.bi.metrics.form.datasource')"
                />
              </NFormItemGi>
              <NFormItemGi span="24 s:12 m:6">
                <NSpace class="w-full" justify="end">
                  <NButton @click="resetSearchParams">
                    <template #icon><icon-ic-round-refresh class="text-icon" /></template>
                    {{ $t('common.reset') }}
                  </NButton>
                  <NButton type="primary" ghost @click="getDataByPage(1)">
                    <template #icon><icon-ic-round-search class="text-icon" /></template>
                    {{ $t('common.search') }}
                  </NButton>
                </NSpace>
              </NFormItemGi>
            </NGrid>
          </NForm>
        </NCollapseItem>
      </NCollapse>
    </NCard>
    <NCard :title="$t('page.bi.metrics.title')" :bordered="false" size="small" class="card-wrapper sm:flex-1-hidden">
      <template #header-extra>
        <TableHeaderOperation v-model:columns="columnChecks" :loading="loading" @refresh="getData">
          <NButton v-if="hasAuth('B_BI_METRIC_CREATE')" size="small" ghost type="primary" @click="handleAdd">
            <template #icon><icon-ic-round-plus class="text-icon" /></template>
            {{ $t('page.bi.metrics.create') }}
          </NButton>
        </TableHeaderOperation>
      </template>
      <NDataTable
        v-model:checked-row-keys="checkedRowKeys"
        :columns="columns"
        :data="data"
        size="small"
        :flex-height="!appStore.isMobile"
        :scroll-x="1000"
        :loading="loading"
        remote
        :row-key="row => row.id"
        :pagination="mobilePagination"
        class="sm:h-full"
      />
      <MetricOperateModal
        v-model:visible="drawerVisible"
        :operate-type="operateType"
        :row-data="editingData"
        :datasource-options="datasourceOptions"
        @submitted="getDataByPage"
      />
      <MetricTestModal v-model:visible="testVisible" :target="testTarget" :loading="testLoading" :result="testResult" />
    </NCard>
  </div>
</template>
