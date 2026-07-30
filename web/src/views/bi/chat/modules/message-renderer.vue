<script setup lang="ts">
import { defineComponent, h, nextTick, reactive, ref, watch, type PropType } from 'vue';
import { NButton, NCode, NDataTable, NEmpty, NSelect, NSpin, NTabPane, NTabs, NTag, NTooltip } from 'naive-ui';
import { Marked } from 'marked';
import DOMPurify from 'dompurify';
import { useEcharts, type ECOption } from '@/hooks/common/echarts';
import { $t } from '@/locales';

defineOptions({ name: 'BiChatMessageRenderer' });

// ---- Markdown 渲染（LLM 返回的解读文本）----
const marked = new Marked({
  gfm: true,
  breaks: true
});

function renderMarkdown(md: string): string {
  if (!md) return '';
  const raw = marked.parse(md, { async: false }) as string;
  return DOMPurify.sanitize(raw);
}

type ChatMessage = Api.Bi.BiChatMessage & { chartType?: string };

interface Props {
  messages: ChatMessage[];
  streaming: boolean;
  hasSession: boolean;
}

const props = defineProps<Props>();

// ---- 内联图表组件（每条 assistant 消息独立实例，复用 useEcharts hook）----
const MessageChart = defineComponent({
  name: 'BiChatMessageChart',
  props: {
    option: { type: Object as PropType<ECOption>, default: () => ({}) as ECOption }
  },
  setup(p, { expose }) {
    const { domRef, chart, updateOptions } = useEcharts<ECOption>(() => ({}) as ECOption);
    watch(
      () => p.option,
      opt => {
        if (opt && Object.keys(opt).length > 0) {
          updateOptions(() => opt);
        }
      },
      { immediate: true, deep: true }
    );
    function savePng(filename: string) {
      const inst = chart.value;
      if (!inst) return;
      const url = inst.getDataURL({ pixelRatio: 2, backgroundColor: '#fff' });
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
    }
    expose({ savePng });
    return () => h('div', { ref: domRef, class: 'h-360px w-full' });
  }
});

// ---- 自动滚动到底部 ----
const scrollRef = ref<HTMLElement>();
watch(
  () => props.messages.length,
  async () => {
    await nextTick();
    if (scrollRef.value) {
      scrollRef.value.scrollTop = scrollRef.value.scrollHeight;
    }
  }
);
// 流式过程中持续贴底（content / steps 增量更新）
watch(
  () => props.messages.map(m => `${m.id}:${m.content?.length ?? 0}:${m.agentStepsJson?.length ?? 0}`).join('|'),
  async () => {
    await nextTick();
    if (scrollRef.value) {
      scrollRef.value.scrollTop = scrollRef.value.scrollHeight;
    }
  }
);

// ---- 图表类型选择（每条消息独立）----
const chartTypeMap = reactive<Record<string, string>>({});
const chartRefs = new Map<string, any>();

const chartTypeOptions = [
  { label: $t('page.bi.metrics.chartTypes.bar'), value: 'bar' },
  { label: $t('page.bi.metrics.chartTypes.line'), value: 'line' },
  { label: $t('page.bi.metrics.chartTypes.pie'), value: 'pie' }
];

function getChartTabType(msg: ChatMessage): string {
  const override = chartTypeMap[msg.id];
  if (override && override !== 'table') return override;
  const t = msg.chartType;
  if (t === 'bar' || t === 'line' || t === 'pie') return t;
  return 'bar';
}

function setChartType(msg: ChatMessage, type: string) {
  chartTypeMap[msg.id] = type;
}

function setChartRef(id: string, el: any) {
  if (el) chartRefs.set(id, el);
  else chartRefs.delete(id);
}

// ---- 图表 option 构建 ----
function isNumeric(v: any): boolean {
  if (typeof v === 'number') return !Number.isNaN(v);
  if (typeof v === 'string' && v !== '') return !Number.isNaN(Number(v));
  return false;
}

function hasNumericData(result: Api.Bi.ChatSqlResult): boolean {
  const cols = result.columns || [];
  const rows = result.rows || [];
  return cols.slice(1).some(c => rows.some(r => isNumeric(r[c])));
}

