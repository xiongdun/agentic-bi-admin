<script setup lang="tsx">
import { reactive } from 'vue';
import { NButton, NPopconfirm, NTag } from 'naive-ui';
import { statusTypeRecord } from '@/constants/business';
import { fetchBiSubscriptionList, fetchDeleteBiSubscription } from '@/service/api/bi-subscription';
import { useAppStore } from '@/store/modules/app';
import { defaultTransform, useNaivePaginatedTable, useTableOperate } from '@/hooks/common/table';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';
import SubscriptionOperateModal from './modules/subscription-operate-modal.vue';

defineOptions({ name: 'BiSubscriptions' });

const appStore = useAppStore();
const { hasAuth } = useAuth();

const searchParams = reactive<Api.Bi.BiSubscriptionSearchParams>({
  current: 1,
  size: 10,
  name: null,
  statusType: null
});

function formatTime(iso: string | null): string {
  if (!iso) return '-';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

const { columns, columnChecks, data, loading, getData, getDataByPage, mobilePagination } = useNaivePaginatedTable({
  api: () => fetchBiSubscriptionList(searchParams),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.current = params.page;
    searchParams.size = params.pageSize;
  },
  columns: () => [
    { type: 'selection', align: 'center', width: 48 },
    { key: 'index', title: $t('common.index'), width: 64, align: 'center', render: (_, index) => index + 1 },
    { key: 'name', title: $t('page.bi.subscription.name'), minWidth: 140 },
    { key: 'cronExpr', title: $t('page.bi.subscription.cronExpr'), minWidth: 120 },
    {
      key: 'nextRunAt',
      title: $t('page.bi.subscription.nextRunAt'),
      minWidth: 160,
      render: row => formatTime(row.nextRunAt)
    },
    {
      key: 'lastRunAt',
      title: $t('page.bi.subscription.lastRunAt'),
      minWidth: 160,
      render: row => formatTime(row.lastRunAt)
    },
    {
      key: 'lastStatus',
      title: $t('page.bi.subscription.lastStatus'),
      align: 'center',
      width: 90,
      render: row => {
        if (row.lastStatus === null) return null;
        const isSuccess = row.lastStatus === 'success';
        return (
          <NTag type={isSuccess ? 'success' : 'error'} size="small">
            {isSuccess ? $t('page.bi.subscription.statusSuccess') : $t('page.bi.subscription.statusFailed')}
          </NTag>
        );
      }
    },
    {
      key: 'statusType',
      title: $t('page.bi.subscription.status'),
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
          {hasAuth('B_BI_SUBSCRIPTION_EDIT') && (
            <NButton type="primary" ghost size="small" onClick={() => edit(row.id)}>
              {$t('common.edit')}
            </NButton>
          )}
          {hasAuth('B_BI_SUBSCRIPTION_DELETE') && (
            <NPopconfirm onPositiveClick={() => handleDelete(row.id)}>
              {{
                default: () => $t('page.bi.subscription.confirmDelete'),
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

const { drawerVisible, operateType, editingData, handleAdd, handleEdit, onDeleted } = useTableOperate(data, 'id', getData);

async function handleDelete(id: string) {
  const { error } = await fetchDeleteBiSubscription({ id });
  if (!error) onDeleted();
}

function edit(id: string) {
  handleEdit(id);
}

function resetSearchParams() {
  Object.assign(searchParams, {
    current: 1,
    name: null,
    statusType: null
  });
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <NCard :bordered="false" size="small" class="card-wrapper">
      <NCollapse :default-expanded-names="['subscription-search']">
        <NCollapseItem :title="$t('common.search')" name="subscription-search">
          <NForm :model="searchParams" label-placement="left" :label-width="80">
            <NGrid responsive="screen" item-responsive>
              <NFormItemGi span="24 s:12 m:6" :label="$t('page.bi.subscription.name')" path="name" class="pr-24px">
                <NInput
                  v-model:value="searchParams.name"
                  clearable
                  :placeholder="$t('page.bi.subscription.searchPlaceholder')"
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
      :title="$t('page.bi.subscription.title')"
      :bordered="false"
      size="small"
      class="card-wrapper sm:flex-1-hidden"
    >
      <template #header-extra>
        <TableHeaderOperation v-model:columns="columnChecks" :loading="loading" @refresh="getData">
          <NButton v-if="hasAuth('B_BI_SUBSCRIPTION_CREATE')" size="small" ghost type="primary" @click="handleAdd">
            <template #icon><icon-ic-round-plus class="text-icon" /></template>
            {{ $t('page.bi.subscription.create') }}
          </NButton>
        </TableHeaderOperation>
      </template>
      <NDataTable
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
      <SubscriptionOperateModal
        v-model:visible="drawerVisible"
        :operate-type="operateType"
        :editing-id="editingData?.id ?? null"
        @submitted="getData"
      />
    </NCard>
  </div>
</template>
