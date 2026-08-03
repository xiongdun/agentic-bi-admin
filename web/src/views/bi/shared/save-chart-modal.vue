<script setup lang="ts">
/**
 * 保存图表弹窗 — 智能对话与 SQL 工作台共用。
 *
 * 从外部接收图表上下文（数据源 / 图表类型 / 轴字段 / SQL / 结果快照），
 * 用户只需填写标题 / 说明 / 标签，提交后调用 fetchAddBiChart 保存。
 *
 * 图表上下文以只读形式展示在弹窗中，用户可确认无误后再保存。
 */
import { computed, ref, watch } from 'vue';
import { fetchAddBiChart } from '@/service/api/bi-chart';
import { useFormRules, useNaiveForm } from '@/hooks/common/form';
import { $t } from '@/locales';
import { chartTypeOptions, type ChartType } from './chart-config';

defineOptions({ name: 'BiSaveChartModal' });

/** 外部传入的图表上下文（只读） */
interface ChartContext {
  datasourceId: string;
  chartType: ChartType;
  xCol: string;
  yCol: string;
  sqlText: string;
  resultSnapshot: Api.Bi.ChartResultSnapshot;
  snapshotAt: string;
}

interface Props {
  /** 图表上下文 */
  chartData: ChartContext | null;
  /** 默认标题（如对话问题前 50 字符） */
  defaultName?: string;
}

const props = defineProps<Props>();

interface Emits {
  (e: 'submitted'): void;
}

const emit = defineEmits<Emits>();
const visible = defineModel<boolean>('visible', { default: false });
const { formRef, validate, restoreValidation } = useNaiveForm();
const { defaultRequiredRule } = useFormRules();

const submitting = ref<boolean>(false);

interface SaveModel {
  name: string;
  description: string | null;
  tags: string | null;
}

function createDefaultModel(): SaveModel {
  return {
    name: props.defaultName ?? '',
    description: null,
    tags: null
  };
}

const model = ref<SaveModel>(createDefaultModel());

type RuleKey = 'name';
const rules: Record<RuleKey, App.Global.FormRule> = {
  name: defaultRequiredRule
};

/** 图表类型展示名 */
const chartTypeLabel = computed(() => {
  if (!props.chartData) return '';
  const opt = chartTypeOptions.find(o => o.value === props.chartData?.chartType);
  return opt?.label ?? props.chartData.chartType;
});

/** 结果快照摘要（行数 / 耗时） */
const snapshotSummary = computed(() => {
  if (!props.chartData) return '';
  const snap = props.chartData.resultSnapshot;
  return `${snap.rowCount} ${$t('page.bi.chart.rowCount')} · ${snap.elapsedMs}ms`;
});

/** SQL 预览（前 200 字符） */
const sqlPreview = computed(() => {
  if (!props.chartData) return '';
  const sql = props.chartData.sqlText;
  return sql.length > 200 ? `${sql.slice(0, 200)}...` : sql;
});

function closeModal() {
  visible.value = false;
}

async function handleSubmit() {
  if (!props.chartData) return;
  await validate();
  submitting.value = true;
  try {
    const params: Api.Bi.BiChartOperateParams = {
      name: model.value.name,
      description: model.value.description,
      datasourceId: props.chartData.datasourceId,
      chartType: props.chartData.chartType,
      xCol: props.chartData.xCol,
      yCol: props.chartData.yCol,
      sqlText: props.chartData.sqlText,
      resultSnapshot: props.chartData.resultSnapshot,
      tags: model.value.tags,
      snapshotAt: props.chartData.snapshotAt
    };
    const { error } = await fetchAddBiChart(params);
    if (error) return;
    window.$message?.success($t('page.bi.chart.saveSuccess'));
    closeModal();
    emit('submitted');
  } finally {
    submitting.value = false;
  }
}

watch(visible, val => {
  if (val) {
    model.value = createDefaultModel();
    restoreValidation();
  }
});
</script>

<template>
  <NModal v-model:show="visible" :title="$t('page.bi.chart.saveAsChart')" preset="card" class="w-600px">
    <NScrollbar class="max-h-520px pr-20px">
      <NForm ref="formRef" :model="model" :rules="rules" label-placement="left" :label-width="90">
        <!-- 用户填写区域 -->
        <NFormItem :label="$t('page.bi.chart.name')" path="name">
          <NInput v-model:value="model.name" :placeholder="$t('page.bi.chart.name')" maxlength="100" show-count />
        </NFormItem>
        <NFormItem :label="$t('page.bi.chart.tags')" path="tags">
          <NInput v-model:value="model.tags" :placeholder="$t('page.bi.chart.tagsHint')" maxlength="500" />
        </NFormItem>
        <NFormItem :label="$t('page.bi.chart.description')" path="description">
          <NInput
            v-model:value="model.description"
            type="textarea"
            :rows="2"
            :placeholder="$t('page.bi.chart.description')"
          />
        </NFormItem>

        <!-- 图表上下文预览（只读） -->
        <NDivider title-placement="left" class="!mt-8px">
          <span class="text-12px text-gray-500">{{ $t('page.bi.chart.chartType') }}</span>
        </NDivider>
        <NDescriptions label-placement="left" :column="2" size="small" bordered>
          <NDescriptionsItem :label="$t('page.bi.chart.chartType')">
            <NTag size="small" type="primary">{{ chartTypeLabel }}</NTag>
          </NDescriptionsItem>
          <NDescriptionsItem :label="$t('page.bi.chart.snapshotAt')">
            {{ chartData?.snapshotAt ? new Date(chartData.snapshotAt).toLocaleString() : '-' }}
          </NDescriptionsItem>
          <NDescriptionsItem :label="$t('page.bi.chart.xCol')">{{ chartData?.xCol || '-' }}</NDescriptionsItem>
          <NDescriptionsItem :label="$t('page.bi.chart.yCol')">{{ chartData?.yCol || '-' }}</NDescriptionsItem>
          <NDescriptionsItem :label="$t('page.bi.chart.rowCount')">
            {{ snapshotSummary }}
          </NDescriptionsItem>
          <NDescriptionsItem :label="$t('page.bi.chart.truncated')">
            <NTag v-if="chartData?.resultSnapshot?.isTruncated" size="small" type="warning">
              {{ $t('page.bi.chart.truncated') }}
            </NTag>
            <span v-else class="text-gray-400">-</span>
          </NDescriptionsItem>
        </NDescriptions>
        <div class="mt-12px">
          <div class="mb-4px text-12px text-gray-500">{{ $t('page.bi.chart.sqlText') }}</div>
          <NCode :code="sqlPreview" language="sql" word-wrap class="rounded-4px" />
        </div>
      </NForm>
    </NScrollbar>
    <template #footer>
      <NSpace justify="end" :size="16">
        <NButton @click="closeModal">{{ $t('common.cancel') }}</NButton>
        <NButton type="primary" :loading="submitting" @click="handleSubmit">
          {{ $t('page.bi.chart.save') }}
        </NButton>
      </NSpace>
    </template>
  </NModal>
</template>
