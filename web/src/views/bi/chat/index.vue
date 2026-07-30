<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { NSelect } from 'naive-ui';
import SessionList from './modules/session-list.vue';
import MessageRenderer from './modules/message-renderer.vue';
import MessageInput from './modules/message-input.vue';
import {
  fetchAddBiChatSession,
  fetchBiChatMessages,
  fetchBiChatSessionList,
  fetchDeleteBiChatSession,
  sendBiChatMessage
} from '@/service/api/bi-chat';
import { fetchBiDatasourceList } from '@/service/api/bi';
import { $t } from '@/locales';

defineOptions({ name: 'BiChat' });

const route = useRoute();
const router = useRouter();

/** 消息类型（扩展 chartType 字段，承载 SSE final 事件中的图表推荐） */
type ChatMessage = Api.Bi.BiChatMessage & { chartType?: string };

const sessions = ref<Api.Bi.BiChatSession[]>([]);
const currentSessionId = ref<string>('');
const messages = ref<ChatMessage[]>([]);
const collapsed = ref(false);
const sending = ref(false);

/** 顶部 toolbar：数据源选择（状态提升到页面级，MessageInput 不再持有） */
const datasourceId = ref<string | null>(null);
const datasourceOptions = ref<{ label: string; value: string }[]>([]);

let streamReader: ReadableStreamDefaultReader<Uint8Array> | null = null;

async function loadDatasources() {
  const { data } = await fetchBiDatasourceList({ current: 1, size: 100, name: null, dbType: null, statusType: '1' });
  if (data?.records) {
    datasourceOptions.value = data.records.map(d => ({ label: `${d.name} (${d.dbType})`, value: d.id }));
  }
}

/** 当前会话标题（用于 toolbar 展示） */
const currentSessionTitle = computed(() => {
  const s = sessions.value.find(item => item.id === currentSessionId.value);
  return s?.title || '';
});

async function loadSessions() {
  const { data } = await fetchBiChatSessionList({ current: 1, size: 100, title: null });
  if (data) {
    sessions.value = data.records || [];
  }
}

async function selectSession(id: string) {
  if (!id) return;
  currentSessionId.value = id;
  messages.value = [];
  const { data } = await fetchBiChatMessages(id, { current: 1, size: 1000, sessionId: null, role: null, status: null });
  if (data) {
    messages.value = (data.records || []) as ChatMessage[];
  }
  await router.replace({ query: { ...route.query, sessionId: id } });
}

async function handleNewSession() {
  const { data } = await fetchAddBiChatSession({ title: $t('page.bi.chat.newSession') });
  if (!data) return;
  await loadSessions();
  await selectSession(data.createdId);
}

async function handleDeleteSession(id: string) {
  const { error } = await fetchDeleteBiChatSession({ id });
  if (error) return;
  window.$message?.success($t('common.deleteSuccess'));
  if (currentSessionId.value === id) {
    currentSessionId.value = '';
    messages.value = [];
  }
  await loadSessions();
  if (!currentSessionId.value && sessions.value.length > 0) {
    await selectSession(sessions.value[0].id);
  }
}

function buildTempMessage(role: Api.Bi.ChatRole, content: string): ChatMessage {
  const now = Date.now();
  return {
    id: `temp-${role}-${now}-${Math.random().toString(36).slice(2, 8)}`,
    sessionId: currentSessionId.value,
    role,
    content,
    sqlText: null,
    sqlResult: null,
    agentStepsJson: role === 'assistant' ? [] : null,
    intentType: null,
    executionTimeMs: 0,
    tokenUsage: null,
    status: 'success',
    errorMessage: null,
    chartType: role === 'assistant' ? 'table' : undefined,
    createdBy: null,
    createdAt: now,
    updatedBy: null,
    updatedAt: now,
    statusType: null,
    fmtCreatedAt: '',
    fmtUpdatedAt: ''
  };
}

function handleSseEvent(event: Api.Bi.ChatEvent, msg: ChatMessage) {
  if (event.type === 'step') {
    if (!msg.agentStepsJson) msg.agentStepsJson = [];
    msg.agentStepsJson.push({
      node: event.node,
      status: event.status,
      data: event.data,
      elapsedMs: event.elapsedMs
    });
  } else if (event.type === 'final') {
    msg.content = event.data.explanation;
    msg.sqlText = event.data.sqlText;
    msg.sqlResult = event.data.sqlResult;
    msg.tokenUsage = event.data.tokenUsage;
    msg.chartType = event.data.chartType || 'table';
    msg.executionTimeMs = event.data.totalElapsedMs;
    msg.status = 'success';
    // 不覆盖临时 id：避免 v-for key 切换导致整张卡片重建闪烁；
    // 真实 id 在下次 selectSession 重新加载时由后端返回。
  } else if (event.type === 'error') {
    msg.status = 'failed';
    msg.errorMessage = event.error;
    msg.content = `${$t('page.bi.chat.messageStatus.failed')}: ${event.error}`;
    if (!msg.agentStepsJson) msg.agentStepsJson = [];
    msg.agentStepsJson.push({
      node: event.node,
      status: 'failed',
      data: { error: event.error },
      elapsedMs: event.elapsedMs || 0
    });
  }
  // heartbeat: 忽略
}

