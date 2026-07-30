<script setup lang="tsx">
import { computed, reactive, ref } from 'vue';
import { NButton, NPopconfirm, NTag } from 'naive-ui';
import { statusTypeRecord } from '@/constants/business';
import { fetchBiLLMProviderList, fetchDeleteBiLLMProvider, fetchTestBiLLMProvider } from '@/service/api/bi-llm';
import { useAppStore } from '@/store/modules/app';
import { defaultTransform, useNaivePaginatedTable, useTableOperate } from '@/hooks/common/table';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';
import ProviderOperateModal from './modules/provider-operate-modal.vue';

defineOptions({ name: 'BiModels' });

const appStore = useAppStore();
const { hasAuth } = useAuth();

const searchParams = reactive<Api.Bi.BiLLMProviderSearchParams>({
  current: 1,
  size: 10,
  name: null,
  providerType: null,
  statusType: null,
  isDefault: null
});

const providerTypeOptions = computed(() => [
  { label: $t('page.bi.models.providerTypes.deepseek'), value: 'deepseek' },
  { label: $t('page.bi.models.providerTypes.ollama'), value: 'ollama' },
  { label: $t('page.bi.models.providerTypes.qwen'), value: 'qwen' },
  { label: $t('page.bi.models.providerTypes.openai'), value: 'openai' },
  { label: $t('page.bi.models.providerTypes.mock'), value: 'mock' },
  { label: $t('page.bi.models.providerTypes.custom'), value: 'custom' }
]);

const providerTypeLabel = (val: Api.Bi.LLMProviderType) => {
  const opt = providerTypeOptions.value.find(o => o.value === val);
  return opt ? opt.label : val;
};

const testingId = ref<string | null>(null);

const { columns, columnChecks, data, loading, getData, getDataByPage, mobilePagination } = useNaivePaginatedTable({
  api: () => fetchBiLLMProviderList(searchParams),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.current = params.page;
    searchParams.size = params.pageSize;
  },
  columns: () => [
    { type: 'selection', align: 'center', width: 48 },
    { key: 'index', title: $t('common.index'), width: 64, align: 'center', render: (_, index) => index + 1 },
    { key: 'name', title: $t('page.bi.models.providerName'), minWidth: 140 },
    {
      key: 'providerType',
      title: $t('page.bi.models.providerType'),
      align: 'center',
      minWidth: 110,
      render: row => <NTag size="small">{providerTypeLabel(row.providerType)}</NTag>
    },
    { key: 'baseUrl', title: $t('page.bi.models.baseUrl'), minWidth: 180 },
    { key: 'defaultModel', title: $t('page.bi.models.defaultModel'), align: 'center', minWidth: 140 },
    {
      key: 'isDefault',
      title: $t('page.bi.models.isDefault'),
      align: 'center',
      width: 100,
      render: row => (row.isDefault ? <NTag type="success" size="small">{$t('common.yesOrNo.yes')}</NTag> : null)
    },
    {
      key: 'statusType',
      title: $t('page.bi.audit.status'),
      align: 'center',
      width: 90,
      render: row => {
        if (row.statusType === null) return null;
        const tagMap: Record<Api.Common.EnableStatus, NaiveUI.ThemeColor> = { '1': 'success', '2': 'warning' };
        return <NTag type={tagMap[row.statusType]}>{$t(statusTypeRecord[row.statusType])}</NTag>;
      }
    },
    {
      key: 'operate',
      title: $t('common.operate'),
      align: 'center',
      width: 240,
      render: row => (
        <div class="flex-center gap-8px">
          {hasAuth('B_BI_MODEL_PROVIDER_TEST') && (
            <NButton type="info" ghost size="small" loading={testingId.value === row.id} onClick={() => handleTest(row.id)}>
              {$t('page.bi.models.testProvider')}
            </NButton>
          )}
          {hasAuth('B_BI_MODEL_PROVIDER_EDIT') && (
            <NButton type="primary" ghost size="small" onClick={() => edit(row.id)}>
              {$t('common.edit')}
            </NButton>
          )}
          {hasAuth('B_BI_MODEL_PROVIDER_DELETE') && (
            <NPopconfirm onPositiveClick={() => handleDelete(row.id)}>
              {{
                default: () => $t('page.bi.models.deleteProviderConfirm'),
                trigger: () => (
                  <NButton type="error" ghost size="small">
                    {$t('common.delete')}
                  </NButton>
                )
              }}
            </NPopconfirm>
          )}
        </div>
      )
    }
  ]
});

