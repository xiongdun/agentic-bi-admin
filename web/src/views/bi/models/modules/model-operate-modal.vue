<script setup lang="tsx">
import { computed, reactive, ref, watch } from 'vue';
import {
  NCheckbox,
  NCheckboxGroup,
  NForm,
  NFormItemGi,
  NGrid,
  NInput,
  NInputNumber,
  NSelect,
  NSwitch,
  useMessage
} from 'naive-ui';
import type { FormRules } from 'naive-ui';
import { fetchCreateBiModel, fetchUpdateBiModel } from '@/service/api';
import { $t } from '@/locales';
import { useNaiveForm } from '@/hooks/common/form';

defineOptions({ name: 'BiModelOperateModal' });

const props = defineProps<{
  /** 编辑中的 model；null 表示新增 */
  editing: Api.Bi.BiModel | null;
  /** 提供商列表（用于选择） */
  providers: Api.Bi.ModelProvider[];
}>();

const emit = defineEmits<{
  submitted: [];
}>();

const visible = ref(false);
const message = useMessage();
const { formRef, validate, restoreValidation } = useNaiveForm();

const TYPE_OPTIONS: { label: string; value: Api.Bi.ModelType }[] = [
  { label: $t('page.bi.models.model.typeLabel.chat'), value: 'chat' },
  { label: $t('page.bi.models.model.typeLabel.embedding'), value: 'embedding' },
  { label: $t('page.bi.models.model.typeLabel.vision'), value: 'vision' }
];

const CAPABILITY_OPTIONS: { label: string; value: Api.Bi.ModelCapability }[] = [
  { label: $t('page.bi.models.model.capabilityLabel.function_call'), value: 'function_call' },
  { label: $t('page.bi.models.model.capabilityLabel.reasoning'), value: 'reasoning' },
  { label: $t('page.bi.models.model.capabilityLabel.json_mode'), value: 'json_mode' },
  { label: $t('page.bi.models.model.capabilityLabel.vision'), value: 'vision' },
  { label: $t('page.bi.models.model.capabilityLabel.streaming'), value: 'streaming' }
];

const model = reactive<Api.Bi.BiModelAddParams & { id?: string; defaultParamsText?: string }>({
  providerId: '',
  code: '',
  displayName: null,
  type: 'chat',
  contextWindow: 8192,
  inputPrice: null,
  outputPrice: null,
  defaultParams: null,
  defaultParamsText: '',
  capabilities: [],
  isEnabled: true,
  isDefault: false,
  order: 0,
  remark: null
});

const providerOptions = computed(() =>
  props.providers.map(p => ({
    label: `${p.name} (${p.code})`,
    value: p.id
  }))
);

const isEdit = computed(() => Boolean(props.editing?.id));

const title = computed(() => (isEdit.value ? $t('page.bi.models.model.edit') : $t('page.bi.models.model.add')));

const rules = computed<FormRules>(() => ({
  providerId: { required: true, message: $t('page.bi.models.model.form.provider'), trigger: ['blur', 'change'] },
  code: { required: true, message: $t('page.bi.models.model.form.code'), trigger: ['blur', 'input'] }
}));

function resetModel() {
  Object.assign(model, {
    providerId: providerOptions.value[0]?.value ?? '',
    code: '',
    displayName: null,
    type: 'chat',
    contextWindow: 8192,
    inputPrice: null,
    outputPrice: null,
    defaultParams: null,
    defaultParamsText: '',
    capabilities: [],
    isEnabled: true,
    isDefault: false,
    order: 0,
    remark: null
  });
}

function fillFromEditing(row: Api.Bi.BiModel) {
  const dp = row.defaultParams;
  Object.assign(model, {
    id: row.id,
    providerId: row.providerId,
    code: row.code,
    displayName: row.displayName,
    type: row.type,
    contextWindow: row.contextWindow,
    inputPrice: row.inputPrice,
    outputPrice: row.outputPrice,
    defaultParams: dp,
    defaultParamsText: dp ? JSON.stringify(dp, null, 2) : '',
    capabilities: row.capabilities ?? [],
    isEnabled: row.isEnabled,
    isDefault: row.isDefault,
    order: row.order,
    remark: row.remark
  });
}

