<script setup lang="tsx">
import { computed, ref, watch } from 'vue';
import { NButton, NCard, NEmpty, NPopconfirm, NSelect, NSpace, NSwitch, NTag } from 'naive-ui';
import {
  fetchBiModelList,
  fetchBiModelProviderList,
  fetchDeleteBiModel,
  fetchDeleteBiModelProvider,
  fetchTestBiModelProvider,
  fetchUpdateBiModelProvider
} from '@/service/api';
import { defaultTransform, useNaivePaginatedTable } from '@/hooks/common/table';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';
import ModelProviderOperateModal from './modules/provider-operate-modal.vue';
import BiModelOperateModal from './modules/model-operate-modal.vue';

const { hasAuth } = useAuth();

const PAGE_SIZE = 50;

// ===== 提供商 =====
const providerSearch = ref<Api.Bi.ModelProviderSearchParams>({
  current: 1,
  size: PAGE_SIZE,
  name: null,
  code: null,
  type: null,
  isEnabled: null
});

const {
  columns: providerColumns,
  data: providerData,
  loading: providerLoading,
  getData: getProviderData
} = useNaivePaginatedTable({
  api: () => fetchBiModelProviderList(providerSearch.value),
  transform: response => defaultTransform(response),
  showTotal: false,
  initialPageSize: PAGE_SIZE,
  onPaginationParamsChange: params => {
    providerSearch.value.current = params.page ?? 1;
    providerSearch.value.size = params.pageSize ?? PAGE_SIZE;
  },
  columns: () => [
    {
      key: 'index',
      title: '#',
      width: 48,
      render: (_, index) => index + 1
    },
    {
      key: 'name',
      title: $t('page.bi.models.provider.name'),
      minWidth: 140,
      render: row => (
        <NSpace align="center" size={4}>
          <span>{row.name}</span>
          {row.isDefault && <NTag type="primary" size="small">Default</NTag>}
        </NSpace>
      )
    },
    {
      key: 'code',
      title: $t('page.bi.models.provider.code'),
      width: 110
    },
    {
      key: 'type',
      title: $t('page.bi.models.provider.type'),
      width: 130,
      render: row => $t(`page.bi.models.provider.typeLabel.${row.type}`)
    },
    {
      key: 'baseUrl',
      title: $t('page.bi.models.provider.baseUrl'),
      minWidth: 200,
      render: row => row.baseUrl ?? '-'
    },
    {
      key: 'apiKeyMasked',
      title: $t('page.bi.models.provider.apiKeyMasked'),
      width: 180,
      render: row => row.apiKeyMasked ?? '-'
    },
    {
      key: 'modelCount',
      title: $t('page.bi.models.provider.modelCount'),
      width: 80,
      render: row => row.modelCount
    },
    {
      key: 'isEnabled',
      title: $t('page.bi.models.provider.isEnabled'),
      width: 80,
      render: row => (
        <NSwitch
          value={row.isEnabled}
          size="small"
          onUpdateValue={async (val: boolean) => {
            const { error } = await fetchUpdateBiModelProvider(row.id, { isEnabled: val });
            if (!error) {
              window.$message?.success($t('common.updateSuccess'));
              getProviderData();
            }
          }}
        />
      )
    },
    {
      key: 'isDefault',
      title: $t('page.bi.models.provider.isDefault'),
      width: 80,
      render: row => (
        <NSwitch
          value={row.isDefault}
          size="small"
          onUpdateValue={async (val: boolean) => {
            const { error } = await fetchUpdateBiModelProvider(row.id, { isDefault: val });
            if (error) {
              window.$message?.error(String(error));
            } else {
              window.$message?.success($t('common.updateSuccess'));
              getProviderData();
            }
          }}
        />
      )
    },
    {
      key: 'lastTestOk',
      title: $t('page.bi.models.provider.lastTestOk'),
      width: 100,
      render: row => {
        if (row.lastTestOk === null || row.lastTestOk === undefined) {
          return <span class="text-gray-400">{row.lastTestedAt ? $t('page.bi.models.provider.lastTestOkLabel.null') : '-'}</span>;
        }
        const key = String(row.lastTestOk) as 'true' | 'false';
        return <NTag type={row.lastTestOk ? 'success' : 'error'} size="small">{$t(`page.bi.models.provider.lastTestOkLabel.${key}`)}</NTag>;
      }
    },
    {
      key: 'op',
      title: $t('common.action'),
      width: 320,
      fixed: 'right',
      render: row => (
        <NSpace size={8}>
          {hasAuth('B_BI_MODEL_PROVIDER_TEST') && (
            <NButton size="tiny" onClick={() => handleTest(row)}>
              {$t('page.bi.models.provider.test')}
            </NButton>
          )}
          {hasAuth('B_BI_MODEL_PROVIDER_UPDATE') && (
            <NButton size="tiny" onClick={() => handleEditProvider(row)}>
              {$t('common.modify')}
            </NButton>
          )}
          {hasAuth('B_BI_MODEL_PROVIDER_DELETE') && (
            <NPopconfirm onPositiveClick={() => handleDeleteProvider(row)}>
              {{
                trigger: () => (
                  <NButton size="tiny" type="error" ghost>
                    {$t('common.delete')}
                  </NButton>
                ),
                default: () => $t('common.confirmDelete')
              }}
            </NPopconfirm>
          )}
        </NSpace>
      )
    }
  ]
});

