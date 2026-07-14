<script setup lang="tsx">
import { computed, onMounted, ref, watch } from 'vue';
import {
  NAlert,
  NButton,
  NCard,
  NCheckbox,
  NDataTable,
  NEmpty,
  NInput,
  NPopconfirm,
  NSelect,
  NSpace,
  NSpin,
  NTag
} from 'naive-ui';
import { useClipboard } from '@vueuse/core';
import {
  fetchBiDatasourceList,
  fetchBiSqlExecute,
  fetchBiSqlExplain,
  fetchBiSqlHistory
} from '@/service/api';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';

const { hasAuth } = useAuth();

// ===== 数据源 =====
const dsOptions = ref<{ label: string; value: string }[]>([]);
const datasourceId = ref<string | null>(null);

async function loadDatasources() {
  const { data } = await fetchBiDatasourceList({ current: 1, size: 200, name: null, type: null });
  const records = data?.records ?? [];
  // 优先把默认数据源排在最前
  records.sort((a, b) => Number(b.isDefault) - Number(a.isDefault));
  dsOptions.value = records.map(d => ({
    label: `${d.name} (${d.type})${d.isDefault ? ' · 默认' : ''}`,
    value: d.id
  }));
  if (!datasourceId.value && dsOptions.value.length) {
    datasourceId.value = dsOptions.value[0].value;
  }
}

// ===== SQL 编辑器 =====
const sqlInput = ref<string>('');
const allowWrite = ref(false);
const running = ref(false);
const explainLoading = ref(false);
const historyLoading = ref(false);

const { copy: copyToClipboard } = useClipboard();

function handleFormat() {
  // 极简格式化：把空白压成单空格；保留换行分隔多条
  sqlInput.value = sqlInput.value
    .replace(/\s+/g, ' ')
    .replace(/\s*;\s*/g, ';\n')
    .trim();
}

function handleClear() {
  sqlInput.value = '';
}

function handleCopy() {
  copyToClipboard(sqlInput.value);
  window.$message?.success('已复制');
}

function requireDs(): string | null {
  if (!datasourceId.value) {
    window.$message?.warning($t('page.bi.sqlworkbench.messages.noDs'));
    return null;
  }
  return datasourceId.value;
}

// ===== 执行 =====
const result = ref<Api.Bi.SqlExecuteResponse | null>(null);
const executeError = ref<string | null>(null);
const executeDenied = ref<boolean>(false);

function handleCopyFinal() {
  const finalSql = result.value?.finalSql;
  if (!finalSql) {
    window.$message?.warning($t('page.bi.sqlworkbench.result.empty'));
    return;
  }
  copyToClipboard(finalSql);
  window.$message?.success('已复制');
}

async function handleRun() {
  const ds = requireDs();
  if (!ds) return;
  const sql = sqlInput.value.trim();
  if (!sql) {
    window.$message?.warning($t('page.bi.sqlworkbench.messages.emptySql'));
    return;
  }
  if (!hasAuth('B_BI_SQL_RUN')) {
    window.$message?.error($t('page.bi.sqlworkbench.messages.noPermission'));
    return;
  }
  running.value = true;
  executeError.value = null;
  executeDenied.value = false;
  try {
    const { data, error } = await fetchBiSqlExecute({
      datasourceId: ds,
      sql,
      allowWrite: allowWrite.value
    });
    if (error) {
      executeError.value = error.message || 'execute failed';
      return;
    }
    result.value = data ?? null;
    window.$message?.success($t('page.bi.sqlworkbench.messages.runOk'));
  } catch (e: any) {
    // 沙箱拒绝：code 4000+ 时 onBackendFail/onError 弹了 message，但仍会抛出，这里把 error 文本塞进 result 区
    executeError.value = e?.message ?? 'execute failed';
    executeDenied.value = true;
  } finally {
    running.value = false;
    loadHistory();
  }
}

// ===== EXPLAIN =====
const explainResult = ref<Api.Bi.SqlExplainResponse | null>(null);

