<script setup lang="tsx">
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useClipboard } from '@vueuse/core';
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NEmpty,
  NInput,
  NPopconfirm,
  NSelect,
  NSpace,
  NSpin,
  NTag
} from 'naive-ui';
import { useEcharts } from '@/hooks/common/echarts';
import type { ECOption } from '@/hooks/common/echarts';
import {
  fetchBiChatCreate,
  fetchBiChatDelete,
  fetchBiChatDetail,
  fetchBiChatList,
  fetchBiDatasourceList,
  openBiChatSend
} from '@/service/api';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';

const { hasAuth } = useAuth();

// ===== 数据源 =====
const dsOptions = ref<{ label: string; value: string }[]>([]);
const currentDsId = ref<string | null>(null);

async function loadDatasources() {
  const { data } = await fetchBiDatasourceList({ current: 1, size: 200, name: null, type: null });
  const records = data?.records ?? [];
  records.sort((a, b) => Number(b.isDefault) - Number(a.isDefault));
  dsOptions.value = records.map(d => ({
    label: `${d.name} (${d.type})${d.isDefault ? ' · 默认' : ''}`,
    value: d.id
  }));
  if (!currentDsId.value && dsOptions.value.length) {
    currentDsId.value = dsOptions.value[0].value;
  }
}

// ===== 会话列表 =====
const sessions = ref<Api.Bi.ChatSession[]>([]);
const sessionsLoading = ref(false);
const currentSession = ref<Api.Bi.ChatSession | null>(null);
const messages = ref<Api.Bi.ChatMessage[]>([]);
const messagesLoading = ref(false);

async function loadSessions() {
  if (!hasAuth('B_BI_CHAT_NEW')) return;
  sessionsLoading.value = true;
  try {
    const { data, error } = await fetchBiChatList({ current: 1, size: 50 });
    if (error) return;
    sessions.value = data?.records ?? [];
    if (!currentSession.value && sessions.value.length) {
      await openSession(sessions.value[0]);
    }
  } finally {
    sessionsLoading.value = false;
  }
}

async function openSession(s: Api.Bi.ChatSession) {
  currentSession.value = s;
  if (s.datasourceId) currentDsId.value = s.datasourceId;
  messagesLoading.value = true;
  try {
    const { data, error } = await fetchBiChatDetail(s.id);
    if (error) {
      messages.value = [];
      return;
    }
    messages.value = data?.messages ?? [];
    scrollToBottom();
  } finally {
    messagesLoading.value = false;
  }
}

async function handleNewSession() {
  if (!hasAuth('B_BI_CHAT_NEW')) {
    window.$message?.warning('当前角色没有「新建对话」权限');
    return;
  }
  const { data, error } = await fetchBiChatCreate({
    title: '新会话',
    datasourceId: currentDsId.value
  });
  if (error || !data) {
    window.$message?.error(error?.message || '创建失败');
    return;
  }
  await loadSessions();
  await openSession(data);
}

async function handleDeleteSession(s: Api.Bi.ChatSession) {
  const { error } = await fetchBiChatDelete(s.id);
  if (error) return;
  window.$message?.success('已删除');
  if (currentSession.value?.id === s.id) {
    currentSession.value = null;
    messages.value = [];
  }
  await loadSessions();
}

// ===== 输入 / 发送 =====
const questionInput = ref('');
const sending = ref(false);
const currentStream = ref<{
  steps: Api.Bi.ChatAgentStep[];
  columns: string[];
  rows: (string | number | boolean | null)[][];
  finalSql: string;
  error: string | null;
  explanation: string;
  rowCount: number;
  costMs: number;
  tokensUsed: number;
  intent: string | null;
} | null>(null);
let es: { close: () => void } | null = null;

function handleStop() {
  es?.close();
  es = null;
  sending.value = false;
  if (currentStream.value) currentStream.value.steps = [...currentStream.value.steps];
}

