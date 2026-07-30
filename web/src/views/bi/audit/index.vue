<script setup lang="tsx">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { NButton, NTag } from 'naive-ui';
import {
  fetchBiAuditLogList,
  fetchBiAuditStats,
  fetchExportBiAuditLogs
} from '@/service/api/bi-audit';
import { useAppStore } from '@/store/modules/app';
import { defaultTransform, useNaivePaginatedTable } from '@/hooks/common/table';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';

defineOptions({ name: 'BiAudit' });

const appStore = useAppStore();
const { hasAuth } = useAuth();

const searchParams = reactive<Api.Bi.BiAuditSearchParams>({
  current: 1,
  size: 10,
  eventType: null,
  action: null,
  userId: null,
  username: null,
  status: null,
  resourceType: null,
  createdAtStart: null,
  createdAtEnd: null
});

const timeRange = ref<[number, number] | null>(null);

watch(timeRange, val => {
  if (val) {
    searchParams.createdAtStart = val[0];
    searchParams.createdAtEnd = val[1];
  } else {
    searchParams.createdAtStart = null;
    searchParams.createdAtEnd = null;
  }
});

const eventTypeOptions = computed(() => [
  { label: $t('page.bi.audit.eventTypes.datasource'), value: 'datasource' },
  { label: $t('page.bi.audit.eventTypes.metadata'), value: 'metadata' },
  { label: $t('page.bi.audit.eventTypes.chat'), value: 'chat' },
  { label: $t('page.bi.audit.eventTypes.sql'), value: 'sql' },
  { label: $t('page.bi.audit.eventTypes.metric'), value: 'metric' },
  { label: $t('page.bi.audit.eventTypes.llm'), value: 'llm' }
]);

const statusOptions = computed(() => [
  { label: $t('page.bi.audit.statuses.success'), value: 'success' },
  { label: $t('page.bi.audit.statuses.failed'), value: 'failed' }
]);

const stats = ref<Api.Bi.BiAuditStats>({
  total: 0,
  successCount: 0,
  failedCount: 0,
  byEventType: {},
  byAction: {},
  byUser: {}
});

const statsLoading = ref(false);

async function loadStats() {
  statsLoading.value = true;
  const params: Api.Bi.BiAuditStatsParams = {};
  if (searchParams.createdAtStart) params.startDate = searchParams.createdAtStart;
  if (searchParams.createdAtEnd) params.endDate = searchParams.createdAtEnd;
  const { data, error } = await fetchBiAuditStats(params);
  statsLoading.value = false;
  if (!error && data) {
    stats.value = data;
  }
}

const successRate = computed(() => {
  if (stats.value.total === 0) return '0%';
  return `${((stats.value.successCount / stats.value.total) * 100).toFixed(1)}%`;
});

const { columns, columnChecks, data, loading, getData, getDataByPage, mobilePagination } = useNaivePaginatedTable({
  api: () => fetchBiAuditLogList(searchParams),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.current = params.page;
    searchParams.size = params.pageSize;
  },
  columns: () => [
    {
      type: 'expand',
      renderExpand: (row: Api.Bi.BiAuditLog) => (
        <div class="px-24px py-12px">
          {row.detail ? (
            <div class="mb-8px">
              <div class="mb-4px text-12px text-gray-400">{$t('page.bi.audit.detail')}</div>
              <NCode code={JSON.stringify(row.detail, null, 2)} language="json" word-wrap />
            </div>
          ) : null}
          {row.errorMessage ? (
            <NAlert type="error" title={$t('page.bi.audit.errorMessage')}>
              {row.errorMessage}
            </NAlert>
          ) : null}
        </div>
      )
    },
    { key: 'index', title: $t('common.index'), width: 64, align: 'center', render: (_, index) => index + 1 },
    {
      key: 'traceId',
      title: $t('page.bi.audit.traceId'),
      minWidth: 180,
      render: row => <span class="font-mono text-12px break-all">{row.traceId || '-'}</span>
    },
    { key: 'eventType', title: $t('page.bi.audit.eventType'), align: 'center', minWidth: 100 },
    { key: 'action', title: $t('page.bi.audit.action'), minWidth: 140 },
    {
      key: 'username',
      title: $t('page.bi.audit.user'),
      align: 'center',
      minWidth: 120,
      render: row => row.username || row.userId || '-'
    },
    { key: 'ipAddress', title: $t('page.bi.audit.ip'), align: 'center', minWidth: 130, render: row => row.ipAddress || '-' },
    {
      key: 'resourceType',
      title: $t('page.bi.audit.resource'),
      align: 'center',
      minWidth: 110,
      render: row => row.resourceType || '-'
    },
    {
      key: 'status',
      title: $t('page.bi.audit.status'),
      align: 'center',
      width: 90,
      render: row => (
        <NTag type={row.status === 'success' ? 'success' : 'error'} size="small">
          {row.status === 'success' ? $t('page.bi.audit.statuses.success') : $t('page.bi.audit.statuses.failed')}
        </NTag>
      )
    },
    {
      key: 'executionTimeMs',
      title: $t('page.bi.audit.executionTime'),
      align: 'center',
      width: 100,
      render: row => (row.executionTimeMs != null ? `${row.executionTimeMs}ms` : '-')
    },
    {
      key: 'fmtCreatedAt',
      title: $t('page.bi.audit.startTime'),
      align: 'center',
      minWidth: 160,
      render: row => row.fmtCreatedAt || '-'
    }
  ]
});