const { drawerVisible, operateType, editingData, handleAdd, handleEdit, checkedRowKeys, onDeleted } = useTableOperate(
  data,
  'id',
  getData
);

async function handleDelete(id: string) {
  const { error } = await fetchDeleteBiLLMProvider({ id });
  if (!error) onDeleted();
}

function edit(id: string) {
  handleEdit(id);
}

async function handleTest(id: string) {
  testingId.value = id;
  const { data: result, error } = await fetchTestBiLLMProvider(id);
  testingId.value = null;
  if (error) return;
  if (result.success) {
    window.$message?.success(
      `${$t('page.bi.models.testResult')}: ${result.message} (${result.modelName || '-'} / ${result.elapsedMs}ms)`
    );
  } else {
    window.$message?.error(`${$t('page.bi.models.testResult')}: ${result.message}`);
  }
}

function resetSearchParams() {
  Object.assign(searchParams, {
    current: 1,
    name: null,
    providerType: null,
    statusType: null,
    isDefault: null
  });
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <NCard :bordered="false" size="small" class="card-wrapper">
      <NCollapse :default-expanded-names="['provider-search']">
        <NCollapseItem :title="$t('common.search')" name="provider-search">
          <NForm :model="searchParams" label-placement="left" :label-width="90">
            <NGrid responsive="screen" item-responsive>
              <NFormItemGi span="24 s:12 m:6" :label="$t('page.bi.models.providerName')" path="name" class="pr-24px">
                <NInput
                  v-model:value="searchParams.name"
                  clearable
                  :placeholder="$t('page.bi.models.form.providerName')"
                />
              </NFormItemGi>
              <NFormItemGi
                span="24 s:12 m:6"
                :label="$t('page.bi.models.providerType')"
                path="providerType"
                class="pr-24px"
              >
                <NSelect
                  v-model:value="searchParams.providerType"
                  :options="providerTypeOptions"
                  clearable
                  :placeholder="$t('page.bi.models.form.providerType')"
                />
              </NFormItemGi>
              <NFormItemGi span="24 s:12 m:6" :label="$t('page.bi.audit.status')" path="statusType" class="pr-24px">
                <NSelect
                  v-model:value="searchParams.statusType"
                  :options="[
                    { label: $t('page.manage.common.statusType.enable'), value: '1' },
                    { label: $t('page.manage.common.statusType.disable'), value: '2' }
                  ]"
                  clearable
                  :placeholder="$t('page.bi.models.form.statusType')"
                />
              </NFormItemGi>
              <NFormItemGi span="24 s:12 m:6">
                <NSpace class="w-full" justify="end">
                  <NButton @click="resetSearchParams">
                    <template #icon><icon-ic-round-refresh class="text-icon" /></template>
                    {{ $t('common.reset') }}
                  </NButton>
                  <NButton type="primary" ghost @click="getDataByPage(1)">
                    <template #icon><icon-ic-round-search class="text-icon" /></template>
                    {{ $t('common.search') }}
                  </NButton>
                </NSpace>
              </NFormItemGi>
            </NGrid>
          </NForm>
        </NCollapseItem>
      </NCollapse>
    </NCard>
    <NCard
      :title="$t('page.bi.models.providerList')"
      :bordered="false"
      size="small"
      class="card-wrapper sm:flex-1-hidden"
    >
      <template #header-extra>
        <TableHeaderOperation v-model:columns="columnChecks" :loading="loading" @refresh="getData">
          <NButton v-if="hasAuth('B_BI_MODEL_PROVIDER_CREATE')" size="small" ghost type="primary" @click="handleAdd">
            <template #icon><icon-ic-round-plus class="text-icon" /></template>
            {{ $t('page.bi.models.createProvider') }}
          </NButton>
        </TableHeaderOperation>
      </template>
      <NDataTable
        v-model:checked-row-keys="checkedRowKeys"
        :columns="columns"
        :data="data"
        size="small"
        :flex-height="!appStore.isMobile"
        :scroll-x="1100"
        :loading="loading"
        remote
        :row-key="row => row.id"
        :pagination="mobilePagination"
        class="sm:h-full"
      />
      <ProviderOperateModal
        v-model:visible="drawerVisible"
        :operate-type="operateType"
        :row-data="editingData"
        @submitted="getDataByPage"
      />
    </NCard>
  </div>
</template>