function buildChartOption(result: Api.Bi.ChatSqlResult, chartType: string): ECOption {
  const cols = result.columns || [];
  const rows = result.rows || [];
  if (!cols.length || !rows.length) return {} as ECOption;

  if (chartType === 'pie') {
    const nameCol = cols[0];
    const valueCol = cols.slice(1).find(c => rows.some(r => isNumeric(r[c]))) || cols[1];
    if (!valueCol) return {} as ECOption;
    return {
      tooltip: { trigger: 'item' },
      legend: { orient: 'vertical', left: 'left' },
      series: [
        {
          type: 'pie',
          radius: '60%',
          data: rows.map(r => ({ name: String(r[nameCol] ?? ''), value: Number(r[valueCol]) || 0 }))
        }
      ]
    } as ECOption;
  }

  // bar / line
  const xCol = cols[0];
  const yCols = cols.slice(1).filter(c => rows.some(r => isNumeric(r[c])));
  if (!yCols.length) return {} as ECOption;
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: yCols, top: 0 },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true, top: '15%' },
    xAxis: { type: 'category', data: rows.map(r => String(r[xCol] ?? '')) },
    yAxis: { type: 'value' },
    series: yCols.map(c => ({
      name: c,
      type: chartType as 'bar' | 'line',
      data: rows.map(r => Number(r[c]) || 0)
    }))
  } as ECOption;
}

function getChartOption(msg: ChatMessage): ECOption {
  if (!msg.sqlResult) return {} as ECOption;
  return buildChartOption(msg.sqlResult, getChartTabType(msg));
}

// ---- 表格列构建 ----
function buildTableColumns(result: Api.Bi.ChatSqlResult) {
  return (result.columns || []).map(col => ({
    key: col,
    title: col,
    dataIndex: col,
    ellipsis: { tooltip: true }
  }));
}

// 稳定行 key：每行对象分配唯一 key（SQL 结果通常无 id 列）
let rowKeyCounter = 0;
const rowKeyWeakMap = new WeakMap<object, string>();
function rowKey(row: object): string {
  let k = rowKeyWeakMap.get(row);
  if (k === undefined) {
    rowKeyCounter += 1;
    k = `r-${rowKeyCounter}`;
    rowKeyWeakMap.set(row, k);
  }
  return k;
}

// ---- Agent 步骤 ----
const STEP_ORDER = ['intent', 'sql_gen', 'sql_validate', 'executor', 'explain'];

function getSteps(msg: ChatMessage): Array<{ node: string; status: string; elapsedMs: number }> {
  if (!msg.agentStepsJson) return [];
  const map = new Map<string, { node: string; status: string; elapsedMs: number }>();
  for (const s of msg.agentStepsJson as any[]) {
    if (s && s.node) {
      map.set(s.node, { node: s.node, status: s.status, elapsedMs: s.elapsedMs });
    }
  }
  return [...map.values()].sort((a, b) => STEP_ORDER.indexOf(a.node) - STEP_ORDER.indexOf(b.node));
}

function stepTagType(status: string): 'default' | 'success' | 'info' | 'warning' | 'error' {
  if (status === 'success') return 'success';
  if (status === 'failed') return 'error';
  if (status === 'running') return 'info';
  if (status === 'skipped') return 'default';
  return 'default';
}

const STEP_NODE_LABELS: Record<string, App.I18n.I18nKey> = {
  intent: 'page.bi.chat.steps.intent',
  sql_gen: 'page.bi.chat.steps.sql_gen',
  sql_validate: 'page.bi.chat.steps.sql_validate',
  executor: 'page.bi.chat.steps.executor',
  explain: 'page.bi.chat.steps.explain'
};

const STEP_STATUS_LABELS: Record<string, App.I18n.I18nKey> = {
  running: 'page.bi.chat.steps.running',
  success: 'page.bi.chat.steps.success',
  failed: 'page.bi.chat.steps.failed',
  skipped: 'page.bi.chat.steps.skipped'
};

function stepLabel(node: string): string {
  const key = STEP_NODE_LABELS[node];
  return key ? $t(key) : node;
}

function stepStatusLabel(status: string): string {
  const key = STEP_STATUS_LABELS[status];
  return key ? $t(key) : status;
}

function isLastMessage(index: number): boolean {
  return index === props.messages.length - 1;
}

