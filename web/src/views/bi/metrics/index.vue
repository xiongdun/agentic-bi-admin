<script setup lang="tsx">
import { ref } from 'vue';
import { NButton, NCard, NEmpty, NPopconfirm, NSelect, NSpace, NSwitch, NTag } from 'naive-ui';
import {
  fetchBiDatasourceList,
  fetchBiMetricList,
  fetchCreateBiMetric,
  fetchDeleteBiMetric,
  fetchTestBiMetric,
  fetchUpdateBiMetric
} from '@/service/api';
import { defaultTransform, useNaivePaginatedTable } from '@/hooks/common/table';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';
import MetricOperateModal from './modules/metric-operate-modal.vue';
import MetricTestModal from './modules/metric-test-modal.vue';

const { hasAuth } = useAuth();

const PAGE_SIZE = 20;

const canView = hasAuth('B_BI_METRIC_VIEW');
const canManage = hasAuth('B_BI_METRIC_MANAGE');

const searchParams = ref<Api.Bi.MetricSearchParams>({
  current: 1,
  size: PAGE_SIZE,
  name: null,
  datasourceId: null,
  statusType: null
});

const datasourceOptions = ref<{ label: string; value: string }[]>([]);
const datasourceLabelMap = ref<Map<string, string>>(new Map());

async function loadDatasources() {
  try {
    const resp = await fetchBiDatasourceList({ current: 1, size: 100, name: null, type: null });
    const records = resp.data?.records ?? [];
    datasourceOptions.value = records.map(d => ({ label: d.name, value: d.id }));
    datasourceLabelMap.value = new Map(records.map(d => [d.id, d.name]));
  } catch {
    // 非阻塞：数据源失败也不影响列表
    datasourceOptions.value = [];
  }
}

const {
  columns: metricColumns,
  data: metricData,
  loading: metricLoading,
  getData: getMetricData
} = useNaivePaginatedTable({
  api: () => fetchBiMetricList(searchParams.value),
  transform: response => defaultTransform(response),
  showTotal: true,
  initialPageSize: PAGE_SIZE,
  onPaginationParamsChange: params => {
    searchParams.value.current = params.page ?? 1;
    searchParams.value.size = params.pageSize ?? PAGE_SIZE;
  },
  columns: () => [
    {
      key: 'index',
      title: '#',
      width: 48,
      render: (_, index) => index + 1
    },
    {
      key: 'name',
      title: $t('page.bi.metrics.columns.name'),
      width: 160
    },
    {
      key: 'displayName',
      title: $t('page.bi.metrics.columns.displayName'),
      width: 160
    },
    {
      key: 'description',
      title: $t('page.bi.metrics.columns.description'),
      minWidth: 180,
      ellipsis: { tooltip: true },
      render: row => row.description || '-'
    },
    {
      key: 'sqlTemplate',
      title: $t('page.bi.metrics.columns.sqlTemplate'),
      minWidth: 240,
      ellipsis: { tooltip: true },
      render: row => <code class="text-12px">{row.sqlTemplate}</code>
    },
    {
      key: 'unit',
      title: $t('page.bi.metrics.columns.unit'),
      width: 80,
      render: row => row.unit ?? '-'
    },
    {
      key: 'datasourceId',
      title: $t('page.bi.metrics.columns.datasource'),
      width: 160,
      render: row => datasourceLabelMap.value.get(row.datasourceId) ?? row.datasourceId ?? '-'
    },
    {
      key: 'statusType',
      title: $t('page.bi.metrics.columns.status'),
      width: 90,
      render: row => (
        <NSwitch
          value={row.statusType === '1'}
          size="small"
          disabled={!canManage}
          onUpdateValue={async (val: boolean) => {
            await fetchUpdateBiMetric(row.id, { statusType: val ? '1' : '2' });
            window.$message?.success($t('common.updateSuccess'));
            await getMetricData();
          }}
        />
      )
    },
    {
      key: 'op',
      title: $t('page.bi.metrics.columns.actions'),
      width: 280,
      fixed: 'right',
      render: row => (
        <NSpace size={8}>
          {canManage && (
            <NButton size="tiny" onClick={() => handleEdit(row)}>
              {$t('common.modify')}
            </NButton>
          )}
          {canManage && (
            <NButton size="tiny" type="primary" ghost onClick={() => handleTest(row)}>
              {$t('page.bi.metrics.test')}
            </NButton>
          )}
          {canManage && (
            <NPopconfirm onPositiveClick={() => handleDelete(row)}>
              {{
                trigger: () => (
                  <NButton size="tiny" type="error" ghost>
                    {$t('common.delete')}
                  </NButton>
                ),
                default: () => $t('page.bi.metrics.actions.confirmDelete')
              }}
            </NPopconfirm>
          )}
        </NSpace>
      )
    }
  ]
});

