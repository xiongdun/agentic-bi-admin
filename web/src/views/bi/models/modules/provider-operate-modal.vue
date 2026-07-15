<script setup lang="tsx">
import { computed, reactive, ref, watch } from 'vue';
import { NForm, NFormItemGi, NGrid, NInput, NInputNumber, NSelect, NSwitch, useMessage } from 'naive-ui';
import type { FormRules } from 'naive-ui';
import { fetchCreateBiModelProvider, fetchUpdateBiModelProvider } from '@/service/api';
import { $t } from '@/locales';
import { useNaiveForm } from '@/hooks/common/form';

defineOptions({ name: 'ModelProviderOperateModal' });

const props = defineProps<{
  /** 编辑中的 provider；null 表示新增 */
  editing: Api.Bi.ModelProvider | null;
}>();

const emit = defineEmits<{
  submitted: [];
}>();

const visible = ref(false);
const message = useMessage();
const { formRef, validate, restoreValidation } = useNaiveForm();

const TYPE_OPTIONS: { label: string; value: Api.Bi.ModelProviderType }[] = [
  { label: 'OpenAI Compatible', value: 'openai_compatible' },
  { label: 'Anthropic', value: 'anthropic' },
  { label: 'Ollama', value: 'ollama' },
  { label: 'Mock', value: 'mock' },
  { label: 'Custom', value: 'custom' }
];

const model = reactive<Api.Bi.ModelProviderAddParams & { id?: string }>({
  name: '',
  code: '',
  type: 'openai_compatible',
  displayName: null,
  baseUrl: null,
  apiKey: null,
  isEnabled: true,
  isDefault: false,
  order: 0,
  remark: null
});

const isEdit = computed(() => Boolean(props.editing?.id));

const title = computed(() => (isEdit.value ? $t('page.bi.models.provider.edit') : $t('page.bi.models.provider.add')));

const rules = computed<FormRules>(() => ({
  name: { required: true, message: $t('page.bi.models.provider.form.name'), trigger: ['blur', 'input'] },
  code: { required: true, message: $t('page.bi.models.provider.form.code'), trigger: ['blur', 'input'] },
  type: { required: true, message: $t('page.bi.models.provider.form.type'), trigger: ['blur', 'change'] }
}));

function resetModel() {
  Object.assign(model, {
    name: '',
    code: '',
    type: 'openai_compatible',
    displayName: null,
    baseUrl: null,
    apiKey: null,
    isEnabled: true,
    isDefault: false,
    order: 0,
    remark: null
  });
}

function fillFromEditing(row: Api.Bi.ModelProvider) {
  Object.assign(model, {
    id: row.id,
    name: row.name,
    code: row.code,
    type: row.type,
    displayName: row.displayName,
    baseUrl: row.baseUrl,
    apiKey: null, // 不回填
    isEnabled: row.isEnabled,
    isDefault: row.isDefault,
    order: row.order,
    remark: row.remark
  });
}

function open(row?: Api.Bi.ModelProvider) {
  if (row) {
    fillFromEditing(row);
  } else {
    resetModel();
  }
  restoreValidation();
  visible.value = true;
}

function close() {
  visible.value = false;
}

async function handleSubmit() {
  await validate();
  const payload: Api.Bi.ModelProviderAddParams = {
    name: model.name,
    code: model.code,
    type: model.type,
    displayName: model.displayName,
    baseUrl: model.baseUrl,
    apiKey: model.apiKey || undefined,
    isEnabled: model.isEnabled,
    isDefault: model.isDefault,
    order: model.order,
    remark: model.remark
  };
  let error: unknown = null;
  if (isEdit.value && model.id) {
    const updatePayload: Api.Bi.ModelProviderUpdateParams = { ...payload };
    if (!model.apiKey) {
      // 不修改 API Key
      delete updatePayload.apiKey;
    }
    const res = await fetchUpdateBiModelProvider(model.id, updatePayload);
    error = res.error;
    if (!error) message.success($t('common.modifySuccess'));
  } else {
    const res = await fetchCreateBiModelProvider(payload);
    error = res.error;
    if (!error) message.success($t('common.addSuccess'));
  }
  if (!error) {
    close();
    emit('submitted');
  }
}

defineExpose({ open, close });

watch(visible, v => {
  if (!v) resetModel();
});
</script>

<template>
  <NModal
    v-model:show="visible"
    preset="card"
    :title="title"
    style="width: 720px"
    :mask-closable="false"
    @close="close"
  >
    <NForm ref="formRef" :model="model" :rules="rules" label-placement="top">
      <NGrid :cols="12" :x-gap="12">
        <NFormItemGi :span="6" :label="$t('page.bi.models.provider.name')" path="name">
          <NInput v-model:value="model.name" :placeholder="$t('page.bi.models.provider.form.name')" />
        </NFormItemGi>
        <NFormItemGi :span="3" :label="$t('page.bi.models.provider.code')" path="code">
          <NInput
            v-model:value="model.code"
            :placeholder="$t('page.bi.models.provider.form.code')"
            :disabled="isEdit"
          />
        </NFormItemGi>
        <NFormItemGi :span="3" :label="$t('page.bi.models.provider.type')" path="type">
          <NSelect v-model:value="model.type" :options="TYPE_OPTIONS" :disabled="isEdit" />
        </NFormItemGi>

        <NFormItemGi :span="6" :label="$t('page.bi.models.provider.displayName')" path="displayName">
          <NInput v-model:value="model.displayName" :placeholder="$t('page.bi.models.provider.form.displayName')" />
        </NFormItemGi>
        <NFormItemGi :span="6" :label="$t('page.bi.models.provider.baseUrl')" path="baseUrl">
          <NInput v-model:value="model.baseUrl" :placeholder="$t('page.bi.models.provider.form.baseUrl')" />
        </NFormItemGi>

        <NFormItemGi :span="12" :label="$t('page.bi.models.provider.apiKey')" path="apiKey">
          <NInput
            v-model:value="model.apiKey"
            type="password"
            show-password-on="click"
            :placeholder="
              isEdit ? $t('page.bi.models.provider.apiKeyPlaceholder') : $t('page.bi.models.provider.form.apiKey')
            "
          />
        </NFormItemGi>

        <NFormItemGi :span="12" :label="$t('page.bi.models.provider.remark')" path="remark">
          <NInput v-model:value="model.remark" type="textarea" :rows="2" />
        </NFormItemGi>

        <NFormItemGi :span="3" :label="$t('page.bi.models.provider.order')" path="order">
          <NInputNumber v-model:value="model.order" :min="0" style="width: 100%" />
        </NFormItemGi>
        <NFormItemGi :span="5" :label="$t('page.bi.models.provider.isEnabled')" path="isEnabled">
          <NSwitch v-model:value="model.isEnabled" />
        </NFormItemGi>
        <NFormItemGi :span="4" :label="$t('page.bi.models.provider.isDefault')" path="isDefault">
          <NSwitch v-model:value="model.isDefault" />
        </NFormItemGi>
      </NGrid>
    </NForm>

    <template #footer>
      <NSpace justify="end">
        <NButton @click="close">{{ $t('common.cancel') }}</NButton>
        <NButton type="primary" @click="handleSubmit">{{ $t('common.confirm') }}</NButton>
      </NSpace>
    </template>
  </NModal>
</template>
