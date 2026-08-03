<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import type { DataTableColumns } from 'naive-ui';
import { buildBiAsyncDownloadUrl, fetchBiAsyncTask, fetchBiAsyncTaskCancel } from '@/service/api/bi-async-query';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';

defineOptions({ name: 'BiAsyncQueryDetail' });

const route = useRoute();
const router = useRouter();
const { hasAuth } = useAuth();

const canCancel = computed(() => hasAuth('B_BI_SQL_TASK_CANCEL'));
const canDownload = computed(() => hasAuth('B_BI_SQL_TASK_DOWNLOAD'));

const task = ref<Api.Bi.BiQueryTask | null>(null);
const loading = ref<boolean>(false);
const pollingTimer = ref<number | null>(null);

const taskId = computed(() => route.params.id as string);

const isRunning = computed(() => task.value?.status === 'pending' || task.value?.status === 'running');

const statusTagType = computed<'default' | 'info' | 'success' | 'error' | 'warning'>(() => {
  if (!task.value) return 'default';
  const map: Record<Api.Bi.BiQueryTaskStatus, 'default' | 'info' | 'success' | 'error' | 'warning'> = {
    pending: 'default',
    running: 'info',
    success: 'success',
    failed: 'error',
    cancelled: 'warning'
  };
  return map[task.value.status];
});

const statusLabel = computed(() => {
  if (!task.value) return '';
  return $t(`page.bi.async-query-tasks.status.${task.value.status}`);
});

const previewColumns = computed<DataTableColumns<Record<string, any>>>(() => {
  const cols = task.value?.resultSnapshot?.columns ?? [];
  return cols.map(c => ({ key: c, title: c, minWidth: 140, ellipsis: { tooltip: true } }));
});

const previewRows = computed<Record<string, any>[]>(() => task.value?.resultSnapshot?.rows ?? []);

async function loadTask() {
  loading.value = true;
  try {
    const { data, error } = await fetchBiAsyncTask(taskId.value);
    if (!error && data) {
      task.value = data;
    }
  } finally {
    loading.value = false;
  }
}

async function cancel() {
  const { error } = await fetchBiAsyncTaskCancel(taskId.value);
  if (!error) {
    window.$message?.success($t('page.bi.async-query-tasks.actions.cancelSuccess'));
    await loadTask();
  }
}

function downloadCsv() {
  window.open(buildBiAsyncDownloadUrl(taskId.value), '_blank');
}

function back() {
  router.push({ name: 'bi_async-query-tasks' });
}

function startPolling() {
  stopPolling();
  pollingTimer.value = window.setInterval(() => {
    if (isRunning.value) {
      loadTask();
    } else {
      stopPolling();
    }
  }, 2000);
}

function stopPolling() {
  if (pollingTimer.value !== null) {
    clearInterval(pollingTimer.value);
    pollingTimer.value = null;
  }
}

onMounted(() => {
  loadTask().then(startPolling);
});

onUnmounted(stopPolling);
</script>