async function handleSend() {
  const q = questionInput.value.trim();
  if (!q) return;
  if (!currentSession.value) {
    await handleNewSession();
    if (!currentSession.value) return;
  }
  const ds = currentDsId.value || currentSession.value?.datasourceId;
  if (!ds) {
    window.$message?.warning($t('page.bi.chat.chooseDatasource'));
    return;
  }
  if (!hasAuth('B_BI_CHAT_SEND')) {
    window.$message?.warning('当前角色没有「发送问题」权限');
    return;
  }
  // 乐观插入 user message
  const userMsg: Api.Bi.ChatMessage = {
    id: `tmp-${Date.now()}`,
    sessionId: currentSession.value!.id,
    role: 'user',
    content: q,
    thinking: null,
    sql: null,
    error: null,
    costMs: null,
    tokensUsed: null,
    agentSteps: [],
    createdAt: new Date().toISOString()
  };
  messages.value = [...messages.value, userMsg];
  questionInput.value = '';
  scrollToBottom();

  const session = currentSession.value;
  sending.value = true;
  currentStream.value = {
    steps: [],
    columns: [],
    rows: [],
    finalSql: '',
    error: null,
    explanation: '',
    rowCount: 0,
    costMs: 0,
    tokensUsed: 0,
    intent: null
  };

  es = openBiChatSend(session!.id, { question: q, datasourceId: ds }, {
    onStep: step => {
      if (!currentStream.value) return;
      const list = currentStream.value.steps;
      const idx = list.findIndex(s => s.node === step.node);
      const merged: Api.Bi.ChatAgentStep = {
        node: step.node,
        durationMs: Number(step.durationMs ?? 0),
        input: (step as { input?: Record<string, unknown> }).input,
        output: (step as { output?: Record<string, unknown> }).output,
        error: (step as { error?: string | null }).error ?? null
      };
      if (idx >= 0) list[idx] = merged;
      else list.push(merged);
      // 摘取 intent / draftSql
      const s = step as { intent?: string; draftSql?: string; finalSql?: string; rowCount?: number };
      if (s.intent) currentStream.value.intent = s.intent;
      if (s.draftSql && !currentStream.value.finalSql) currentStream.value.finalSql = s.draftSql;
      if (s.finalSql) currentStream.value.finalSql = s.finalSql;
      if (typeof s.rowCount === 'number') currentStream.value.rowCount = s.rowCount;
      currentStream.value = { ...currentStream.value, steps: [...list] };
    },
    onFinal: fdata => {
      const data = fdata as {
        finalSql: string;
        explanation: string;
        error: string | null;
        columns: string[];
        rows: (string | number | boolean | null)[][];
        rowCount: number;
        costMs: number;
        tokensUsed: number;
        steps: Api.Bi.ChatAgentStep[];
        intent: string | null;
      };
      currentStream.value = {
        steps: data.steps || [],
        columns: data.columns || [],
        rows: data.rows || [],
        finalSql: data.finalSql || '',
        error: data.error || null,
        explanation: data.explanation || '',
        rowCount: data.rowCount || 0,
        costMs: data.costMs || 0,
        tokensUsed: data.tokensUsed || 0,
        intent: data.intent || null
      };
      // 落库 assistant 消息已由后端完成，刷新一次以拉真实 id
      if (session) {
        fetchBiChatDetail(session.id).then(({ data: detail }) => {
          if (detail) messages.value = detail.messages ?? [];
          scrollToBottom();
        });
      }
    },
    onError: msg => {
      if (currentStream.value) currentStream.value.error = msg;
    },
    onDone: () => {
      sending.value = false;
      es = null;
      loadSessions(); // 更新 last_message_at
    }
  });
}

// ===== 消息渲染 =====
const messageListRef = ref<HTMLElement | null>(null);

function scrollToBottom() {
  nextTick(() => {
    const el = messageListRef.value;
    if (el) el.scrollTop = el.scrollHeight;
  });
}

