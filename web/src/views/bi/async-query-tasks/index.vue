<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { NButton, NPopconfirm, NSpace, NTag } from 'naive-ui';
import type { DataTableColumns, SelectOption } from 'naive-ui';
import {
  buildBiAsyncDownloadUrl,
  fetchBiAsyncTaskCancel,
  fetchBiAsyncTaskDelete,
  fetchBiAsyncTaskSearch
} from '@/service/api/bi-async-query';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';

defineOptions({ name: 'BiAsyncQueryTasks' });

const router = useRouter();
const { hasAuth } = useAuth();

const canCancel = computed(() => hasAuth('B_BI_SQL_TASK_CANCEL'));
const canDelete = computed(() => hasAuth('B_BI_SQL_TASK_DELETE'));
const canDownload = computed(() => hasAuth('B_BI_SQL_TASK_DOWNLOAD'));

const loading = ref<boolean>(false);
const tasks = ref<Api.Bi.BiQueryTask[]>([]);
const total = ref<number>(0);
const current = ref<number>(1);
const size = ref<number>(10);

const searchName = ref<string>('');
const searchStatus = ref<Api.Bi.BiQueryTaskStatus | null>(null);

const pollingTimer = ref<number | null>(null);

const statusOptions: SelectOption[] = [
  { label: $t('page.bi.async-query-tasks.status.pending'), value: 'pending' },
  { label: $t('page.bi.async-query-tasks.status.running'), value: 'running' },
  { label: $t('page.bi.async-query-tasks.status.success'), value: 'success' },
  { label: $t('page.bi.async-query-tasks.status.failed'), value: 'failed' },
  { label: $t('page.bi.async-query-tasks.status.cancelled'), value: 'cancelled' }
];

const statusTagType: Record<Api.Bi.BiQueryTaskStatus, 'default' | 'info' | 'success' | 'error' | 'warning'> = {
  pending: 'default',
  running: 'info',
  success: 'success',
  failed: 'error',
  cancelled: 'warning'
};

function statusLabel(status: Api.Bi.BiQueryTaskStatus): string {
  return $t(`page.bi.async-query-tasks.status.${status}`);
}

async function loadTasks() {
  loading.value = true;
  try {
    const { data, error } = await fetchBiAsyncTaskSearch({
      current: current.value,
      size: size.value,
      name: searchName.value || undefined,
      status: searchStatus.value || undefined
    });
    if (!error && data) {
      tasks.value = data.records;
      total.value = data.total;
    }
  } finally {
    loading.value = false;
  }
}

function viewDetail(id: string) {
  router.push({ name: 'bi_async-query-detail', params: { id } });
}

async function cancelTask(id: string) {
  const { error } = await fetchBiAsyncTaskCancel(id);
  if (!error) {
    window.$message?.success($t('page.bi.async-query-tasks.actions.cancelSuccess'));
    await loadTasks();
  }
}

async function removeTask(id: string) {
  const { error } = await fetchBiAsyncTaskDelete(id);
  if (!error) {
    window.$message?.success($t('common.deleteSuccess'));
    await loadTasks();
  }
}

function downloadCsv(id: string) {
  window.open(buildBiAsyncDownloadUrl(id), '_blank');
}

function onPageChange(p: number) {
  current.value = p;
  loadTasks();
}

function onSearch() {
  current.value = 1;
  loadTasks();
}

function startPolling() {
  stopPolling();
  pollingTimer.value = window.setInterval(() => {
    if (tasks.value.some(t => t.status === 'pending' || t.status === 'running')) {
      loadTasks();
    }
  }, 3000);
}

function stopPolling() {
  if (pollingTimer.value !== null) {
    clearInterval(pollingTimer.value);
    pollingTimer.value = null;
  }
}

