<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { fetchAddBiQuota, fetchBiQuota, fetchUpdateBiQuota } from '@/service/api/bi-quota';
import { useFormRules, useNaiveForm } from '@/hooks/common/form';
import { $t } from '@/locales';

defineOptions({ name: 'BiQuotaOperateModal' });

interface Props {
  operateType: 'add' | 'edit';
  editingId?: string | null;
}

const props = defineProps<Props>();

const emit = defineEmits<{ submitted: [] }>();

const visible = defineModel<boolean>('visible');
const { formRef, validate, restoreValidation } = useNaiveForm();
const { defaultRequiredRule } = useFormRules();

const title = computed(() => {
  const titles: Record<'add' | 'edit', string> = {
    add: $t('page.bi.quota.create'),
    edit: $t('page.bi.quota.edit')
  };
  return titles[props.operateType];
});

const scopeTypeOptions = computed(() => [
  { label: $t('page.bi.quota.scopeTypes.global'), value: 'global' },
  { label: $t('page.bi.quota.scopeTypes.user'), value: 'user' },
  { label: $t('page.bi.quota.scopeTypes.datasource'), value: 'datasource' }
]);

function createDefaultModel(): Api.Bi.BiQuotaConfigOperateParams {
  return {
    name: '',
    maxRows: 10000,
    timeoutSeconds: 30,
    breakerThreshold: 10,
    breakerWindowSeconds: 60,
    scopeType: 'global',
    scopeId: null,
    statusType: '1'
  };
}

const model = ref<Api.Bi.BiQuotaConfigOperateParams>(createDefaultModel());

type RuleKey = 'name' | 'scopeType';
const rules: Record<RuleKey, App.Global.FormRule> = {
  name: defaultRequiredRule,
  scopeType: defaultRequiredRule
};

async function handleInitModel() {
  model.value = createDefaultModel();
  if (props.operateType === 'edit' && props.editingId) {
    const { data } = await fetchBiQuota(props.editingId);
    if (data) {
      const { name, maxRows, timeoutSeconds, breakerThreshold, breakerWindowSeconds, scopeType, scopeId, statusType } =
        data;
      Object.assign(model.value, {
        name,
        maxRows,
        timeoutSeconds,
        breakerThreshold,
        breakerWindowSeconds,
        scopeType,
        scopeId,
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
  const payload: Api.Bi.BiQuotaConfigOperateParams = {
    ...model.value,
    scopeId: model.value.scopeType === 'global' ? null : model.value.scopeId
  };
  if (props.operateType === 'add') {
    const { error } = await fetchAddBiQuota(payload);
    if (error) return;
    window.$message?.success($t('common.addSuccess'));
  } else {
    const { error } = await fetchUpdateBiQuota({ ...payload, id: props.editingId ?? undefined });
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
      <NForm ref="formRef" :model="model" :rules="rules" label-placement="left" :label-width="120">
        <NGrid responsive="screen" item-responsive>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.quota.name')" path="name">
            <NInput v-model:value="model.name" :placeholder="$t('page.bi.quota.name')" />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.quota.scopeType')" path="scopeType">
            <NSelect
              v-model:value="model.scopeType"
              :options="scopeTypeOptions"
              :placeholder="$t('page.bi.quota.scopeType')"
            />
          </NFormItemGi>
          <NFormItemGi
            v-if="model.scopeType !== 'global'"
            span="24 m:12"
            :label="$t('page.bi.quota.scopeId')"
            path="scopeId"
          >
            <NInputNumber v-model:value="model.scopeId" :min="0" class="w-full" />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.quota.maxRows')" path="maxRows">
            <NInputNumber v-model:value="model.maxRows" :min="1" class="w-full" />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.quota.timeoutSeconds')" path="timeoutSeconds">
            <NInputNumber v-model:value="model.timeoutSeconds" :min="1" class="w-full" />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.quota.breakerThreshold')" path="breakerThreshold">
            <NInputNumber v-model:value="model.breakerThreshold" :min="1" class="w-full" />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.quota.breakerWindowSeconds')" path="breakerWindowSeconds">
            <NInputNumber v-model:value="model.breakerWindowSeconds" :min="1" class="w-full" />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.quota.status')" path="statusType">
            <NSwitch v-model:value="model.statusType" checked-value="1" unchecked-value="2" />
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
