<script setup lang="tsx">
import { reactive } from 'vue';
import { NButton, NTag } from 'naive-ui';
import { fetchBiNotifyList, fetchMarkBiNotifyRead } from '@/service/api/bi-notify';
import { useAppStore } from '@/store/modules/app';
import { defaultTransform, useNaivePaginatedTable } from '@/hooks/common/table';
import { $t } from '@/locales';

defineOptions({ name: 'BiNotifyRecords' });

const appStore = useAppStore();

const searchParams = reactive<Api.Bi.BiNotifyRecordSearchParams>({
  current: 1,
  size: 10,
  status: null,
  isRead: null
});

const { columns, columnChecks, data, loading, getData, getDataByPage, mobilePagination } = useNaivePaginatedTable({
  api: () => fetchBiNotifyList(searchParams),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.current = params.page;
    searchParams.size = params.pageSize;
  },
  columns: () => [
    { key: 'index', title: $t('common.index'), width: 64, align: 'center', render: (_, index) => index + 1 },
    { key: 'title', title: $t('page.bi.notify.title'), minWidth: 220 },
    {
      key: 'status',
      title: $t('page.bi.notify.statusSuccess'),
      align: 'center',
      width: 90,
      render: row => {
        const isSuccess = row.status === 'success';
        return (
          <NTag type={isSuccess ? 'success' : 'error'} size="small">
            {isSuccess ? $t('page.bi.notify.statusSuccess') : $t('page.bi.notify.statusFailed')}
          </NTag>
        );
      }
    },
    {
      key: 'fmtCreatedAt',
      title: $t('page.bi.notify.createdAt'),
      minWidth: 160,
      render: row => row.fmtCreatedAt || '-'
    },
    {
      key: 'isRead',
      title: $t('page.bi.notify.unread'),
      align: 'center',
      width: 90,
      render: row =>
        row.isRead ? (
          <NTag size="small">{ $t('page.bi.notify.read') }</NTag>
        ) : (
          <NTag type="warning" size="small">{ $t('page.bi.notify.unread') }</NTag>
        )
    },
    {
      key: 'operate',
      title: $t('common.operate'),
      align: 'center',
      width: 110,
      render: row =>
        !row.isRead ? (
          <NButton size="small" text type="primary" onClick={() => handleMarkRead(row.id)}>
            {$t('page.bi.notify.markRead')}
          </NButton>
        ) : null
    }
  ]
});

async function handleMarkRead(id: string) {
  const { error } = await fetchMarkBiNotifyRead(id);
  if (!error) {
    window.$message?.success($t('page.bi.notify.markRead'));
    getData();
  }
}

function resetSearchParams() {
  Object.assign(searchParams, {
    current: 1,
    status: null,
    isRead: null
  });
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <NCard :bordered="false" size="small" class="card-wrapper">
      <NCollapse :default-expanded-names="['notify-search']">
        <NCollapseItem :title="$t('common.search')" name="notify-search">
          <NForm :model="searchParams" label-placement="left" :label-width="80">
            <NGrid responsive="screen" item-responsive>
              <NFormItemGi span="24 s:12 m:6" :label="$t('page.bi.notify.statusSuccess')" path="status" class="pr-24px">
                <NSelect
                  v-model:value="searchParams.status"
                  clearable
                  :options="[
                    { label: $t('page.bi.notify.statusSuccess'), value: 'success' },
                    { label: $t('page.bi.notify.statusFailed'), value: 'failed' }
                  ]"
                  :placeholder="$t('page.bi.notify.statusSuccess')"
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
    <NCard :title="$t('page.bi.notify.title')" :bordered="false" size="small" class="card-wrapper sm:flex-1-hidden">
      <template #header-extra>
        <TableHeaderOperation v-model:columns="columnChecks" :loading="loading" @refresh="getData" />
      </template>
      <NDataTable
        :columns="columns"
        :data="data"
        size="small"
        :flex-height="!appStore.isMobile"
        :scroll-x="900"
        :loading="loading"
        remote
        :row-key="row => row.id"
        :pagination="mobilePagination"
        class="sm:h-full"
      />
    </NCard>
  </div>
</template>