const columns = computed<DataTableColumns<Api.Bi.BiQueryTask>>(() => [
  {
    key: 'name',
    title: $t('page.bi.async-query-tasks.columns.name'),
    minWidth: 160,
    ellipsis: { tooltip: true },
    render: row => row.name || '-'
  },
  {
    key: 'status',
    title: $t('page.bi.async-query-tasks.columns.status'),
    width: 100,
    render: row =>
      h(NTag, { type: statusTagType[row.status], size: 'small' }, { default: () => statusLabel(row.status) })
  },
  {
    key: 'progress',
    title: $t('page.bi.async-query-tasks.columns.progress'),
    width: 80,
    render: row => `${row.progress}%`
  },
  { key: 'rowsFetched', title: $t('page.bi.async-query-tasks.columns.rowsFetched'), width: 120 },
  { key: 'elapsedMs', title: $t('page.bi.async-query-tasks.columns.elapsedMs'), width: 100 },
  {
    key: 'source',
    title: $t('page.bi.async-query-tasks.columns.source'),
    width: 110,
    render: row =>
      row.source === 'auto_transfer'
        ? $t('page.bi.async-query-tasks.sourceAutoTransfer')
        : $t('page.bi.async-query-tasks.sourceManual')
  },
  {
    key: 'createdAt',
    title: $t('page.bi.async-query-tasks.columns.createdAt'),
    minWidth: 160,
    ellipsis: { tooltip: true }
  },
  {
    key: 'actions',
    title: $t('page.bi.async-query-tasks.columns.actions'),
    width: 220,
    fixed: 'right',
    render: row =>
      h(
        NSpace,
        { size: 4 },
        {
          default: () => [
            h(
              NButton,
              { size: 'small', text: true, type: 'primary', onClick: () => viewDetail(row.id) },
              { default: () => $t('page.bi.async-query-tasks.actions.view') }
            ),
            canCancel.value && (row.status === 'running' || row.status === 'pending')
              ? h(
                  NPopconfirm,
                  { onPositiveClick: () => cancelTask(row.id) },
                  {
                    default: () => $t('page.bi.async-query-tasks.cancelConfirm'),
                    trigger: () =>
                      h(
                        NButton,
                        { size: 'small', text: true, type: 'warning' },
                        { default: () => $t('page.bi.async-query-tasks.actions.cancel') }
                      )
                  }
                )
              : null,
            canDownload.value && row.status === 'success'
              ? h(
                  NButton,
                  { size: 'small', text: true, type: 'info', onClick: () => downloadCsv(row.id) },
                  { default: () => $t('page.bi.async-query-tasks.actions.download') }
                )
              : null,
            canDelete.value
              ? h(
                  NPopconfirm,
                  { onPositiveClick: () => removeTask(row.id) },
                  {
                    default: () => $t('page.bi.async-query-tasks.deleteConfirm'),
                    trigger: () =>
                      h(
                        NButton,
                        { size: 'small', text: true, type: 'error' },
                        { default: () => $t('page.bi.async-query-tasks.actions.delete') }
                      )
                  }
                )
              : null
          ]
        }
      )
  }
]);

onMounted(() => {
  loadTasks();
  startPolling();
});

onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <div class="h-full flex-col-stretch">
    <NCard :bordered="false" size="small" class="card-wrapper">
      <template #header>
        <span class="text-16px font-medium">{{ $t('page.bi.async-query-tasks.title') }}</span>
      </template>
      <template #header-extra>
        <NSpace :size="8" align="center" wrap>
          <NInput
            v-model:value="searchName"
            :placeholder="$t('page.bi.async-query-tasks.searchNamePlaceholder')"
            clearable
            size="small"
            style="width: 200px"
            @keyup.enter="onSearch"
          />
          <NSelect
            v-model:value="searchStatus"
            :options="statusOptions"
            :placeholder="$t('page.bi.async-query-tasks.statusPlaceholder')"
            size="small"
            clearable
            style="width: 160px"
            @update:value="onSearch"
          />
          <NButton size="small" type="primary" @click="onSearch">
            <template #icon>
              <icon-ic-round-search class="text-icon" />
            </template>
            {{ $t('common.search') }}
          </NButton>
        </NSpace>
      </template>
      <NDataTable
        :columns="columns"
        :data="tasks"
        :loading="loading"
        size="small"
        :scroll-x="1100"
        :row-key="(row: Api.Bi.BiQueryTask) => row.id"
        :pagination="{
          page: current,
          pageSize: size,
          itemCount: total,
          showSizePicker: true,
          pageSizes: [10, 20, 50],
          prefix: (info: { itemCount: number | undefined }) =>
            $t('datatable.itemCount', { total: info.itemCount ?? 0 }),
          onUpdatePage: onPageChange,
          onUpdatePageSize: (ps: number) => {
            size = ps;
            current = 1;
            loadTasks();
          }
        }"
      />
    </NCard>
  </div>
</template>
