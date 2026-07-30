<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { statusTypeOptions } from '@/constants/business';
import { fetchAddBiMetric, fetchBiMetric, fetchUpdateBiMetric } from '@/service/api/bi-metric';
import { useFormRules, useNaiveForm } from '@/hooks/common/form';
import { $t } from '@/locales';

defineOptions({ name: 'MetricOperateModal' });

interface Props {
  operateType: NaiveUI.TableOperateType;
  rowData?: Api.Bi.BiMetric | null;
  datasourceOptions: { label: string; value: string }[];
}

const props = defineProps<Props>();

interface Emits {
  (e: 'submitted'): void;
}

const emit = defineEmits<Emits>();
const visible = defineModel<boolean>('visible', { default: false });
const { formRef, validate, restoreValidation } = useNaiveForm();
const { defaultRequiredRule } = useFormRules();

const title = computed(() => {
  const titles: Record<NaiveUI.TableOperateType, string> = {
    add: $t('page.bi.metrics.create'),
    edit: $t('page.bi.metrics.edit')
  };
  return titles[props.operateType];
});

const chartTypeOptions = computed(() => [
  { label: $t('page.bi.metrics.chartTypes.table'), value: 'table' },
  { label: $t('page.bi.metrics.chartTypes.line'), value: 'line' },
  { label: $t('page.bi.metrics.chartTypes.bar'), value: 'bar' },
  { label: $t('page.bi.metrics.chartTypes.pie'), value: 'pie' },
  { label: $t('page.bi.metrics.chartTypes.scatter'), value: 'scatter' },
  { label: $t('page.bi.metrics.chartTypes.area'), value: 'area' }
]);

function createDefaultModel(): Api.Bi.BiMetricOperateParams {
  return {
    name: '',
    code: '',
    description: null,
    datasourceId: '',
    sqlTemplate: '',
    chartType: null,
    statusType: '1'
  };
}

const model = ref<Api.Bi.BiMetricOperateParams>(createDefaultModel());

type RuleKey = 'name' | 'code' | 'datasourceId' | 'sqlTemplate';
const rules: Record<RuleKey, App.Global.FormRule> = {
  name: defaultRequiredRule,
  code: defaultRequiredRule,
  datasourceId: defaultRequiredRule,
  sqlTemplate: defaultRequiredRule
};

async function handleInitModel() {
  model.value = createDefaultModel();
  if (props.operateType === 'edit' && props.rowData) {
    const { data } = await fetchBiMetric(props.rowData.id);
    if (data) {
      const { id, name, code, description, datasourceId, sqlTemplate, chartType, statusType } = data;
      Object.assign(model.value, {
        id,
        name,
        code,
        description,
        datasourceId,
        sqlTemplate,
        chartType,
        statusType
      });
    }
  }
}

function closeModal() {
  visible.value = false;
}

async function handleSubmit() {
  await validate();
  if (props.operateType === 'add') {
    const { error } = await fetchAddBiMetric(model.value);
    if (error) return;
    window.$message?.success($t('common.addSuccess'));
  } else {
    const { error } = await fetchUpdateBiMetric({ ...model.value, id: props.rowData?.id });
    if (error) return;
    window.$message?.success($t('common.updateSuccess'));
  }
  closeModal();
  emit('submitted');
}

watch(visible, () => {
  if (visible.value) {
    handleInitModel();
    restoreValidation();
  }
});
</script>

<template>
  <NModal v-model:show="visible" :title="title" preset="card" class="w-700px">
    <NScrollbar class="h-480px pr-20px">
      <NForm ref="formRef" :model="model" :rules="rules" label-placement="left" :label-width="110">
        <NGrid responsive="screen" item-responsive>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.metrics.name')" path="name">
            <NInput v-model:value="model.name" :placeholder="$t('page.bi.metrics.form.name')" />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.metrics.code')" path="code">
            <NInput v-model:value="model.code" :placeholder="$t('page.bi.metrics.form.code')" />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.metrics.datasource')" path="datasourceId">
            <NSelect
              v-model:value="model.datasourceId"
              :options="datasourceOptions"
              filterable
              :placeholder="$t('page.bi.metrics.form.datasource')"
            />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.metrics.chartType')" path="chartType">
            <NSelect
              v-model:value="model.chartType"
              :options="chartTypeOptions"
              clearable
              :placeholder="$t('page.bi.metrics.form.chartType')"
            />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.audit.status')" path="statusType">
            <NRadioGroup v-model:value="model.statusType">
              <NRadio v-for="item in statusTypeOptions" :key="item.value" :value="item.value" :label="$t(item.label)" />
            </NRadioGroup>
          </NFormItemGi>
          <NFormItemGi span="24" :label="$t('page.bi.metrics.description')" path="description">
            <NInput
              v-model:value="model.description"
              type="textarea"
              :rows="2"
              :placeholder="$t('page.bi.metrics.form.description')"
            />
          </NFormItemGi>
          <NFormItemGi span="24" :label="$t('page.bi.metrics.sqlTemplate')" path="sqlTemplate">
            <NInput
              v-model:value="model.sqlTemplate"
              type="textarea"
              :rows="6"
              :placeholder="$t('page.bi.metrics.sqlTemplateHint')"
            />
          </NFormItemGi>
        </NGrid>
      </NForm>
    </NScrollbar>
    <template #footer>
      <NSpace justify="end" :size="16">
        <NButton @click="closeModal">{{ $t('common.cancel') }}</NButton>
        <NButton type="primary" @click="handleSubmit">{{ $t('common.confirm') }}</NButton>
      </NSpace>
    </template>
  </NModal>
</template>