// ===== 弹窗 =====
const modalShow = ref(false);
const modalRecord = ref<Api.Bi.Metric | null>(null);

function handleCreate() {
  modalRecord.value = null;
  modalShow.value = true;
}

function handleEdit(row: Api.Bi.Metric) {
  modalRecord.value = row;
  modalShow.value = true;
}

async function handleSubmit(payload: Api.Bi.MetricCreateParams | (Api.Bi.MetricUpdateParams & { id: string })) {
  if ('id' in payload) {
    const { id, ...rest } = payload;
    await fetchUpdateBiMetric(id, rest);
    window.$message?.success($t('common.updateSuccess'));
  } else {
    await fetchCreateBiMetric(payload);
    window.$message?.success($t('common.addSuccess'));
  }
  modalShow.value = false;
  await getMetricData();
}

// ===== 测试 =====
const testModalShow = ref(false);
const testResult = ref<Api.Bi.MetricTestResult | null>(null);
const testLoading = ref(false);

async function handleTest(row: Api.Bi.Metric) {
  testLoading.value = true;
  testResult.value = null;
  testModalShow.value = true;
  try {
    const resp = await fetchTestBiMetric(row.id);
    testResult.value = resp.data ?? null;
  } catch (e: any) {
    testResult.value = { success: false, error: e?.message ?? String(e) };
  } finally {
    testLoading.value = false;
  }
}

// ===== 删除 =====
async function handleDelete(row: Api.Bi.Metric) {
  await fetchDeleteBiMetric(row.id);
  window.$message?.success($t('common.deleteSuccess'));
  await getMetricData();
}

// 初次加载 + 监听搜索参数
function reload() {
  searchParams.value.current = 1;
  getMetricData();
}

defineExpose({ reload, loadDatasources });
</script>

<template>
  <div class="p-16px">
    <NCard v-if="canView" :title="$t('page.bi.metrics.title')">
      <template #header-extra>
        <NSpace>
          <NSelect
            v-model:value="searchParams.datasourceId"
            :options="datasourceOptions"
            :placeholder="$t('page.bi.metrics.search.datasource')"
            clearable
            style="width: 200px"
            @update:value="reload"
          />
          <NSelect
            v-model:value="searchParams.statusType"
            :options="[
              { label: $t('page.bi.metrics.status.enable'), value: 'enable' },
              { label: $t('page.bi.metrics.status.disable'), value: 'disable' }
            ]"
            :placeholder="$t('page.bi.metrics.search.status')"
            clearable
            style="width: 120px"
            @update:value="reload"
          />
          <NButton v-if="canManage" type="primary" @click="handleCreate">
            {{ $t('page.bi.metrics.create') }}
          </NButton>
        </NSpace>
      </template>

      <div class="mb-12px flex gap-8px">
        <NTag :bordered="false" type="info">
          {{ $t('page.bi.metrics.subtitle') }}
        </NTag>
      </div>

      <NDataTable
        :columns="metricColumns"
        :data="metricData"
        :loading="metricLoading"
        :row-key="(row: Api.Bi.Metric) => row.id"
        size="small"
        :bordered="false"
        flex-height
        style="margin-top: 12px"
      />
    </NCard>

    <NEmpty v-else :description="$t('page.bi.chat.messages.noPermission')" class="mt-32px" />

    <MetricOperateModal
      v-model:show="modalShow"
      :record="modalRecord"
      :datasource-options="datasourceOptions"
      @submit="handleSubmit"
    />

    <MetricTestModal
      v-model:show="testModalShow"
      :result="testResult"
      :loading="testLoading"
    />
  </div>
</template>