async function handleExplain() {
  const ds = requireDs();
  if (!ds) return;
  const sql = sqlInput.value.trim();
  if (!sql) {
    window.$message?.warning($t('page.bi.sqlworkbench.messages.emptySql'));
    return;
  }
  if (!hasAuth('B_BI_SQL_EXPLAIN')) {
    window.$message?.error($t('page.bi.sqlworkbench.messages.noPermission'));
    return;
  }
  explainLoading.value = true;
  try {
    const { data, error } = await fetchBiSqlExplain({ datasourceId: ds, sql });
    if (error) {
      window.$message?.error(error.message || 'explain failed');
      explainResult.value = null;
      return;
    }
    explainResult.value = data ?? null;
  } finally {
    explainLoading.value = false;
  }
}

// ===== 结果表 =====
const resultColumns = computed<NaiveUI.TableColumn<Record<string, unknown>>[]>(() => {
  if (!result.value || !result.value.columns?.length) return [];
  return result.value.columns.map(col => ({
    key: col,
    title: col,
    minWidth: 120,
    ellipsis: { tooltip: true },
    render: row => {
      const v = (row as Record<string, unknown>)[col];
      if (v === null || v === undefined) return <span class="text-gray-400">NULL</span>;
      return String(v);
    }
  }));
});

const resultData = computed(() => {
  if (!result.value) return [];
  const cols = result.value.columns;
  return result.value.rows.map(row => {
    const obj: Record<string, unknown> = {};
    cols.forEach((c, i) => {
      obj[c] = row[i];
    });
    return obj;
  });
});

const explainColumns = computed<NaiveUI.TableColumn<Record<string, unknown>>[]>(() => {
  if (!explainResult.value || !explainResult.value.columns?.length) return [];
  return explainResult.value.columns.map(col => ({
    key: col,
    title: col,
    minWidth: 120,
    ellipsis: { tooltip: true },
    render: row => {
      const v = (row as Record<string, unknown>)[col];
      if (v === null || v === undefined) return '';
      return String(v);
    }
  }));
});

const explainData = computed(() => {
  if (!explainResult.value) return [];
  const cols = explainResult.value.columns;
  return explainResult.value.rows.map(row => {
    const obj: Record<string, unknown> = {};
    cols.forEach((c, i) => {
      obj[c] = row[i];
    });
    return obj;
  });
});

// ===== 历史 =====
const historyRecords = ref<Api.Bi.QueryExecutionRecord[]>([]);
const historyTotal = ref(0);
const historyCurrent = ref(1);
const historyPageSize = ref(10);
// 'all' = 不筛；其他值 = 同步给后端
const historyStatus = ref<Api.Bi.ExecutionStatus | 'all'>('all');

const historyStatusOptions = [
  { label: 'ALL', value: 'all' as const },
  { label: $t('page.bi.sqlworkbench.history.statusLabel.success'), value: 'success' as const },
  { label: $t('page.bi.sqlworkbench.history.statusLabel.failed'), value: 'failed' as const },
  { label: $t('page.bi.sqlworkbench.history.statusLabel.timeout'), value: 'timeout' as const },
  { label: $t('page.bi.sqlworkbench.history.statusLabel.denied'), value: 'denied' as const }
];

const historyColumns = computed<NaiveUI.TableColumn<Api.Bi.QueryExecutionRecord>[]>(() => [
  {
    key: 'createdAt',
    title: $t('page.bi.sqlworkbench.history.time'),
    width: 170,
    render: row => row.createdAt ?? '-'
  },
  {
    key: 'status',
    title: $t('page.bi.sqlworkbench.history.status'),
    width: 90,
    render: row => {
      const type =
        row.status === 'success'
          ? 'success'
          : row.status === 'denied'
            ? 'warning'
            : 'error';
      return <NTag type={type} size="small">{row.status}</NTag>;
    }
  },
  {
    key: 'rowCount',
    title: $t('page.bi.sqlworkbench.history.rowCount'),
    width: 80,
    render: row => row.rowCount ?? '-'
  },
  {
    key: 'costMs',
    title: $t('page.bi.sqlworkbench.history.cost'),
    width: 90,
    render: row => (row.costMs != null ? `${row.costMs} ms` : '-')
  },
  {
    key: 'sql',
    title: $t('page.bi.sqlworkbench.history.sql'),
    minWidth: 200,
    ellipsis: { tooltip: true },
    render: row => <span class="font-mono">{row.sql}</span>
  },
  {
    key: 'error',
    title: $t('page.bi.sqlworkbench.history.error'),
    minWidth: 200,
    ellipsis: { tooltip: true },
    render: row => row.error ?? '-'
  }
]);