// ===== 模型 =====
const modelSearch = ref<Api.Bi.BiModelSearchParams>({
  current: 1,
  size: PAGE_SIZE,
  providerId: null,
  code: null,
  type: null,
  isEnabled: null
});

const {
  columns: modelColumns,
  data: modelData,
  loading: modelLoading,
  getData: getModelData
} = useNaivePaginatedTable({
  api: () => fetchBiModelList(modelSearch.value),
  transform: response => defaultTransform(response),
  showTotal: false,
  initialPageSize: PAGE_SIZE,
  onPaginationParamsChange: params => {
    modelSearch.value.current = params.page ?? 1;
    modelSearch.value.size = params.pageSize ?? PAGE_SIZE;
  },
  columns: () => [
    {
      key: 'index',
      title: '#',
      width: 48,
      render: (_, index) => index + 1
    },
    {
      key: 'providerName',
      title: $t('page.bi.models.model.provider'),
      minWidth: 140,
      render: row => row.providerName ?? row.providerCode ?? '-'
    },
    {
      key: 'code',
      title: $t('page.bi.models.model.code'),
      minWidth: 160,
      render: row => (
        <NSpace align="center" size={4}>
          <span>{row.code}</span>
          {row.isDefault && <NTag type="primary" size="small">Default</NTag>}
        </NSpace>
      )
    },
    {
      key: 'displayName',
      title: $t('page.bi.models.model.displayName'),
      minWidth: 120,
      render: row => row.displayName ?? '-'
    },
    {
      key: 'type',
      title: $t('page.bi.models.model.type'),
      width: 90,
      render: row => $t(`page.bi.models.model.typeLabel.${row.type}`)
    },
    {
      key: 'contextWindow',
      title: $t('page.bi.models.model.contextWindow'),
      width: 110,
      render: row => row.contextWindow.toLocaleString()
    },
    {
      key: 'isEnabled',
      title: $t('page.bi.models.model.isEnabled'),
      width: 80,
      render: row => (row.isEnabled ? $t('common.yesOrNo.yes') : $t('common.yesOrNo.no'))
    },
    {
      key: 'op',
      title: $t('common.action'),
      width: 200,
      fixed: 'right',
      render: row => (
        <NSpace size={8}>
          {hasAuth('B_BI_MODEL_UPDATE') && (
            <NButton size="tiny" onClick={() => handleEditModel(row)}>
              {$t('common.modify')}
            </NButton>
          )}
          {hasAuth('B_BI_MODEL_DELETE') && (
            <NPopconfirm onPositiveClick={() => handleDeleteModel(row)}>
              {{
                trigger: () => (
                  <NButton size="tiny" type="error" ghost>
                    {$t('common.delete')}
                  </NButton>
                ),
                default: () => $t('common.confirmDelete')
              }}
            </NPopconfirm>
          )}
        </NSpace>
      )
    }
  ]
});

// ===== 表单 / 操作 =====
const providerModalRef = ref<InstanceType<typeof ModelProviderOperateModal> | null>(null);
const modelModalRef = ref<InstanceType<typeof BiModelOperateModal> | null>(null);
const editingProvider = ref<Api.Bi.ModelProvider | null>(null);
const editingModel = ref<Api.Bi.BiModel | null>(null);

