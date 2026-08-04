<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { fetchAddBiMasking, fetchBiMasking, fetchUpdateBiMasking } from '@/service/api/bi-masking';
import { useFormRules, useNaiveForm } from '@/hooks/common/form';
import { $t } from '@/locales';

defineOptions({ name: 'BiMaskingOperateModal' });

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
    add: $t('page.bi.masking.create'),
    edit: $t('page.bi.masking.edit')
  };
  return titles[props.operateType];
});

const maskTypeOptions = computed(() => [
  { label: $t('page.bi.masking.maskTypes.phone'), value: 'phone' },
  { label: $t('page.bi.masking.maskTypes.idcard'), value: 'idcard' },
  { label: $t('page.bi.masking.maskTypes.email'), value: 'email' },
  { label: $t('page.bi.masking.maskTypes.bankcard'), value: 'bankcard' },
  { label: $t('page.bi.masking.maskTypes.custom'), value: 'custom' }
]);

function createDefaultModel(): Api.Bi.BiMaskingRuleOperateParams {
  return {
    name: '',
    columnPattern: '',
    maskType: 'phone',
    maskChar: '*',
    keepPrefix: 0,
    keepSuffix: 0,
    statusType: '1'
  };
}

const model = ref<Api.Bi.BiMaskingRuleOperateParams>(createDefaultModel());

type RuleKey = 'name' | 'columnPattern' | 'maskType';
const rules: Record<RuleKey, App.Global.FormRule> = {
  name: defaultRequiredRule,
  columnPattern: defaultRequiredRule,
  maskType: defaultRequiredRule
};

async function handleInitModel() {
  model.value = createDefaultModel();
  if (props.operateType === 'edit' && props.editingId) {
    const { data } = await fetchBiMasking(props.editingId);
    if (data) {
      const { name, columnPattern, maskType, maskChar, keepPrefix, keepSuffix, statusType } = data;
      Object.assign(model.value, {
        name,
        columnPattern,
        maskType,
        maskChar,
        keepPrefix,
        keepSuffix,
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
    const { error } = await fetchAddBiMasking(model.value);
    if (error) return;
    window.$message?.success($t('common.addSuccess'));
  } else {
    const { error } = await fetchUpdateBiMasking({ ...model.value, id: props.editingId ?? undefined });
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
          <NFormItemGi span="24 m:12" :label="$t('page.bi.masking.name')" path="name">
            <NInput v-model:value="model.name" :placeholder="$t('page.bi.masking.name')" />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.masking.maskType')" path="maskType">
            <NSelect
              v-model:value="model.maskType"
              :options="maskTypeOptions"
              :placeholder="$t('page.bi.masking.maskType')"
            />
          </NFormItemGi>
          <NFormItemGi span="24" :label="$t('page.bi.masking.columnPattern')" path="columnPattern">
            <NInput v-model:value="model.columnPattern" :placeholder="$t('page.bi.masking.columnPattern')" />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.masking.maskChar')" path="maskChar">
            <NInput v-model:value="model.maskChar" :placeholder="$t('page.bi.masking.maskChar')" />
          </NFormItemGi>
          <NFormItemGi span="24 m:6" :label="$t('page.bi.masking.keepPrefix')" path="keepPrefix">
            <NInputNumber v-model:value="model.keepPrefix" :min="0" class="w-full" />
          </NFormItemGi>
          <NFormItemGi span="24 m:6" :label="$t('page.bi.masking.keepSuffix')" path="keepSuffix">
            <NInputNumber v-model:value="model.keepSuffix" :min="0" class="w-full" />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.masking.status')" path="statusType">
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