// ===== 结果表 / 图表 =====
const resultView = ref<'table' | 'chart'>('table');

const lastAssistantContent = computed<Api.Bi.ChatMessage | null>(() => {
  for (let i = messages.value.length - 1; i >= 0; i -= 1) {
    if (messages.value[i].role === 'assistant') return messages.value[i];
  }
  return null;
});

const finalResult = computed(() => {
  // 流式结果优先；落库后的历史消息只有 SQL/错误，没有 rows（不重复展示）
  if (currentStream.value) {
    return {
      columns: currentStream.value.columns,
      rows: currentStream.value.rows,
      rowCount: currentStream.value.rowCount,
      costMs: currentStream.value.costMs,
      tokensUsed: currentStream.value.tokensUsed,
      finalSql: currentStream.value.finalSql,
      steps: currentStream.value.steps,
      error: currentStream.value.error,
      intent: currentStream.value.intent,
      explanation: currentStream.value.explanation
    };
  }
  const m = lastAssistantContent.value;
  if (m && (m.sql || m.error)) {
    return {
      columns: [] as string[],
      rows: [] as (string | number | boolean | null)[][],
      rowCount: 0,
      costMs: m.costMs || 0,
      tokensUsed: m.tokensUsed || 0,
      finalSql: m.sql || '',
      steps: m.agentSteps || [],
      error: m.error,
      intent: null as string | null,
      explanation: m.content
    };
  }
  return null;
});

