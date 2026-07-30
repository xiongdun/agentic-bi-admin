<script setup lang="ts">
import { $t } from '@/locales';

defineOptions({ name: 'MetricTestModal' });

interface Props {
  target: Api.Bi.BiMetric | null;
  loading: boolean;
  result: Api.Bi.BiMetricTestResult | null;
}

defineProps<Props>();
const visible = defineModel<boolean>('visible', { default: false });
</script>

<template>
  <NModal v-model:show="visible" :title="$t('page.bi.metrics.testResult')" preset="card" class="w-700px">
    <NSpin :show="loading">
      <template v-if="result">
        <NDescriptions :column="2" label-placement="left" bordered size="small">
          <NDescriptionsItem :label="$t('page.bi.audit.status')">
            <NTag :type="result.success ? 'success' : 'error'" size="small">
              {{ result.success ? $t('page.bi.audit.statuses.success') : $t('page.bi.audit.statuses.failed') }}
            </NTag>
          </NDescriptionsItem>
          <NDescriptionsItem :label="$t('page.bi.audit.executionTime')">{{ result.elapsedMs }} ms</NDescriptionsItem>
          <NDescriptionsItem :label="$t('page.bi.sql-workbench.rows')">
            {{ result.rowCount }}
          </NDescriptionsItem>
          <NDescriptionsItem :label="$t('page.bi.metrics.code')">
            {{ target?.code || '-' }}
          </NDescriptionsItem>
          <NDescriptionsItem :label="$t('page.bi.metrics.sqlTemplate')" :span="2">
            <NCode :code="result.sql" language="sql" word-wrap />
          </NDescriptionsItem>
          <NDescriptionsItem v-if="result.error" :label="$t('page.bi.audit.errorMessage')" :span="2">
            <NAlert type="error" :show-icon="true">{{ result.error }}</NAlert>
          </NDescriptionsItem>
        </NDescriptions>
      </template>
      <NEmpty v-else-if="!loading" :description="$t('common.noData')" />
    </NSpin>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="visible = false">{{ $t('common.close') }}</NButton>
      </NSpace>
    </template>
  </NModal>
</template>
