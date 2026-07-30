<script setup lang="ts">
import { ref } from 'vue';
import { NButton, NInput } from 'naive-ui';
import { $t } from '@/locales';

defineOptions({ name: 'BiChatMessageInput' });

interface Props {
  sending: boolean;
  disabled?: boolean;
}

const props = withDefaults(defineProps<Props>(), { disabled: false });

interface Emits {
  (e: 'send', payload: { question: string }): void;
  (e: 'stop'): void;
}

const emit = defineEmits<Emits>();

const inputValue = ref('');

function submit() {
  const question = inputValue.value.trim();
  if (!question || props.sending || props.disabled) return;
  emit('send', { question });
  inputValue.value = '';
}

function handleKeydown(e: KeyboardEvent) {
  // Enter 发送，Shift+Enter 换行；输入法组合中不触发
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    submit();
  }
}

function stopGenerate() {
  emit('stop');
}
</script>

<template>
  <div class="message-input px-20px py-16px bg-white dark:bg-gray-900">
    <div class="max-w-1200px mx-auto">
      <!-- ChatGPT 风格输入容器：圆角 + 阴影 + 内嵌发送按钮 -->
      <div
        class="input-shell relative rounded-16px border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm transition-all"
        :class="{ 'input-shell--disabled': disabled }"
      >
        <NInput
          v-model:value="inputValue"
          type="textarea"
          :placeholder="disabled ? $t('page.bi.chat.emptySession') : $t('page.bi.chat.placeholder')"
          :autosize="{ minRows: 3, maxRows: 12 }"
          :disabled="disabled"
          :bordered="false"
          class="chat-textarea"
          @keydown="handleKeydown"
        />
        <!-- 内嵌右下角发送/停止按钮 -->
        <div class="absolute right-12px bottom-12px">
          <NButton v-if="sending" type="error" ghost circle size="medium" @click="stopGenerate">
            <template #icon><icon-ic-round-stop class="text-icon" /></template>
          </NButton>
          <NButton
            v-else
            type="primary"
            circle
            size="medium"
            :disabled="!inputValue.trim() || disabled"
            @click="submit"
          >
            <template #icon><icon-ic-round-send class="text-icon" /></template>
          </NButton>
        </div>
      </div>
      <!-- 底部提示文字 -->
      <div class="text-center text-12px opacity-50 mt-8px">
        {{ $t('page.bi.chat.inputHint') }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.message-input {
  flex-shrink: 0;
}

.input-shell--disabled {
  opacity: 0.6;
}

/* 让 NInput 内部 textarea 贴合容器圆角并去掉默认边框 */
.chat-textarea :deep(.n-input__textarea-el) {
  padding: 14px 56px 14px 16px;
  font-size: 15px;
  line-height: 1.6;
}

.chat-textarea :deep(.n-input--textarea) {
  background: transparent;
}

.chat-textarea :deep(.n-input__textarea-wrapper) {
  background: transparent;
}
</style>