const resultColumns = computed<NaiveUI.TableColumn<Record<string, unknown>>[]>(() => {
  const r = finalResult.value;
  if (!r || !r.columns?.length) return [];
  return r.columns.map(col => ({
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
  const r = finalResult.value;
  if (!r) return [];
  const cols = r.columns;
  return r.rows.map(row => {
    const obj: Record<string, unknown> = {};
    cols.forEach((c, i) => {
      obj[c] = row[i];
    });
    return obj;
  });
});

// 图表自动选择类型
const chartKind = computed<'bar' | 'line' | 'pie'>(() => {
  const r = finalResult.value;
  if (!r || r.columns.length < 2) return 'bar';
  for (const row of r.rows.slice(0, 5)) {
    const v = row[r.columns.length - 1];
    if (typeof v !== 'number') return 'bar';
  }
  if (r.rows.length <= 8 && r.columns.length === 2) return 'pie';
  return 'bar';
});

const chartOptions = computed(() => {
  const r = finalResult.value;
  if (!r || r.columns.length < 2) return {};
  const val = r.columns[r.columns.length - 1];
  if (chartKind.value === 'pie') {
    return {
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      series: [
        {
          name: val,
          type: 'pie',
          radius: ['35%', '60%'],
          data: r.rows.map(row => ({ name: String(row[0] ?? ''), value: Number(row[r.columns.length - 1] ?? 0) }))
        }
      ]
    };
  }
  return {
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0 },
    grid: { left: 50, right: 30, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: r.rows.map(row => String(row[0] ?? '')) },
    yAxis: { type: 'value' },
    series: [{ name: val, type: chartKind.value, data: r.rows.map(row => Number(row[r.columns.length - 1] ?? 0)) }]
  };
});

const { domRef: chartRef, updateOptions: updateChart } = useEcharts(() => chartOptions.value as ECOption, {
  onRender() {}
});

watch(
  () => [chartOptions.value, resultView.value] as const,
  () => {
    if (resultView.value === 'chart') updateChart(() => chartOptions.value as ECOption);
  },
  { deep: true }
);

const { copy: copyToClipboard } = useClipboard();
function handleCopy(text: string) {
  copyToClipboard(text);
  window.$message?.success('已复制');
}

function stepNodeLabel(node: string) {
  const map: Record<string, string> = {
    intent: $t('page.bi.chat.steps.intent'),
    sql_gen: $t('page.bi.chat.steps.sql_gen'),
    validate: $t('page.bi.chat.steps.validate'),
    executor: $t('page.bi.chat.steps.executor'),
    explain: $t('page.bi.chat.steps.explain')
  };
  return map[node] || node;
}

function stepStatusType(node: string): 'success' | 'warning' | 'error' | 'default' {
  const step = currentStream.value?.steps.find(s => s.node === node);
  if (!step) return 'default';
  if (step.error) return 'error';
  return 'success';
}

const STEP_NODES = ['intent', 'sql_gen', 'validate', 'executor', 'explain'] as const;

// ===== 初始化 =====
onMounted(() => {
  loadDatasources();
  loadSessions();
});

// 会话切换时滚动到底
watch(currentSession, () => scrollToBottom());
</script>

<template>
  <div class="bi-chat-layout">
    <!-- 左侧：会话列表 -->
    <NCard :bordered="false" size="small" class="bi-chat-sidebar">
      <template #header>
        <NSpace align="center" :wrap="false" :size="6">
          <span class="text-14px font-medium">{{ $t('page.bi.chat.sessionList') }}</span>
          <NButton v-if="hasAuth('B_BI_CHAT_NEW')" size="tiny" type="primary" @click="handleNewSession">
            + {{ $t('page.bi.chat.newSession') }}
          </NButton>
        </NSpace>
      </template>

      <NEmpty v-if="!sessionsLoading && sessions.length === 0" :description="$t('page.bi.chat.emptySession')" />
      <NScrollbar v-else style="max-height: calc(100vh - 220px)">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="bi-chat-session-item"
          :class="{ active: currentSession?.id === s.id }"
          @click="openSession(s)"
        >
          <div class="bi-chat-session-title text-13px">
            {{ s.title || $t('page.bi.chat.sessionTitle', { id: s.id }) }}
          </div>
          <div class="bi-chat-session-meta text-11px text-gray-500">
            {{ s.lastMessageAt || s.createdAt || '-' }}
          </div>
          <NPopconfirm @positive-click="handleDeleteSession(s)">
            <template #trigger>
              <NButton size="tiny" type="error" ghost class="bi-chat-session-del" @click.stop>
                {{ $t('common.delete') }}
              </NButton>
            </template>
            {{ $t('common.confirmDelete') }}
          </NPopconfirm>
        </div>
      </NScrollbar>
    </NCard>

    <!-- 右侧：对话主区 -->
    <NCard :bordered="false" size="small" class="bi-chat-main">
      <template #header>
        <NSpace align="center" :wrap="false" :size="12">
          <span class="text-14px font-medium">
            {{ currentSession?.title || $t('page.bi.chat.title') }}
          </span>
          <span class="text-12px text-gray-500">{{ $t('page.bi.chat.subtitle') }}</span>
        </NSpace>
      </template>

      <template #header-extra>
        <NSpace align="center" :size="8">
          <span class="text-12px text-gray-500">{{ $t('page.bi.chat.datasource') }}</span>
          <NSelect
            v-model:value="currentDsId"
            :options="dsOptions"
            :placeholder="$t('page.bi.chat.chooseDatasource')"
            style="width: 240px"
            filterable
            clearable
          />
        </NSpace>
      </template>

      <!-- 消息列表 -->
      <div ref="messageListRef" class="bi-chat-messages">
        <NSpin :show="messagesLoading">
          <NEmpty
            v-if="!messagesLoading && messages.length === 0 && !sending"
            :description="$t('page.bi.chat.emptySession')"
            class="mt-48px"
          />
          <template v-else>
            <div v-for="m in messages" :key="m.id" class="bi-chat-msg" :class="['bi-chat-msg-' + m.role]">
              <div class="bi-chat-bubble">
                <div v-if="m.role === 'user'" class="bi-chat-text">{{ m.content }}</div>

                <template v-else>
                  <!-- 思维链 / agent 步骤 -->
                  <div v-if="m.role === 'assistant' && m.agentSteps?.length" class="bi-chat-steps">
                    <NSpace :size="4" :wrap="true">
                      <NTag
                        v-for="st in m.agentSteps"
                        :key="st.node"
                        size="small"
                        :type="st.error ? 'error' : 'success'"
                        round
                      >
                        {{ stepNodeLabel(st.node) }}
                        <span v-if="st.durationMs" class="ml-4px text-10px">{{ st.durationMs }}ms</span>
                      </NTag>
                    </NSpace>
                  </div>
                  <div class="bi-chat-text">{{ m.content }}</div>
                  <NAlert v-if="m.error" type="error" :title="$t('page.bi.chat.error')" class="mt-6px">
                    {{ m.error }}
                  </NAlert>
                  <div v-if="m.sql" class="bi-chat-sql">
                    <div class="bi-chat-sql-label">
                      <span>{{ $t('page.bi.chat.finalSql') }}</span>
                      <NButton text size="tiny" @click="handleCopy(m.sql!)">{{ $t('common.copy') }}</NButton>
                    </div>
                    <pre class="font-mono text-12px">{{ m.sql }}</pre>
                  </div>
                </template>
              </div>
            </div>

            <!-- 流式中：展示正在跑的步骤 + 结果 -->
            <div v-if="sending || currentStream" class="bi-chat-msg bi-chat-msg-assistant">
              <div class="bi-chat-bubble">
                <div class="bi-chat-steps">
                  <NSpace :size="4" :wrap="true">
                    <NTag v-for="node in STEP_NODES" :key="node" size="small" :type="stepStatusType(node)" round>
                      {{ stepNodeLabel(node) }}
                      <span v-if="currentStream?.steps.find(s => s.node === node)?.durationMs" class="ml-4px text-10px">
                        {{ currentStream?.steps.find(s => s.node === node)?.durationMs }}ms
                      </span>
                    </NTag>
                  </NSpace>
                </div>

                <div v-if="currentStream?.error" class="mt-8px">
                  <NAlert type="error" :title="$t('page.bi.chat.error')">
                    {{ currentStream.error }}
                  </NAlert>
                </div>

                <div v-if="currentStream?.explanation" class="bi-chat-text mt-6px">
                  {{ currentStream.explanation }}
                </div>

                <div v-if="currentStream?.finalSql" class="bi-chat-sql">
                  <div class="bi-chat-sql-label">
                    <span>{{ $t('page.bi.chat.finalSql') }}</span>
                    <NButton text size="tiny" @click="handleCopy(currentStream!.finalSql)">
                      {{ $t('common.copy') }}
                    </NButton>
                  </div>
                  <pre class="font-mono text-12px">{{ currentStream.finalSql }}</pre>
                </div>
              </div>
            </div>
          </template>
        </NSpin>
      </div>

      <!-- 结果区：表格 / 图表 -->
      <div v-if="finalResult" class="bi-chat-result">
        <NSpace align="center" :size="8" class="mb-6px">
          <NTag type="info" size="small">
            {{ $t('page.bi.chat.result.rowCount', { count: finalResult.rowCount || 0 }) }}
          </NTag>
          <NTag v-if="finalResult.costMs" type="info" size="small">
            {{ $t('page.bi.chat.result.costMs', { ms: finalResult.costMs }) }}
          </NTag>
          <NTag v-if="finalResult.tokensUsed" type="info" size="small">
            {{ $t('page.bi.chat.result.tokens', { n: finalResult.tokensUsed }) }}
          </NTag>
          <NTag v-if="currentStream" type="warning" size="small">Streaming…</NTag>
          <span class="flex-1" />
          <NButton size="tiny" :type="resultView === 'table' ? 'primary' : 'default'" @click="resultView = 'table'">
            表格
          </NButton>
          <NButton
            size="tiny"
            :type="resultView === 'chart' ? 'primary' : 'default'"
            :disabled="!resultData.length"
            @click="resultView = 'chart'"
          >
            图表
          </NButton>
        </NSpace>

        <div v-if="resultView === 'table'">
          <NEmpty v-if="!resultData.length" :description="$t('page.bi.chat.noData')" />
          <NDataTable
            v-else
            :columns="resultColumns"
            :data="resultData"
            :max-height="320"
            :scroll-x="Math.max(800, (finalResult.columns?.length || 1) * 140)"
            :pagination="{ pageSize: 50 }"
            size="small"
            striped
          />
        </div>
        <div v-else-if="resultView === 'chart'">
          <div ref="chartRef" class="bi-chat-chart" />
        </div>
      </div>

      <!-- 输入区 -->
      <div class="bi-chat-input">
        <NInput
          v-model:value="questionInput"
          type="textarea"
          :placeholder="$t('page.bi.chat.placeholder')"
          :autosize="{ minRows: 2, maxRows: 5 }"
          :disabled="sending"
          @keydown.meta.enter.prevent="handleSend"
          @keydown.ctrl.enter.prevent="handleSend"
        />
        <NSpace align="center" :size="8" class="mt-8px">
          <NButton v-if="!sending" type="primary" :disabled="!questionInput.trim() || !currentDsId" @click="handleSend">
            {{ $t('page.bi.chat.send') }}
          </NButton>
          <NButton v-else type="warning" @click="handleStop">
            {{ $t('page.bi.chat.stop') }}
          </NButton>
          <span v-if="sending" class="text-12px text-gray-500">{{ $t('page.bi.chat.thinking') }}</span>
        </NSpace>
      </div>
    </NCard>
  </div>
</template>

<style scoped>
.bi-chat-layout {
  display: flex;
  gap: 12px;
  min-height: 600px;
}

.bi-chat-sidebar {
  width: 260px;
  flex-shrink: 0;
}

.bi-chat-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.bi-chat-session-item {
  position: relative;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: background 0.15s;
}
.bi-chat-session-item:hover {
  background: var(--n-color-hover, rgba(0, 0, 0, 0.04));
}
.bi-chat-session-item.active {
  background: var(--n-color-primary-hover, rgba(24, 160, 88, 0.12));
}
.bi-chat-session-title {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 60px;
}
.bi-chat-session-meta {
  margin-top: 2px;
}
.bi-chat-session-del {
  position: absolute;
  right: 8px;
  top: 8px;
  display: none;
}
.bi-chat-session-item:hover .bi-chat-session-del {
  display: inline-flex;
}

.bi-chat-messages {
  max-height: calc(100vh - 480px);
  min-height: 240px;
  overflow-y: auto;
  padding: 12px 4px;
  background: var(--n-color-card-2, #fafafa);
  border-radius: 6px;
  margin-bottom: 12px;
}

.bi-chat-msg {
  display: flex;
  margin-bottom: 12px;
}
.bi-chat-msg-user {
  justify-content: flex-end;
}
.bi-chat-msg-assistant {
  justify-content: flex-start;
}

.bi-chat-bubble {
  max-width: 80%;
  padding: 8px 12px;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}
.bi-chat-msg-user .bi-chat-bubble {
  background: var(--n-color-primary, #18a058);
  color: #fff;
}

.bi-chat-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
}

.bi-chat-steps {
  margin-bottom: 6px;
}

.bi-chat-sql {
  margin-top: 8px;
  background: #f5f5f5;
  border-radius: 4px;
  padding: 6px 8px;
}
.bi-chat-sql-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: #888;
  margin-bottom: 4px;
}
.bi-chat-sql pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}

.bi-chat-result {
  margin-bottom: 12px;
}

.bi-chat-chart {
  width: 100%;
  height: 320px;
  background: #fff;
  border-radius: 4px;
}

.bi-chat-input {
  border-top: 1px solid var(--n-border-color, #eee);
  padding-top: 10px;
}

.font-mono {
  font-family: 'JetBrains Mono', 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace;
}
</style>