<template>
  <div class="h-full flex-col-stretch overflow-auto">
    <NSpin :show="loading">
      <NCard v-if="task" :bordered="false" size="small" class="card-wrapper">
        <template #header>
          <span class="text-16px font-medium">
            {{ $t('page.bi.async-query-tasks.detail.title') }}{{ task.name ? ` - ${task.name}` : '' }}
          </span>
        </template>
        <template #header-extra>
          <NSpace :size="8">
            <NButton size="small" @click="back">
              <template #icon>
                <icon-ic-round-arrow-back class="text-icon" />
              </template>
              {{ $t('page.bi.async-query-tasks.detail.back') }}
            </NButton>
            <NButton v-if="canCancel && isRunning" size="small" type="warning" @click="cancel">
              {{ $t('page.bi.async-query-tasks.detail.cancel') }}
            </NButton>
            <NButton v-if="canDownload && task.status === 'success'" size="small" type="info" @click="downloadCsv">
              <template #icon>
                <icon-ic-round-download class="text-icon" />
              </template>
              {{ $t('page.bi.async-query-tasks.detail.download') }}
            </NButton>
          </NSpace>
        </template>

        <NDescriptions :column="3" bordered label-placement="left" size="small">
          <NDescriptionsItem :label="$t('page.bi.async-query-tasks.columns.status')">
            <NTag :type="statusTagType" size="small">{{ statusLabel }}</NTag>
          </NDescriptionsItem>
          <NDescriptionsItem :label="$t('page.bi.async-query-tasks.columns.progress')">
            <NProgress type="line" :percentage="task.progress" />
          </NDescriptionsItem>
          <NDescriptionsItem :label="$t('page.bi.async-query-tasks.columns.rowsFetched')">
            {{ task.rowsFetched }}
          </NDescriptionsItem>
          <NDescriptionsItem :label="$t('page.bi.async-query-tasks.columns.elapsedMs')">
            {{ task.elapsedMs }}
          </NDescriptionsItem>
          <NDescriptionsItem :label="$t('page.bi.async-query-tasks.detail.resultRowCount')">
            {{ task.resultRowCount }}
          </NDescriptionsItem>
          <NDescriptionsItem :label="$t('page.bi.async-query-tasks.columns.source')">
            {{
              task.source === 'auto_transfer'
                ? $t('page.bi.async-query-tasks.sourceAutoTransfer')
                : $t('page.bi.async-query-tasks.sourceManual')
            }}
          </NDescriptionsItem>
          <NDescriptionsItem :label="$t('page.bi.async-query-tasks.detail.startedAt')">
            {{ task.startedAt || '-' }}
          </NDescriptionsItem>
          <NDescriptionsItem :label="$t('page.bi.async-query-tasks.detail.finishedAt')">
            {{ task.finishedAt || '-' }}
          </NDescriptionsItem>
          <NDescriptionsItem :label="$t('page.bi.async-query-tasks.columns.createdAt')">
            {{ task.createdAt }}
          </NDescriptionsItem>
          <NDescriptionsItem v-if="task.sqlText" :label="$t('page.bi.async-query-tasks.detail.sqlLabel')" :span="3">
            <pre class="sql-pre">{{ task.sqlText }}</pre>
          </NDescriptionsItem>
        </NDescriptions>

        <NAlert
          v-if="task.status === 'failed'"
          type="error"
          class="mt-12px"
          :title="task.errorMessage || $t('page.bi.async-query-tasks.status.failed')"
        />
        <NAlert
          v-if="task.status === 'cancelled'"
          type="warning"
          class="mt-12px"
          :title="task.errorMessage || $t('page.bi.async-query-tasks.status.cancelled')"
        />

        <NCard v-if="task.resultSnapshot" :bordered="true" size="small" class="mt-12px">
          <template #header>
            <span class="text-14px font-medium">
              {{ $t('page.bi.async-query-tasks.detail.previewTitle') }}
              <span class="text-12px text-gray-500 ml-8px">
                {{
                  $t('page.bi.async-query-tasks.detail.previewSummary', {
                    total: task.resultRowCount,
                    preview: task.resultSnapshot.rowCount,
                    truncated: task.resultIsTruncated ? $t('page.bi.async-query-tasks.detail.truncated') : ''
                  })
                }}
              </span>
            </span>
          </template>
          <NDataTable
            :columns="previewColumns"
            :data="previewRows"
            size="small"
            :scroll-x="1000"
            :max-height="400"
            :row-key="(row: Record<string, any>) => JSON.stringify(row)"
          />
        </NCard>
      </NCard>
      <NEmpty v-else-if="!loading" :description="$t('common.noData')" class="py-48px" />
    </NSpin>
  </div>
</template>

<style scoped>
.sql-pre {
  margin: 0;
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