function open(row?: Api.Bi.BiModel) {
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

function parseDefaultParams(text: string): Record<string, unknown> | null {
  const trimmed = text.trim();
  if (!trimmed) return null;
  try {
    const obj = JSON.parse(trimmed);
    if (obj && typeof obj === 'object' && !Array.isArray(obj)) {
      return obj as Record<string, unknown>;
    }
  } catch {
    // 忽略
  }
  return { __raw: text };
}

async function handleSubmit() {
  await validate();
  const payload: Api.Bi.BiModelAddParams = {
    providerId: model.providerId,
    code: model.code,
    displayName: model.displayName,
    type: model.type,
    contextWindow: model.contextWindow,
    inputPrice: model.inputPrice,
    outputPrice: model.outputPrice,
    defaultParams: parseDefaultParams(model.defaultParamsText ?? ''),
    capabilities: model.capabilities ?? [],
    isEnabled: model.isEnabled,
    isDefault: model.isDefault,
    order: model.order,
    remark: model.remark
  };
  let error: unknown = null;
  if (isEdit.value && model.id) {
    const res = await fetchUpdateBiModel(model.id, payload);
    error = res.error;
    if (!error) message.success($t('common.modifySuccess'));
  } else {
    const res = await fetchCreateBiModel(payload);
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
        <NFormItemGi :span="6" :label="$t('page.bi.models.model.provider')" path="providerId">
          <NSelect v-model:value="model.providerId" :options="providerOptions" :disabled="isEdit" />
        </NFormItemGi>
        <NFormItemGi :span="3" :label="$t('page.bi.models.model.code')" path="code">
          <NInput v-model:value="model.code" :placeholder="$t('page.bi.models.model.form.code')" :disabled="isEdit" />
        </NFormItemGi>
        <NFormItemGi :span="3" :label="$t('page.bi.models.model.type')" path="type">
          <NSelect v-model:value="model.type" :options="TYPE_OPTIONS" />
        </NFormItemGi>

        <NFormItemGi :span="6" :label="$t('page.bi.models.model.displayName')" path="displayName">
          <NInput v-model:value="model.displayName" :placeholder="$t('page.bi.models.model.form.displayName')" />
        </NFormItemGi>
        <NFormItemGi :span="3" :label="$t('page.bi.models.model.contextWindow')" path="contextWindow">
          <NInputNumber v-model:value="model.contextWindow" :min="1" :step="1024" style="width: 100%" />
        </NFormItemGi>
        <NFormItemGi :span="3" :label="$t('page.bi.models.model.order')" path="order">
          <NInputNumber v-model:value="model.order" :min="0" style="width: 100%" />
        </NFormItemGi>

        <NFormItemGi :span="6" :label="$t('page.bi.models.model.inputPrice')" path="inputPrice">
          <NInputNumber
            v-model:value="model.inputPrice"
            :min="0"
            :precision="4"
            placeholder="元/千 token"
            style="width: 100%"
          />
        </NFormItemGi>
        <NFormItemGi :span="6" :label="$t('page.bi.models.model.outputPrice')" path="outputPrice">
          <NInputNumber
            v-model:value="model.outputPrice"
            :min="0"
            :precision="4"
            placeholder="元/千 token"
            style="width: 100%"
          />
        </NFormItemGi>

        <NFormItemGi :span="12" :label="$t('page.bi.models.model.capabilities')" path="capabilities">
          <NCheckboxGroup v-model:value="model.capabilities">
            <NSpace>
              <NCheckbox v-for="opt in CAPABILITY_OPTIONS" :key="opt.value" :value="opt.value" :label="opt.label" />
            </NSpace>
          </NCheckboxGroup>
        </NFormItemGi>

        <NFormItemGi :span="12" :label="$t('page.bi.models.model.defaultParams')" path="defaultParams">
          <NInput
            v-model:value="model.defaultParamsText"
            type="textarea"
            :rows="3"
            placeholder='e.g. {"temperature": 0.1, "top_p": 0.95}'
          />
        </NFormItemGi>

        <NFormItemGi :span="12" :label="$t('page.bi.models.model.remark')" path="remark">
          <NInput v-model:value="model.remark" type="textarea" :rows="2" />
        </NFormItemGi>

        <NFormItemGi :span="4" :label="$t('page.bi.models.model.isEnabled')" path="isEnabled">
          <NSwitch v-model:value="model.isEnabled" />
        </NFormItemGi>
        <NFormItemGi :span="4" :label="$t('page.bi.models.model.isDefault')" path="isDefault">
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
