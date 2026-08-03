<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { statusTypeOptions } from '@/constants/business';
import { fetchAddBiLLMProvider, fetchBiLLMProvider, fetchUpdateBiLLMProvider } from '@/service/api/bi-llm';
import { useFormRules, useNaiveForm } from '@/hooks/common/form';
import { $t } from '@/locales';

defineOptions({ name: 'ProviderOperateModal' });

interface Props {
  operateType: NaiveUI.TableOperateType;
  rowData?: Api.Bi.BiLLMProvider | null;
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
    add: $t('page.bi.models.createProvider'),
    edit: $t('page.bi.models.editProvider')
  };
  return titles[props.operateType];
});

const isEdit = computed(() => props.operateType === 'edit');

const providerTypeOptions = computed(() => [
  { label: $t('page.bi.models.providerTypes.deepseek'), value: 'deepseek' },
  { label: $t('page.bi.models.providerTypes.ollama'), value: 'ollama' },
  { label: $t('page.bi.models.providerTypes.qwen'), value: 'qwen' },
  { label: $t('page.bi.models.providerTypes.openai'), value: 'openai' },
  { label: $t('page.bi.models.providerTypes.mock'), value: 'mock' },
  { label: $t('page.bi.models.providerTypes.custom'), value: 'custom' }
]);

interface ProviderModel {
  id?: string;
  name: string;
  providerType: Api.Bi.LLMProviderType;
  apiKey: string;
  baseUrl: string | null;
  defaultModel: string | null;
  isDefault: boolean;
  statusType: Api.Common.EnableStatus;
  extraConfig: Record<string, any> | null;
}

function createDefaultModel(): ProviderModel {
  return {
    name: '',
    providerType: 'deepseek',
    apiKey: '',
    baseUrl: null,
    defaultModel: null,
    isDefault: false,
    statusType: '1',
    extraConfig: null
  };
}

const model = ref<ProviderModel>(createDefaultModel());
const extraConfigText = ref('');

type RuleKey = 'name' | 'providerType';
const rules: Record<RuleKey, App.Global.FormRule> = {
  name: defaultRequiredRule,
  providerType: defaultRequiredRule
};

const apiKeyRules = computed<App.Global.FormRule[]>(() => {
  return isEdit.value ? [] : [defaultRequiredRule];
});

async function handleInitModel() {
  model.value = createDefaultModel();
  extraConfigText.value = '';
  if (isEdit.value && props.rowData) {
    const { data } = await fetchBiLLMProvider(props.rowData.id);
    if (data) {
      const { id, name, providerType, baseUrl, defaultModel, isDefault, statusType, extraConfig } = data;
      Object.assign(model.value, {
        id,
        name,
        providerType,
        apiKey: '',
        baseUrl,
        defaultModel,
        isDefault,
        statusType,
        extraConfig
      });
      extraConfigText.value = extraConfig ? JSON.stringify(extraConfig, null, 2) : '';
    }
  }
}

function closeModal() {
  visible.value = false;
}

async function handleSubmit() {
  await validate();

  let parsedExtraConfig: Record<string, any> | null = null;
  const text = extraConfigText.value.trim();
  if (text) {
    try {
      parsedExtraConfig = JSON.parse(text);
    } catch {
      window.$message?.error($t('common.pleaseCheckValue'));
      return;
    }
  }

  if (isEdit.value) {
    const payload: Api.Bi.BiLLMProviderOperateParams = {
      id: model.value.id,
      name: model.value.name,
      providerType: model.value.providerType,
      baseUrl: model.value.baseUrl,
      defaultModel: model.value.defaultModel,
      isDefault: model.value.isDefault,
      statusType: model.value.statusType,
      extraConfig: parsedExtraConfig
    };
    if (model.value.apiKey.trim() !== '') {
      payload.apiKey = model.value.apiKey;
    }
    const { error } = await fetchUpdateBiLLMProvider(payload);
    if (error) return;
    window.$message?.success($t('common.updateSuccess'));
  } else {
    const payload: Api.Bi.BiLLMProviderOperateParams = {
      name: model.value.name,
      providerType: model.value.providerType,
      apiKey: model.value.apiKey,
      baseUrl: model.value.baseUrl,
      defaultModel: model.value.defaultModel,
      isDefault: model.value.isDefault,
      statusType: model.value.statusType,
      extraConfig: parsedExtraConfig
    };
    const { error } = await fetchAddBiLLMProvider(payload);
    if (error) return;
    window.$message?.success($t('common.addSuccess'));
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
  <NModal v-model:show="visible" :title="title" preset="card" class="w-720px">
    <NScrollbar class="h-520px pr-20px">
      <NForm ref="formRef" :model="model" :rules="rules" label-placement="left" :label-width="110">
        <NGrid responsive="screen" item-responsive>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.models.providerName')" path="name">
            <NInput v-model:value="model.name" :placeholder="$t('page.bi.models.form.providerName')" />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.models.providerType')" path="providerType">
            <NSelect
              v-model:value="model.providerType"
              :options="providerTypeOptions"
              :placeholder="$t('page.bi.models.form.providerType')"
            />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.models.apiKey')" path="apiKey" :rule="apiKeyRules">
            <NInput
              v-model:value="model.apiKey"
              type="password"
              show-password-on="click"
              :placeholder="isEdit ? $t('page.bi.models.apiKeyHint') : $t('page.bi.models.form.apiKey')"
            />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.models.baseUrl')" path="baseUrl">
            <NInput v-model:value="model.baseUrl" :placeholder="$t('page.bi.models.form.baseUrl')" />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.models.defaultModel')" path="defaultModel">
            <NInput v-model:value="model.defaultModel" :placeholder="$t('page.bi.models.form.defaultModel')" />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.models.isDefault')" path="isDefault">
            <NSwitch v-model:value="model.isDefault" />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.audit.status')" path="statusType">
            <NRadioGroup v-model:value="model.statusType">
              <NRadio v-for="item in statusTypeOptions" :key="item.value" :value="item.value" :label="$t(item.label)" />
            </NRadioGroup>
          </NFormItemGi>
          <NFormItemGi span="24" label="Extra Config" path="extraConfig">
            <NInput
              v-model:value="extraConfigText"
              type="textarea"
              :rows="4"
              placeholder="{&quot;temperature&quot;: 0.7, &quot;maxTokens&quot;: 2048}"
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
