<script setup lang="tsx">
import { computed, reactive } from 'vue';
import { NButton, NPopconfirm, NTag } from 'naive-ui';
import { statusTypeRecord } from '@/constants/business';
import { fetchBiMaskingList, fetchDeleteBiMasking } from '@/service/api/bi-masking';
import { useAppStore } from '@/store/modules/app';
import { defaultTransform, useNaivePaginatedTable, useTableOperate } from '@/hooks/common/table';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';
import MaskingOperateModal from './modules/masking-operate-modal.vue';

defineOptions({ name: 'BiMasking' });

const appStore = useAppStore();
const { hasAuth } = useAuth();

const searchParams = reactive<Api.Bi.BiMaskingRuleSearchParams>({
  current: 1,
  size: 10,
  name: null,
  maskType: null,
  statusType: null
});

const maskTypeOptions = computed(() => [
  { label: $t('page.bi.masking.maskTypes.phone'), value: 'phone' },
  { label: $t('page.bi.masking.maskTypes.idcard'), value: 'idcard' },
  { label: $t('page.bi.masking.maskTypes.email'), value: 'email' },
  { label: $t('page.bi.masking.maskTypes.bankcard'), value: 'bankcard' },
  { label: $t('page.bi.masking.maskTypes.custom'), value: 'custom' }
]);

const maskTypeLabel = (val: Api.Bi.MaskType | null) => {
  if (!val) return null;
  const opt = maskTypeOptions.value.find(o => o.value === val);
  return opt ? opt.label : val;
};

const { columns, columnChecks, data, loading, getData, getDataByPage, mobilePagination } = useNaivePaginatedTable({
  api: () => fetchBiMaskingList(searchParams),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.current = params.page;
    searchParams.size = params.pageSize;
  },
  columns: () => [
    { type: 'selection', align: 'center', width: 48 },
    { key: 'index', title: $t('common.index'), width: 64, align: 'center', render: (_, index) => index + 1 },
    { key: 'name', title: $t('page.bi.masking.name'), minWidth: 140 },
    { key: 'columnPattern', title: $t('page.bi.masking.columnPattern'), minWidth: 180 },
    {
      key: 'maskType',
      title: $t('page.bi.masking.maskType'),
      align: 'center',
      minWidth: 110,
      render: row => {
        const label = maskTypeLabel(row.maskType);
        return label ? <NTag size="small">{label}</NTag> : null;
      }
    },
    { key: 'maskChar', title: $t('page.bi.masking.maskChar'), align: 'center', minWidth: 100 },
    { key: 'keepPrefix', title: $t('page.bi.masking.keepPrefix'), align: 'center', width: 100 },
    { key: 'keepSuffix', title: $t('page.bi.masking.keepSuffix'), align: 'center', width: 100 },
    {
      key: 'statusType',
      title: $t('page.bi.masking.status'),
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
          {hasAuth('B_BI_MASKING_EDIT') && (
            <NButton type="primary" ghost size="small" onClick={() => edit(row.id)}>
              {$t('common.edit')}
            </NButton>
          )}
          {hasAuth('B_BI_MASKING_DELETE') && (
            <NPopconfirm onPositiveClick={() => handleDelete(row.id)}>
              {{
                default: () => $t('page.bi.masking.confirmDelete'),
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
  const { error } = await fetchDeleteBiMasking({ id });
  if (!error) onDeleted();
}

function edit(id: string) {
  handleEdit(id);
}

function resetSearchParams() {
  Object.assign(searchParams, {
    current: 1,
    name: null,
    maskType: null,
    statusType: null
  });
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <NCard :bordered="false" size="small" class="card-wrapper">
      <NCollapse :default-expanded-names="['masking-search']">
        <NCollapseItem :title="$t('common.search')" name="masking-search">
          <NForm :model="searchParams" label-placement="left" :label-width="80">
            <NGrid responsive="screen" item-responsive>
              <NFormItemGi span="24 s:12 m:6" :label="$t('page.bi.masking.name')" path="name" class="pr-24px">
                <NInput
                  v-model:value="searchParams.name"
                  clearable
                  :placeholder="$t('page.bi.masking.searchPlaceholder')"
                />
              </NFormItemGi>
              <NFormItemGi span="24 s:12 m:6" :label="$t('page.bi.masking.maskType')" path="maskType" class="pr-24px">
                <NSelect
                  v-model:value="searchParams.maskType"
                  :options="maskTypeOptions"
                  clearable
                  :placeholder="$t('page.bi.masking.maskType')"
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
    <NCard :title="$t('page.bi.masking.title')" :bordered="false" size="small" class="card-wrapper sm:flex-1-hidden">
      <template #header-extra>
        <TableHeaderOperation v-model:columns="columnChecks" :loading="loading" @refresh="getData">
          <NButton v-if="hasAuth('B_BI_MASKING_CREATE')" size="small" ghost type="primary" @click="handleAdd">
            <template #icon><icon-ic-round-plus class="text-icon" /></template>
            {{ $t('page.bi.masking.create') }}
          </NButton>
        </TableHeaderOperation>
      </template>
      <NDataTable
        v-model:checked-row-keys="checkedRowKeys"
        :columns="columns"
        :data="data"
        size="small"
        :flex-height="!appStore.isMobile"
        :scroll-x="1000"
        :loading="loading"
        remote
        :row-key="row => row.id"
        :pagination="mobilePagination"
        class="sm:h-full"
      />
      <MaskingOperateModal
        v-model:visible="drawerVisible"
        :operate-type="operateType"
        :editing-id="editingData?.id ?? null"
        @submitted="getData"
      />
    </NCard>
  </div>
</template>
