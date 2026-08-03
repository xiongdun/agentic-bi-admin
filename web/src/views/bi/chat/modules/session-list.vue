<script setup lang="ts">
import { nextTick, ref } from 'vue';
import { NButton, NEmpty, NInput, NPopconfirm, NScrollbar, NTooltip } from 'naive-ui';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';

defineOptions({ name: 'BiChatSessionList' });

interface Props {
  sessions: Api.Bi.BiChatSession[];
  currentSessionId: string;
  collapsed: boolean;
}

const props = defineProps<Props>();

interface Emits {
  (e: 'select', id: string): void;
  (e: 'new'): void;
  (e: 'delete', id: string): void;
  (e: 'rename', id: string, title: string): void;
  (e: 'toggle'): void;
}

const emit = defineEmits<Emits>();
const { hasAuth } = useAuth();

/** 当前正在编辑标题的会话 ID（空字符串表示非编辑态） */
const editingId = ref<string>('');
const editingTitle = ref('');
const inputRef = ref<InstanceType<typeof NInput> | null>(null);

function setInputRef(el: any) {
  inputRef.value = el;
}

function select(id: string) {
  if (id !== props.currentSessionId) emit('select', id);
}

async function startEdit(s: Api.Bi.BiChatSession) {
  if (!hasAuth('B_BI_CHAT_NEW')) return;
  editingId.value = s.id;
  editingTitle.value = s.title || '';
  await nextTick();
  inputRef.value?.focus();
}

function commitEdit() {
  if (!editingId.value) return;
  const title = editingTitle.value.trim();
  if (title) emit('rename', editingId.value, title);
  editingId.value = '';
}

function cancelEdit() {
  editingId.value = '';
}

function formatTime(ts: number | null): string {
  if (!ts) return '';
  const d = new Date(ts);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
</script>

<template>
  <div
    class="session-list h-full flex flex-col border-r border-gray-200 dark:border-gray-700 transition-all duration-200 overflow-hidden"
    :style="{ width: collapsed ? '56px' : '280px' }"
  >
    <!-- 折叠态：仅展开按钮 + 新建按钮 -->
    <template v-if="collapsed">
      <div class="flex flex-col items-center gap-8px py-12px">
        <NButton size="small" quaternary circle @click="emit('toggle')">
          <template #icon><icon-ic-round-chevron-right /></template>
        </NButton>
        <NTooltip v-if="hasAuth('B_BI_CHAT_NEW')" placement="right" trigger="hover">
          <template #trigger>
            <NButton size="small" quaternary circle @click="emit('new')">
              <template #icon><icon-lucide-plus class="text-icon" /></template>
            </NButton>
          </template>
          {{ $t('page.bi.chat.newSession') }}
        </NTooltip>
      </div>
    </template>

    <!-- 展开态：标题栏 + 会话列表 -->
    <template v-else>
      <div class="flex items-center justify-between px-12px py-10px border-b border-gray-200 dark:border-gray-700">
        <span class="font-500 text-15px">{{ $t('page.bi.chat.sessionList') }}</span>
        <div class="flex items-center gap-4px">
          <NTooltip v-if="hasAuth('B_BI_CHAT_NEW')" trigger="hover">
            <template #trigger>
              <NButton size="small" quaternary circle @click="emit('new')">
                <template #icon><icon-lucide-plus class="text-icon" /></template>
              </NButton>
            </template>
            {{ $t('page.bi.chat.newSession') }}
          </NTooltip>
          <NButton size="small" quaternary circle @click="emit('toggle')">
            <template #icon><icon-ic-round-chevron-left /></template>
          </NButton>
        </div>
      </div>

      <NScrollbar class="flex-1">
        <NEmpty v-if="sessions.length === 0" :description="$t('page.bi.chat.noSessions')" class="py-40px" />
        <div v-else class="py-6px">
          <div
            v-for="s in sessions"
            :key="s.id"
            class="session-item group flex items-center justify-between gap-8px px-12px py-10px mx-6px my-2px rounded-6px cursor-pointer transition-colors"
            :class="
              s.id === currentSessionId
                ? 'bg-primary-100 dark:bg-primary-900 dark:opacity-30'
                : 'hover:bg-gray-100 dark:hover:bg-gray-800'
            "
            @click="select(s.id)"
          >
            <div class="flex-1 overflow-hidden">
              <NInput
                v-if="editingId === s.id"
                :ref="setInputRef"
                v-model:value="editingTitle"
                size="small"
                :placeholder="$t('page.bi.chat.newSession')"
                @blur="commitEdit"
                @keyup.enter="commitEdit"
                @keyup.esc="cancelEdit"
                @click.stop
              />
              <template v-else>
                <div
                  class="truncate text-14px font-500 select-none"
                  :class="{ 'cursor-text': hasAuth('B_BI_CHAT_NEW') }"
                  @dblclick.stop="startEdit(s)"
                >
                  {{ s.title || $t('page.bi.chat.newSession') }}
                </div>
                <div class="truncate text-12px opacity-60 mt-2px">
                  {{ formatTime(s.lastMessageAt || s.createdAt) }}
                </div>
              </template>
            </div>
            <NPopconfirm v-if="hasAuth('B_BI_CHAT_DELETE')" @positive-click="emit('delete', s.id)">
              <template #trigger>
                <NButton
                  size="tiny"
                  quaternary
                  circle
                  type="error"
                  class="opacity-0 group-hover:opacity-100 transition-opacity"
                  @click.stop
                >
                  <template #icon><icon-ic-round-close class="text-icon" /></template>
                </NButton>
              </template>
              {{ $t('page.bi.chat.deleteSessionConfirm') }}
            </NPopconfirm>
          </div>
        </div>
      </NScrollbar>
    </template>
  </div>
</template>

<style scoped>
.session-list {
  flex-shrink: 0;
}
</style>