// ---- 导出 / 复制 ----
function exportCsv(msg: ChatMessage) {
  const result = msg.sqlResult;
  if (!result?.rows?.length) return;
  const bom = '\uFEFF';
  const cols = result.columns || [];
  const header = cols.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',');
  const body = result.rows
    .map(row => cols.map(c => `"${String(row[c] ?? '').replace(/"/g, '""')}"`).join(','))
    .join('\n');
  const csv = bom + header + '\n' + body;
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `bi-result-${msg.id}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function exportPng(msg: ChatMessage) {
  const inst = chartRefs.get(msg.id);
  if (!inst) {
    window.$message?.warning($t('page.bi.chat.exportPng'));
    return;
  }
  inst.savePng?.(`bi-chart-${msg.id}.png`);
}

async function copySql(sql: string) {
  try {
    await navigator.clipboard.writeText(sql);
    window.$message?.success($t('page.bi.chat.copySuccess'));
  } catch {
    window.$message?.error($t('common.error'));
  }
}
</script>

<template>
  <div ref="scrollRef" class="message-renderer flex-1 overflow-y-auto px-20px py-16px">
    <!-- 空状态 -->
    <NEmpty
      v-if="messages.length === 0"
      :description="hasSession ? $t('page.bi.chat.emptyMessages') : $t('page.bi.chat.emptySession')"
      class="py-80px"
    />

    <div v-else class="flex flex-col gap-16px max-w-1200px mx-auto">
      <template v-for="(msg, index) in messages" :key="msg.id">
        <!-- 系统消息：居中 -->
        <div v-if="msg.role === 'system'" class="text-center text-12px opacity-50">
          {{ msg.content }}
        </div>

        <!-- 用户消息：右对齐气泡 -->
        <div v-else-if="msg.role === 'user'" class="flex justify-end">
          <div
            class="user-bubble max-w-70% rounded-10px px-14px py-10px bg-primary-500 text-white whitespace-pre-wrap break-words"
          >
            {{ msg.content }}
          </div>
        </div>

        <!-- assistant 消息：左对齐卡片 -->
        <div v-else class="flex flex-col gap-8px">
          <div class="flex items-center gap-8px">
            <span class="text-13px font-500 opacity-70">{{ $t('page.bi.chat.roles.assistant') }}</span>
            <NTag v-if="msg.status === 'failed'" size="small" type="error">
              {{ $t('page.bi.chat.messageStatus.failed') }}
            </NTag>
            <span v-if="msg.executionTimeMs > 0" class="text-12px opacity-50">{{ msg.executionTimeMs }}ms</span>
          </div>

          <div
            class="assistant-card rounded-10px border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-16px py-12px flex flex-col gap-12px"
          >
            <!-- Agent 流水线步骤 -->
            <div v-if="getSteps(msg).length > 0" class="flex flex-wrap items-center gap-6px">
              <NTag v-for="step in getSteps(msg)" :key="step.node" size="small" :type="stepTagType(step.status)" round>
                <span class="flex items-center gap-4px">
                  <span>{{ stepLabel(step.node) }}</span>
                  <span class="opacity-70">·</span>
                  <span>{{ stepStatusLabel(step.status) }}</span>
                  <span v-if="step.elapsedMs > 0" class="opacity-50 text-11px">{{ step.elapsedMs }}ms</span>
                </span>
              </NTag>
            </div>

            <!-- 思考中指示器（流式中且无内容无步骤） -->
            <div
              v-else-if="streaming && isLastMessage(index) && !msg.content"
              class="flex items-center gap-8px text-13px opacity-60"
            >
              <NSpin size="small" />
              <span>{{ $t('page.bi.chat.steps.running') }}...</span>
            </div>

            <!-- SQL 代码块 -->
            <div
              v-if="msg.sqlText"
              class="sql-block rounded-6px overflow-hidden border border-gray-200 dark:border-gray-700"
            >
              <div class="flex items-center justify-between px-10px py-6px bg-gray-50 dark:bg-gray-900">
                <span class="text-12px font-500 opacity-70">SQL</span>
                <NTooltip trigger="hover">
                  <template #trigger>
                    <NButton size="tiny" quaternary @click="copySql(msg.sqlText!)">
                      <template #icon><icon-ic-round-content-copy class="text-icon" /></template>
                    </NButton>
                  </template>
                  {{ $t('page.bi.chat.copySql') }}
                </NTooltip>
              </div>
              <NCode :code="msg.sqlText" language="sql" word-wrap />
            </div>

            <!-- 执行结果 -->
            <div v-if="msg.sqlResult && msg.sqlResult.rows" class="result-block">
              <div class="flex items-center justify-between mb-8px">
                <span class="text-12px opacity-60">
                  {{ msg.sqlResult.rowCount }} {{ $t('page.bi.sql-workbench.rows') }} ·
                  {{ $t('page.bi.sql-workbench.elapsed') }}: {{ msg.sqlResult.elapsedMs }}ms
                </span>
                <NButton size="tiny" ghost @click="exportCsv(msg)">
                  <template #icon><icon-ic-round-download class="text-icon" /></template>
                  {{ $t('page.bi.chat.exportCsv') }}
                </NButton>
              </div>
              <NTabs type="line" size="small" animated>
                <NTabPane name="table" :tab="$t('page.bi.metrics.chartTypes.table')">
                  <NDataTable
                    :columns="buildTableColumns(msg.sqlResult)"
                    :data="msg.sqlResult.rows"
                    size="small"
                    :scroll-x="600"
                    :max-height="360"
                    :row-key="rowKey"
                  />
                </NTabPane>
                <NTabPane name="chart" tab="图表">
                  <div class="flex items-center justify-between mb-8px">
                    <NSelect
                      :value="getChartTabType(msg)"
                      :options="chartTypeOptions"
                      size="small"
                      class="w-160px"
                      @update:value="(v: string) => setChartType(msg, v)"
                    />
                    <NButton size="tiny" ghost @click="exportPng(msg)">
                      <template #icon><icon-ic-round-download class="text-icon" /></template>
                      {{ $t('page.bi.chat.exportPng') }}
                    </NButton>
                  </div>
                  <MessageChart
                    v-if="hasNumericData(msg.sqlResult)"
                    :ref="(el: any) => setChartRef(msg.id, el)"
                    :option="getChartOption(msg)"
                  />
                  <NEmpty v-else :description="$t('common.noData')" class="py-40px" />
                </NTabPane>
              </NTabs>
            </div>

            <!-- 中文解读（Markdown 渲染）-->
            <div
              v-if="msg.content"
              class="markdown-body text-14px break-words leading-relaxed"
              v-html="renderMarkdown(msg.content)"
            />
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.message-renderer {
  min-height: 0;
}
.user-bubble {
  word-break: break-word;
}

/* Markdown 渲染样式（LLM 解读文本）*/
.markdown-body {
  font-size: 14px;
  line-height: 1.7;
}
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  margin: 12px 0 6px;
  font-weight: 600;
  line-height: 1.4;
}
.markdown-body :deep(h1) {
  font-size: 18px;
}
.markdown-body :deep(h2) {
  font-size: 16px;
}
.markdown-body :deep(h3) {
  font-size: 15px;
}
.markdown-body :deep(p) {
  margin: 6px 0;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 6px 0;
  padding-left: 24px;
}
.markdown-body :deep(li) {
  margin: 2px 0;
}
.markdown-body :deep(code) {
  padding: 2px 6px;
  font-size: 13px;
  font-family: var(--font-family-mono, monospace);
  background-color: rgba(128, 128, 128, 0.15);
  border-radius: 4px;
}
.markdown-body :deep(pre) {
  margin: 8px 0;
  padding: 12px;
  overflow-x: auto;
  background-color: rgba(128, 128, 128, 0.12);
  border-radius: 6px;
}
.markdown-body :deep(pre code) {
  padding: 0;
  background: transparent;
}
.markdown-body :deep(blockquote) {
  margin: 8px 0;
  padding: 4px 12px;
  border-left: 3px solid rgba(128, 128, 128, 0.4);
  color: inherit;
  opacity: 0.85;
}
.markdown-body :deep(table) {
  margin: 8px 0;
  border-collapse: collapse;
  width: 100%;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 6px 10px;
  border: 1px solid rgba(128, 128, 128, 0.3);
  text-align: left;
}
.markdown-body :deep(th) {
  background-color: rgba(128, 128, 128, 0.1);
  font-weight: 600;
}
.markdown-body :deep(a) {
  color: var(--primary-color, #2080f0);
  text-decoration: none;
}
.markdown-body :deep(a:hover) {
  text-decoration: underline;
}
.markdown-body :deep(hr) {
  margin: 12px 0;
  border: none;
  border-top: 1px solid rgba(128, 128, 128, 0.3);
}
</style>