async function sendMessage(payload: { question: string }) {
  const question = payload.question.trim();
  if (!question || sending.value) return;

  // 确保存在会话；无则显式创建，便于后续选中与列表刷新
  if (!currentSessionId.value) {
    const { data } = await fetchAddBiChatSession({
      title: question.slice(0, 30) || $t('page.bi.chat.newSession')
    });
    if (!data) return;
    await loadSessions();
    currentSessionId.value = data.createdId;
    await router.replace({ query: { ...route.query, sessionId: data.createdId } });
  }

  sending.value = true;

  // 立即渲染用户消息
  messages.value.push(buildTempMessage('user', question));

  // 创建响应式 assistant 占位消息，SSE 事件直接 mutate 触发更新
  const assistantMsg = reactive<ChatMessage>(buildTempMessage('assistant', ''));
  messages.value.push(assistantMsg);

  let response: Response;
  try {
    response = await sendBiChatMessage({
      question,
      sessionId: currentSessionId.value,
      datasourceId: datasourceId.value || undefined
    });
  } catch (e: any) {
    assistantMsg.status = 'failed';
    assistantMsg.errorMessage = e?.message || 'Network error';
    assistantMsg.content = `${$t('page.bi.chat.messageStatus.failed')}: ${assistantMsg.errorMessage}`;
    sending.value = false;
    return;
  }

  if (!response.ok || !response.body) {
    assistantMsg.status = 'failed';
    assistantMsg.errorMessage = `HTTP ${response.status}`;
    assistantMsg.content = `${$t('page.bi.chat.messageStatus.failed')}: HTTP ${response.status}`;
    sending.value = false;
    return;
  }

  streamReader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await streamReader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      // 末尾可能是不完整行，保留到下次拼接
      buffer = lines.pop() || '';
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith('data:')) continue;
        const dataStr = trimmed.slice(5).trim();
        if (!dataStr) continue;
        try {
          const event = JSON.parse(dataStr) as Api.Bi.ChatEvent;
          handleSseEvent(event, assistantMsg);
        } catch {
          // 忽略非 JSON 行
        }
      }
    }
  } catch (e: any) {
    if (assistantMsg.status !== 'failed') {
      assistantMsg.status = 'failed';
      assistantMsg.errorMessage = e?.message || 'Stream error';
      assistantMsg.content = `${$t('page.bi.chat.messageStatus.failed')}: ${assistantMsg.errorMessage}`;
    }
  } finally {
    streamReader = null;
    sending.value = false;
    // 刷新会话列表（更新 lastMessageAt）
    await loadSessions();
  }
}

function stopGenerate() {
  if (streamReader) {
    streamReader.cancel().catch(() => {});
    streamReader = null;
  }
  sending.value = false;
}

onMounted(async () => {
  await Promise.all([loadSessions(), loadDatasources()]);
  const sessionId = route.query.sessionId as string;
  if (sessionId) {
    await selectSession(sessionId);
  } else if (sessions.value.length > 0) {
    await selectSession(sessions.value[0].id);
  }
});
</script>

<template>
  <div class="h-full flex">
    <!-- 左侧会话列表 -->
    <SessionList
      :sessions="sessions"
      :current-session-id="currentSessionId"
      :collapsed="collapsed"
      @select="selectSession"
      @new="handleNewSession"
      @delete="handleDeleteSession"
      @toggle="collapsed = !collapsed"
    />
    <!-- 右侧消息区 -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- 顶部 toolbar：数据源选择 + 当前会话标题 -->
      <div
        class="chat-toolbar flex-shrink-0 border-b border-gray-200 dark:border-gray-700 px-20px py-10px bg-white dark:bg-gray-900"
      >
        <div class="max-w-1200px mx-auto flex items-center gap-12px">
          <span class="text-13px opacity-70 whitespace-nowrap">{{ $t('page.bi.chat.selectDatasource') }}</span>
          <NSelect
            v-model:value="datasourceId"
            :options="datasourceOptions"
            :placeholder="$t('page.bi.chat.selectDatasource')"
            clearable
            size="small"
            class="w-260px"
          />
          <div
            v-if="currentSessionTitle"
            class="ml-auto text-13px opacity-50 truncate max-w-300px"
            :title="currentSessionTitle"
          >
            {{ currentSessionTitle }}
          </div>
        </div>
      </div>
      <!-- 消息展示区 -->
      <MessageRenderer :messages="messages" :streaming="sending" :has-session="!!currentSessionId" />
      <!-- 输入区 -->
      <MessageInput :sending="sending" :disabled="!currentSessionId" @send="sendMessage" @stop="stopGenerate" />
    </div>
  </div>
</template>

<style scoped></style>