async function loadHistory() {
  if (!hasAuth('B_BI_SQL_HISTORY')) return;
  historyLoading.value = true;
  try {
    const { data, error } = await fetchBiSqlHistory({
      current: historyCurrent.value,
      size: historyPageSize.value,
      datasourceId: datasourceId.value,
      status: historyStatus.value === 'all' ? null : historyStatus.value
    });
    if (error) {
      historyRecords.value = [];
      historyTotal.value = 0;
      return;
    }
    historyRecords.value = data?.records ?? [];
    historyTotal.value = data?.total ?? 0;
  } finally {
    historyLoading.value = false;
  }
}

watch([datasourceId, historyStatus], () => {
  historyCurrent.value = 1;
  loadHistory();
});

onMounted(() => {
  loadDatasources();
  loadHistory();
});

function handleHistoryPageChange(page: number) {
  historyCurrent.value = page;
  loadHistory();
}

function handleHistorySizeChange(size: number) {
  historyPageSize.value = size;
  historyCurrent.value = 1;
  loadHistory();
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-12px">
    <!-- 顶部：数据源 + 操作 -->
    <NCard :bordered="false" size="small" class="card-wrapper" :title="$t('page.bi.sqlworkbench.title')">
      <template #header-extra>
        <NSpace align="center">
          <span class="text-12px text-gray-500">{{ $t('page.bi.sqlworkbench.datasource') }}</span>
          <NSelect
            v-model:value="datasourceId"
            :options="dsOptions"
            :placeholder="$t('page.bi.sqlworkbench.chooseDatasource')"
            clearable
            filterable
            style="width: 280px"
          />
        </NSpace>
      </template>

      <div class="text-12px text-gray-500 mb-8px">{{ $t('page.bi.sqlworkbench.subtitle') }}</div>

      <NInput
        v-model:value="sqlInput"
        type="textarea"
        :placeholder="$t('page.bi.sqlworkbench.placeholder')"
        :autosize="{ minRows: 6, maxRows: 14 }"
        class="font-mono"
        spellcheck="false"
      />

      <NSpace align="center" class="mt-8px" :wrap="false">
        <NButton type="primary" :loading="running" :disabled="!datasourceId" @click="handleRun">
          {{ $t('page.bi.sqlworkbench.actions.run') }}
        </NButton>
        <NButton :loading="explainLoading" :disabled="!datasourceId" @click="handleExplain">
          {{ $t('page.bi.sqlworkbench.actions.explain') }}
        </NButton>
        <NButton @click="handleFormat">{{ $t('page.bi.sqlworkbench.actions.format') }}</NButton>
        <NPopconfirm @positive-click="handleClear">
          <template #trigger>
            <NButton>{{ $t('page.bi.sqlworkbench.actions.clear') }}</NButton>
          </template>
          确定清空编辑器？
        </NPopconfirm>
        <NButton @click="handleCopy">{{ $t('page.bi.sqlworkbench.actions.copy') }}</NButton>
        <NPopconfirm>
          <template #trigger>
            <NCheckbox v-model:checked="allowWrite" class="ml-12px" />
          </template>
          仅在确认有写权限时再勾选
        </NPopconfirm>
        <span class="text-12px text-gray-500">
          {{ $t('page.bi.sqlworkbench.allowWrite') }}
        </span>
      </NSpace>
    </NCard>

    <!-- 执行结果 -->
    <NCard :bordered="false" size="small" class="card-wrapper" :title="$t('page.bi.sqlworkbench.result.finalSql')">
      <template v-if="result" #header-extra>
        <NSpace align="center">
          <NTag type="info" size="small">
            {{
              $t('page.bi.sqlworkbench.result.rowCount', {
                count: result.rowCount,
                ms: result.costMs
              })
            }}
          </NTag>
          <NButton size="tiny" @click="handleCopyFinal">
            {{ $t('page.bi.sqlworkbench.actions.copyFinal') }}
          </NButton>
        </NSpace>
      </template>

      <NSpin :show="running">
        <NAlert
          v-if="executeError"
          :title="executeDenied ? $t('page.bi.sqlworkbench.history.deniedHint') : 'Error'"
          :type="executeDenied ? 'warning' : 'error'"
          class="mb-12px"
        >
          {{ executeError }}
        </NAlert>

        <div v-if="!result && !executeError" class="text-12px text-gray-500">
          {{ $t('page.bi.sqlworkbench.result.empty') }}
        </div>

        <template v-else-if="result">
          <div v-if="result.maskedColumns?.length" class="mb-8px">
            <NTag type="warning" size="small">
              {{
                $t('page.bi.sqlworkbench.result.masked', {
                  cols: result.maskedColumns.join(', ')
                })
              }}
            </NTag>
          </div>

          <div class="mb-12px">
            <div class="text-12px text-gray-500 mb-4px">SQL</div>
            <pre class="font-mono text-12px bg-gray-50 p-8px rounded overflow-auto">{{ result.finalSql }}</pre>
          </div>

          <NDataTable
            v-if="result.columns?.length"
            :columns="resultColumns"
            :data="resultData"
            :scroll-x="Math.max(800, result.columns.length * 140)"
            :max-height="420"
            :pagination="{ pageSize: 50 }"
            size="small"
            striped
          />
          <NEmpty v-else :description="$t('page.bi.sqlworkbench.result.empty')" />
        </template>
      </NSpin>
    </NCard>

    <!-- EXPLAIN -->
    <NCard :bordered="false" size="small" class="card-wrapper" :title="$t('page.bi.sqlworkbench.explain.title')">
      <template v-if="explainResult" #header-extra>
        <NTag type="info" size="small">
          {{ $t('page.bi.sqlworkbench.explain.cost', { ms: explainResult.costMs }) }}
        </NTag>
      </template>

      <NSpin :show="explainLoading">
        <NEmpty v-if="!explainResult" :description="$t('page.bi.sqlworkbench.explain.empty')" />
        <template v-else>
          <div class="mb-12px">
            <div class="text-12px text-gray-500 mb-4px">
              {{ $t('page.bi.sqlworkbench.explain.rawSql') }}
            </div>
            <pre class="font-mono text-12px bg-gray-50 p-8px rounded overflow-auto">{{ explainResult.rawSql }}</pre>
          </div>
          <NDataTable
            :columns="explainColumns"
            :data="explainData"
            :scroll-x="Math.max(600, explainResult.columns.length * 140)"
            :max-height="320"
            size="small"
            striped
          />
        </template>
      </NSpin>
    </NCard>

    <!-- 历史 -->
    <NCard :bordered="false" size="small" class="card-wrapper" :title="$t('page.bi.sqlworkbench.history.title')">
      <template #header-extra>
        <NSpace>
          <NSelect v-model:value="historyStatus" :options="historyStatusOptions" style="width: 160px" />
          <NButton @click="loadHistory">{{ $t('page.bi.sqlworkbench.history.refresh') }}</NButton>
        </NSpace>
      </template>

      <NSpin :show="historyLoading">
        <NEmpty
          v-if="!historyLoading && historyRecords.length === 0"
          :description="$t('page.bi.sqlworkbench.history.empty')"
        />
        <NDataTable
          v-else
          :columns="historyColumns"
          :data="historyRecords"
          :scroll-x="1000"
          :pagination="{
            page: historyCurrent,
            pageSize: historyPageSize,
            itemCount: historyTotal,
            showSizePicker: true,
            pageSizes: [10, 20, 50],
            onUpdatePage: handleHistoryPageChange,
            onUpdatePageSize: handleHistorySizeChange
          }"
          :row-key="row => row.id"
          size="small"
        />
      </NSpin>
    </NCard>
  </div>
</template>

<style scoped>
.font-mono {
  font-family: 'JetBrains Mono', 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace;
}
</style>
