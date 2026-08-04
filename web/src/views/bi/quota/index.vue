<script setup lang="tsx">
import { computed, reactive } from 'vue';
import { NButton, NPopconfirm, NTag } from 'naive-ui';
import { statusTypeRecord } from '@/constants/business';
import { fetchBiQuotaList, fetchDeleteBiQuota } from '@/service/api/bi-quota';
import { useAppStore } from '@/store/modules/app';
import { defaultTransform, useNaivePaginatedTable, useTableOperate } from '@/hooks/common/table';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';
import QuotaOperateModal from './modules/quota-operate-modal.vue';

defineOptions({ name: 'BiQuota' });

const appStore = useAppStore();
const { hasAuth } = useAuth();

const searchParams = reactive<Api.Bi.BiQuotaConfigSearchParams>({
  current: 1,
  size: 10,
  name: null,
  scopeType: null,
  statusType: null
});

const scopeTypeOptions = computed(() => [
  { label: $t('page.bi.quota.scopeTypes.global'), value: 'global' },
  { label: $t('page.bi.quota.scopeTypes.user'), value: 'user' },
  { label: $t('page.bi.quota.scopeTypes.datasource'), value: 'datasource' }
]);

const scopeTypeLabel = (val: string | null) => {
  if (!val) return null;
  const opt = scopeTypeOptions.value.find(o => o.value === val);
  return opt ? opt.label : val;
};

const { columns, columnChecks, data, loading, getData, getDataByPage, mobilePagination } = useNaivePaginatedTable({
  api: () => fetchBiQuotaList(searchParams),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.current = params.page;
    searchParams.size = params.pageSize;
  },
  columns: () => [
    { type: 'selection', align: 'center', width: 48 },
    { key: 'index', title: $t('common.index'), width: 64, align: 'center', render: (_, index) => index + 1 },
    { key: 'name', title: $t('page.bi.quota.name'), minWidth: 140 },
    {
      key: 'scopeType',
      title: $t('page.bi.quota.scopeType'),
      align: 'center',
      minWidth: 110,
      render: row => {
        const label = scopeTypeLabel(row.scopeType);
        return label ? <NTag size="small">{label}</NTag> : null;
      }
    },
    {
      key: 'scopeId',
      title: $t('page.bi.quota.scopeId'),
      align: 'center',
      width: 100,
      render: row => (row.scopeId === null || row.scopeId === undefined ? '-' : row.scopeId)
    },
    { key: 'maxRows', title: $t('page.bi.quota.maxRows'), align: 'center', width: 110 },
    { key: 'timeoutSeconds', title: $t('page.bi.quota.timeoutSeconds'), align: 'center', width: 110 },
    { key: 'breakerThreshold', title: $t('page.bi.quota.breakerThreshold'), align: 'center', width: 110 },
    { key: 'breakerWindowSeconds', title: $t('page.bi.quota.breakerWindowSeconds'), align: 'center', width: 130 },
    {
      key: 'statusType',
      title: $t('page.bi.quota.status'),
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
      width: 180,
      render: row => (
        <div class="flex-center gap-8px">
          {hasAuth('B_BI_QUOTA_EDIT') && (
            <NButton type="primary" ghost size="small" onClick={() => edit(row.id)}>
              {$t('common.edit')}
            </NButton>
          )}
          {hasAuth('B_BI_QUOTA_DELETE') && (
            <NPopconfirm onPositiveClick={() => handleDelete(row.id)}>
              {{
                default: () => $t('page.bi.quota.confirmDelete'),
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
  const { error } = await fetchDeleteBiQuota({ id });
  if (!error) onDeleted();
}

function edit(id: string) {
  handleEdit(id);
}

function resetSearchParams() {
  Object.assign(searchParams, {
    current: 1,
    name: null,
    scopeType: null,
    statusType: null
  });
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <NCard :bordered="false" size="small" class="card-wrapper">
      <NCollapse :default-expanded-names="['quota-search']">
        <NCollapseItem :title="$t('common.search')" name="quota-search">
          <NForm :model="searchParams" label-placement="left" :label-width="80">
            <NGrid responsive="screen" item-responsive>
              <NFormItemGi span="24 s:12 m:6" :label="$t('page.bi.quota.name')" path="name" class="pr-24px">
                <NInput
                  v-model:value="searchParams.name"
                  clearable
                  :placeholder="$t('page.bi.quota.searchPlaceholder')"
                />
              </NFormItemGi>
              <NFormItemGi span="24 s:12 m:6" :label="$t('page.bi.quota.scopeType')" path="scopeType" class="pr-24px">
                <NSelect
                  v-model:value="searchParams.scopeType"
                  :options="scopeTypeOptions"
                  clearable
                  :placeholder="$t('page.bi.quota.scopeType')"
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
    <NCard :title="$t('page.bi.quota.title')" :bordered="false" size="small" class="card-wrapper sm:flex-1-hidden">
      <template #header-extra>
        <TableHeaderOperation v-model:columns="columnChecks" :loading="loading" @refresh="getData">
          <NButton v-if="hasAuth('B_BI_QUOTA_CREATE')" size="small" ghost type="primary" @click="handleAdd">
            <template #icon><icon-ic-round-plus class="text-icon" /></template>
            {{ $t('page.bi.quota.create') }}
          </NButton>
        </TableHeaderOperation>
      </template>
      <NDataTable
        v-model:checked-row-keys="checkedRowKeys"
        :columns="columns"
        :data="data"
        size="small"
        :flex-height="!appStore.isMobile"
        :scroll-x="1200"
        :loading="loading"
        remote
        :row-key="row => row.id"
        :pagination="mobilePagination"
        class="sm:h-full"
      />
      <QuotaOperateModal
        v-model:visible="drawerVisible"
        :operate-type="operateType"
        :editing-id="editingData?.id ?? null"
        @submitted="getData"
      />
    </NCard>
  </div>
</template>
