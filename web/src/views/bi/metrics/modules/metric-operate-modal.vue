<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { NButton, NForm, NFormItem, NInput, NModal, NSelect, NSpace, NText } from 'naive-ui';
import { $t } from '@/locales';

const props = defineProps<{
  show: boolean;
  record: Api.Bi.Metric | null;
  datasourceOptions: { label: string; value: string }[];
}>();

const emit = defineEmits<{
  'update:show': [value: boolean];
  submit: [data: Api.Bi.MetricCreateParams | (Api.Bi.MetricUpdateParams & { id: string })];
}>();

const isEdit = computed(() => props.record !== null);

const formRef = ref<InstanceType<typeof NForm> | null>(null);

interface MetricForm {
  name: string;
  displayName: string;
  datasourceId: string | null;
  description: string | null;
  sqlTemplate: string;
  unit: string | null;
}

const form = ref<MetricForm>({
  name: '',
  displayName: '',
  datasourceId: null,
  description: null,
  sqlTemplate: '',
  unit: null
});

watch(
  () => props.show,
  v => {
    if (!v) return;
    if (props.record) {
      form.value = {
        name: props.record.name,
        displayName: props.record.displayName,
        datasourceId: props.record.datasourceId || null,
        description: props.record.description ?? null,
        sqlTemplate: props.record.sqlTemplate,
        unit: props.record.unit ?? null
      };
    } else {
      form.value = {
        name: '',
        displayName: '',
        datasourceId: null,
        description: null,
        sqlTemplate: '',
        unit: null
      };
    }
  }
);

const rules = {
  name: { required: true, message: $t('page.bi.metrics.form.formNameRequired'), trigger: 'blur' },
  displayName: {
    required: true,
    message: $t('page.bi.metrics.form.formDisplayNameRequired'),
    trigger: 'blur'
  },
  sqlTemplate: {
    required: true,
    message: $t('page.bi.metrics.form.formSqlTemplateRequired'),
    trigger: 'blur'
  },
  datasourceId: {
    required: true,
    message: $t('page.bi.metrics.form.formDatasourceRequired'),
    trigger: 'change'
  }
};

async function handleSubmit() {
  try {
    await formRef.value?.validate();
  } catch {
    return;
  }
  if (isEdit.value && props.record) {
    emit('submit', {
      id: props.record.id,
      displayName: form.value.displayName,
      description: form.value.description,
      sqlTemplate: form.value.sqlTemplate,
      unit: form.value.unit
    });
  } else {
    if (!form.value.datasourceId) return;
    emit('submit', {
      name: form.value.name,
      displayName: form.value.displayName,
      datasourceId: form.value.datasourceId,
      description: form.value.description,
      sqlTemplate: form.value.sqlTemplate,
      unit: form.value.unit
    });
  }
}

function handleCancel() {
  emit('update:show', false);
}
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    :title="isEdit ? $t('page.bi.metrics.edit') : $t('page.bi.metrics.create')"
    style="width: 640px"
    @update:show="(v: boolean) => emit('update:show', v)"
  >
    <NForm ref="formRef" :model="form" :rules="rules" label-placement="top">
      <NFormItem :label="$t('page.bi.metrics.form.name')" path="name">
        <NInput
          v-model:value="form.name"
          :disabled="isEdit"
          :placeholder="$t('page.bi.metrics.form.name')"
        />
        <template v-if="!isEdit" #feedback>
          <NText depth="3" class="text-12px">{{ $t('page.bi.metrics.form.nameTip') }}</NText>
        </template>
      </NFormItem>

      <NFormItem :label="$t('page.bi.metrics.form.displayName')" path="displayName">
        <NInput v-model:value="form.displayName" :placeholder="$t('page.bi.metrics.form.displayName')" />
      </NFormItem>

      <NFormItem :label="$t('page.bi.metrics.form.datasource')" path="datasourceId">
        <NSelect
          v-model:value="form.datasourceId"
          :options="datasourceOptions"
          :disabled="isEdit"
          :placeholder="$t('page.bi.metrics.form.datasource')"
        />
      </NFormItem>

      <NFormItem :label="$t('page.bi.metrics.form.description')" path="description">
        <NInput
          v-model:value="form.description"
          type="textarea"
          :rows="2"
          :placeholder="$t('page.bi.metrics.form.description')"
        />
      </NFormItem>

      <NFormItem :label="$t('page.bi.metrics.form.sqlTemplate')" path="sqlTemplate">
        <NInput
          v-model:value="form.sqlTemplate"
          type="textarea"
          :rows="4"
          :placeholder="$t('page.bi.metrics.form.sqlTemplatePlaceholder')"
        />
        <template #feedback>
          <NText depth="3" class="text-12px">{{ $t('page.bi.metrics.form.sqlTemplateTip') }}</NText>
        </template>
      </NFormItem>

      <NFormItem :label="$t('page.bi.metrics.form.unit')" path="unit">
        <NInput v-model:value="form.unit" :placeholder="$t('page.bi.metrics.form.unit')" />
      </NFormItem>
    </NForm>

    <template #footer>
      <NSpace justify="end">
        <NButton @click="handleCancel">{{ $t('common.cancel') }}</NButton>
        <NButton type="primary" @click="handleSubmit">{{ $t('common.confirm') }}</NButton>
      </NSpace>
    </template>
  </NModal>
</template>