function handleAddProvider() {
  editingProvider.value = null;
  providerModalRef.value?.open();
}

function handleEditProvider(row: Api.Bi.ModelProvider) {
  editingProvider.value = row;
  providerModalRef.value?.open(row);
}

function handleAddModel() {
  if (!providerData.value || providerData.value.length === 0) {
    window.$message?.warning($t('page.bi.models.model.form.provider'));
    return;
  }
  editingModel.value = null;
  modelModalRef.value?.open();
}

function handleEditModel(row: Api.Bi.BiModel) {
  editingModel.value = row;
  modelModalRef.value?.open(row);
}

async function handleDeleteProvider(row: Api.Bi.ModelProvider) {
  const { error } = await fetchDeleteBiModelProvider(row.id);
  if (!error) {
    window.$message?.success($t('common.deleteSuccess'));
    getProviderData();
    getModelData();
  }
}

async function handleDeleteModel(row: Api.Bi.BiModel) {
  const { error } = await fetchDeleteBiModel(row.id);
  if (!error) {
    window.$message?.success($t('common.deleteSuccess'));
    getModelData();
  }
}

async function handleTest(row: Api.Bi.ModelProvider) {
  const { data, error } = await fetchTestBiModelProvider(row.id);
  if (error) return;
  if (data?.ok) {
    window.$message?.success(`${$t('page.bi.models.provider.testOk')}${data.model ? ` (${data.model})` : ''}`);
  } else {
    window.$message?.error($t('page.bi.models.provider.testFailed', { msg: data?.error ?? '-' }));
  }
  // 刷新 provider 列表更新 lastTestedAt/lastTestOk
  getProviderData();
}

function onProviderSubmitted() {
  getProviderData();
  getModelData();
}

function onModelSubmitted() {
  getModelData();
}

// ===== 筛选 =====
const providerOptions = computed(() =>
  (providerData.value ?? []).map(p => ({
    label: p.name,
    value: p.id
  }))
);

const filterProviderId = ref<string | null>(null);
watch(filterProviderId, val => {
  modelSearch.value.providerId = val ?? null;
  modelSearch.value.current = 1;
  getModelData();
});
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-12px">
    <!-- 提供商 -->
    <NCard :bordered="false" size="small" class="card-wrapper" :title="$t('page.bi.models.provider.title')">
      <template #header-extra>
        <NSpace>
          <NButton v-if="hasAuth('B_BI_MODEL_PROVIDER_CREATE')" type="primary" @click="handleAddProvider">
            {{ $t('page.bi.models.provider.add') }}
          </NButton>
        </NSpace>
      </template>

      <NEmpty
        v-if="!providerLoading && !(providerData && providerData.length)"
        :description="$t('page.bi.models.provider.empty')"
      />

      <NDataTable
        v-else
        :columns="providerColumns"
        :data="providerData || []"
        :loading="providerLoading"
        :row-key="row => row.id"
        size="small"
        :scroll-x="1400"
        :pagination="false"
      />
    </NCard>

    <!-- 模型 -->
    <NCard :bordered="false" size="small" class="card-wrapper" :title="$t('page.bi.models.model.title')">
      <template #header-extra>
        <NSpace>
          <NSelect
            v-model:value="filterProviderId"
            :options="providerOptions"
            :placeholder="$t('page.bi.models.model.provider')"
            clearable
            style="width: 240px"
            value-field="value"
            label-field="label"
            @update:value="filterProviderId = $event"
          />
          <NButton v-if="hasAuth('B_BI_MODEL_CREATE')" type="primary" @click="handleAddModel">
            {{ $t('page.bi.models.model.add') }}
          </NButton>
        </NSpace>
      </template>

      <NEmpty
        v-if="!modelLoading && !(modelData && modelData.length)"
        :description="$t('page.bi.models.model.empty')"
      />

      <NDataTable
        v-else
        :columns="modelColumns"
        :data="modelData || []"
        :loading="modelLoading"
        :row-key="row => row.id"
        size="small"
        :scroll-x="1000"
        :pagination="false"
      />
    </NCard>

    <ModelProviderOperateModal ref="providerModalRef" :editing="editingProvider" @submitted="onProviderSubmitted" />
    <BiModelOperateModal
      ref="modelModalRef"
      :editing="editingModel"
      :providers="providerData || []"
      @submitted="onModelSubmitted"
    />
  </div>
</template>
