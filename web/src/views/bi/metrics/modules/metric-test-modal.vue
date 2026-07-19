<script setup lang="ts">
import { NAlert, NDescriptions, NDescriptionsItem, NModal, NSpin, NTag } from 'naive-ui';
import { $t } from '@/locales';

defineProps<{
  show: boolean;
  result: Api.Bi.MetricTestResult | null;
  loading: boolean;
}>();

const emit = defineEmits<{
  'update:show': [value: boolean];
}>();
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    :title="$t('page.bi.metrics.test')"
    style="width: 480px"
    @update:show="(v: boolean) => emit('update:show', v)"
  >
    <div v-if="loading" class="flex justify-center py-24px">
      <NSpin />
    </div>
    <div v-else-if="result">
      <div class="mb-12px">
        <NTag v-if="result.success" type="success">
          {{ $t('page.bi.metrics.testOk') }}
        </NTag>
        <NTag v-else type="error">
          {{ $t('page.bi.metrics.testFailed') }}
        </NTag>
      </div>

      <NDescriptions v-if="result.success" :column="1" bordered size="small">
        <NDescriptionsItem :label="$t('page.bi.metrics.testResult.datasource')">
          {{ result.datasource }}
        </NDescriptionsItem>
        <NDescriptionsItem :label="$t('page.bi.metrics.testResult.dialect')">
          {{ result.dialect }}
        </NDescriptionsItem>
        <NDescriptionsItem :label="$t('page.bi.metrics.testResult.placeholders')">
          <NTag
            v-for="p in result.placeholders ?? []"
            :key="p"
            class="mr-4px"
            type="info"
            size="small"
          >
            {{ p }}
          </NTag>
        </NDescriptionsItem>
      </NDescriptions>

      <NAlert v-else type="error" :title="$t('page.bi.metrics.testFailed')" class="mt-12px">
        {{ result.error }}
      </NAlert>
    </div>
  </NModal>
</template>