function handleSearch() {
  getDataByPage(1);
  loadStats();
}

function resetSearchParams() {
  Object.assign(searchParams, {
    current: 1,
    eventType: null,
    action: null,
    userId: null,
    username: null,
    status: null,
    resourceType: null,
    createdAtStart: null,
    createdAtEnd: null
  });
  timeRange.value = null;
}

const exporting = ref(false);
async function handleExport() {
  exporting.value = true;
  const { data: blob, error } = await fetchExportBiAuditLogs(searchParams);
  exporting.value = false;
  if (error || !blob) return;
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `audit-${Date.now()}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  window.$message?.success($t('page.bi.audit.exportSuccess'));
}

onMounted(() => {
  getData();
  loadStats();
});
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <!-- Stat Cards -->
    <NGrid :cols="appStore.isMobile ? 1 : 4" :x-gap="16" :y-gap="16">
      <NCard :bordered="false" size="small" class="card-wrapper">
        <NStatistic :label="$t('page.bi.audit.total')" :value="stats.total" />
      </NCard>
      <NCard :bordered="false" size="small" class="card-wrapper">
        <NStatistic :label="$t('page.bi.audit.successCount')" :value="stats.successCount">
          <template #suffix><NTag type="success" size="small" class="ml-8px">✓</NTag></template>
        </NStatistic>
      </NCard>
      <NCard :bordered="false" size="small" class="card-wrapper">
        <NStatistic :label="$t('page.bi.audit.failedCount')" :value="stats.failedCount">
          <template #suffix><NTag type="error" size="small" class="ml-8px">✕</NTag></template>
        </NStatistic>
      </NCard>
      <NCard :bordered="false" size="small" class="card-wrapper">
        <NStatistic :label="$t('page.bi.audit.successCount') + ' %'" :value="successRate" />
      </NCard>
    </NGrid>

    <!-- Search -->
    <NCard :bordered="false" size="small" class="card-wrapper">
      <NCollapse :default-expanded-names="['audit-search']">
        <NCollapseItem :title="$t('common.search')" name="audit-search">
          <NForm :model="searchParams" label-placement="left" :label-width="90">
            <NGrid responsive="screen" item-responsive>
              <NFormItemGi span="24 s:12 m:6" :label="$t('page.bi.audit.eventType')" path="eventType" class="pr-24px">
                <NSelect
                  v-model:value="searchParams.eventType"
                  :options="eventTypeOptions"
                  clearable
                  :placeholder="$t('page.bi.audit.eventType')"
                />
              </NFormItemGi>
              <NFormItemGi span="24 s:12 m:6" :label="$t('page.bi.audit.action')" path="action" class="pr-24px">
                <NInput v-model:value="searchParams.action" clearable :placeholder="$t('page.bi.audit.action')" />
              </NFormItemGi>
              <NFormItemGi span="24 s:12 m:6" :label="$t('page.bi.audit.username')" path="username" class="pr-24px">
                <NInput v-model:value="searchParams.username" clearable :placeholder="$t('page.bi.audit.username')" />
              </NFormItemGi>
              <NFormItemGi span="24 s:12 m:6" :label="$t('page.bi.audit.status')" path="status" class="pr-24px">
                <NSelect
                  v-model:value="searchParams.status"
                  :options="statusOptions"
                  clearable
                  :placeholder="$t('page.bi.audit.status')"
                />
              </NFormItemGi>
              <NFormItemGi span="24 s:12 m:12" :label="$t('page.bi.audit.timeRange')" path="timeRange" class="pr-24px">
                <NDatePicker v-model:value="timeRange" type="datetimerange" clearable class="w-full" />
              </NFormItemGi>
              <NFormItemGi span="24 s:12 m:6" :label="$t('page.bi.audit.resource')" path="resourceType" class="pr-24px">
                <NInput
                  v-model:value="searchParams.resourceType"
                  clearable
                  :placeholder="$t('page.bi.audit.resource')"
                />
              </NFormItemGi>
              <NFormItemGi span="24 s:12 m:6">
                <NSpace class="w-full" justify="end">
                  <NButton @click="resetSearchParams">
                    <template #icon><icon-ic-round-refresh class="text-icon" /></template>
                    {{ $t('common.reset') }}
                  </NButton>
                  <NButton type="primary" ghost :loading="statsLoading" @click="handleSearch">
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

    <!-- Table -->
    <NCard :title="$t('page.bi.audit.title')" :bordered="false" size="small" class="card-wrapper sm:flex-1-hidden">
      <template #header-extra>
        <NSpace :size="8" align="center">
          <TableHeaderOperation v-model:columns="columnChecks" :loading="loading" @refresh="getData">
            <template #default>
              <span />
            </template>
          </TableHeaderOperation>
          <NButton
            v-if="hasAuth('B_BI_AUDIT_EXPORT')"
            size="small"
            ghost
            type="primary"
            :loading="exporting"
            @click="handleExport"
          >
            <template #icon><icon-ic-round-download class="text-icon" /></template>
            {{ $t('page.bi.audit.export') }}
          </NButton>
        </NSpace>
      </template>
      <NDataTable
        :columns="columns"
        :data="data"
        size="small"
        :flex-height="!appStore.isMobile"
        :scroll-x="1300"
        :loading="loading"
        remote
        :row-key="row => row.id"
        :pagination="mobilePagination"
        class="sm:h-full"
      />
    </NCard>
  </div>
</template>
