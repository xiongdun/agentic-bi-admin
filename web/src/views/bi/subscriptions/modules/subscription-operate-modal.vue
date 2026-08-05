<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { fetchAddBiSubscription, fetchBiSubscription, fetchUpdateBiSubscription } from '@/service/api/bi-subscription';
import { fetchBiDashboardList } from '@/service/api/bi-dashboard';
import { useFormRules, useNaiveForm } from '@/hooks/common/form';
import { $t } from '@/locales';

defineOptions({ name: 'BiSubscriptionOperateModal' });

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
    add: $t('page.bi.subscription.create'),
    edit: $t('page.bi.subscription.edit')
  };
  return titles[props.operateType];
});

const dashboardOptions = ref<{ label: string; value: string }[]>([]);
const dashboardLoading = ref(false);

async function loadDashboards() {
  dashboardLoading.value = true;
  try {
    const { data } = await fetchBiDashboardList({ current: 1, size: 200 });
    if (data?.records) {
      dashboardOptions.value = data.records.map(d => ({ label: d.name, value: d.id }));
    }
  } finally {
    dashboardLoading.value = false;
  }
}

function createDefaultModel(): Api.Bi.BiSubscriptionOperateParams {
  return {
    name: '',
    dashboardId: '',
    cronExpr: '0 9 * * *',
    statusType: '1'
  };
}

const model = ref<Api.Bi.BiSubscriptionOperateParams>(createDefaultModel());

type RuleKey = 'name' | 'dashboardId' | 'cronExpr';
const rules: Record<RuleKey, App.Global.FormRule> = {
  name: defaultRequiredRule,
  dashboardId: defaultRequiredRule,
  cronExpr: defaultRequiredRule
};

function applyPreset(preset: 'hourly' | 'daily' | 'weekly') {
  const presets: Record<typeof preset, string> = {
    hourly: '0 * * * *',
    daily: '0 9 * * *',
    weekly: '0 9 * * 1'
  };
  model.value.cronExpr = presets[preset];
}

async function handleInitModel() {
  model.value = createDefaultModel();
  await loadDashboards();
  if (props.operateType === 'edit' && props.editingId) {
    const { data } = await fetchBiSubscription(props.editingId);
    if (data) {
      const { name, dashboardId, cronExpr, statusType } = data;
      Object.assign(model.value, {
        name,
        dashboardId,
        cronExpr,
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
    const { error } = await fetchAddBiSubscription(model.value);
    if (error) return;
    window.$message?.success($t('common.addSuccess'));
  } else {
    const { error } = await fetchUpdateBiSubscription({ ...model.value, id: props.editingId ?? undefined });
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
  <NModal v-model:show="visible" :title="title" preset="card" class="w-600px">
    <NScrollbar class="h-460px pr-20px">
      <NForm ref="formRef" :model="model" :rules="rules" label-placement="left" :label-width="110">
        <NGrid responsive="screen" item-responsive>
          <NFormItemGi span="24" :label="$t('page.bi.subscription.name')" path="name">
            <NInput
              v-model:value="model.name"
              :placeholder="$t('page.bi.subscription.name')"
              maxlength="100"
              show-count
            />
          </NFormItemGi>
          <NFormItemGi span="24" :label="$t('page.bi.subscription.dashboard')" path="dashboardId">
            <NSelect
              v-model:value="model.dashboardId"
              :options="dashboardOptions"
              :loading="dashboardLoading"
              filterable
              :placeholder="$t('page.bi.subscription.dashboard')"
            />
          </NFormItemGi>
          <NFormItemGi span="24" :label="$t('page.bi.subscription.cronExpr')" path="cronExpr">
            <NInput v-model:value="model.cronExpr" :placeholder="$t('page.bi.subscription.cronHint')" />
            <NSpace class="mt-8px" :size="4">
              <NButton size="tiny" @click="applyPreset('hourly')">
                {{ $t('page.bi.subscription.cronPresets.hourly') }}
              </NButton>
              <NButton size="tiny" @click="applyPreset('daily')">
                {{ $t('page.bi.subscription.cronPresets.daily') }}
              </NButton>
              <NButton size="tiny" @click="applyPreset('weekly')">
                {{ $t('page.bi.subscription.cronPresets.weekly') }}
              </NButton>
            </NSpace>
            <p class="mt-4px text-12px text-gray-400">{{ $t('page.bi.subscription.cronHint') }}</p>
          </NFormItemGi>
          <NFormItemGi span="24" :label="$t('page.bi.subscription.status')" path="statusType">
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
