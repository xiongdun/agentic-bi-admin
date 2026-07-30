<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { DataTableColumns } from 'naive-ui';
import { fetchBiTableDetail } from '@/service/api/bi';
import { useAppStore } from '@/store/modules/app';
import { $t } from '@/locales';

defineOptions({ name: 'ColumnDetailDrawer' });

interface Props {
  tableId: string | null;
}

const props = defineProps<Props>();
const visible = defineModel<boolean>('visible', { default: false });
const appStore = useAppStore();

const drawerWidth = computed(() => (appStore.isMobile ? '100%' : 720));
const loading = ref(false);
const detail = ref<Api.Bi.BiTableDetail | null>(null);

const columnColumns = computed<DataTableColumns<Api.Bi.BiColumn>>(() => [
  { key: 'name', title: $t('page.bi.metadata.columnName'), minWidth: 140 },
  { key: 'dataType', title: $t('page.bi.metadata.dataType'), minWidth: 120 },
  {
    key: 'isPrimary',
    title: $t('page.bi.metadata.isPrimary'),
    width: 70,
    align: 'center',
    render: (row: Api.Bi.BiColumn) => (row.isPrimary ? '✓' : '')
  },
  {
    key: 'isNullable',
    title: $t('page.bi.metadata.isNullable'),
    width: 70,
    align: 'center',
    render: (row: Api.Bi.BiColumn) => (row.isNullable ? '✓' : '')
  },
  {
    key: 'defaultValue',
    title: $t('page.bi.metadata.defaultValue'),
    minWidth: 100,
    render: (row: Api.Bi.BiColumn) => row.defaultValue ?? '-'
  },
  {
    key: 'comment',
    title: $t('page.bi.metadata.columnComment'),
    minWidth: 120,
    render: (row: Api.Bi.BiColumn) => row.comment ?? '-'
  },
  {
    key: 'sampleValues',
    title: $t('page.bi.metadata.sampleValues'),
    minWidth: 160,
    render: (row: Api.Bi.BiColumn) => (row.sampleValues?.length ? row.sampleValues.map(v => String(v)).join(', ') : '-')
  }
]);

const indexColumns = computed<DataTableColumns<Api.Bi.BiIndex>>(() => [
  { key: 'name', title: $t('page.bi.metadata.indexName'), minWidth: 160 },
  { key: 'indexType', title: $t('page.bi.metadata.indexType'), minWidth: 100 },
  {
    key: 'columns',
    title: $t('page.bi.metadata.indexColumns'),
    minWidth: 160,
    render: (row: Api.Bi.BiIndex) => (row.columns || []).join(', ')
  },
  {
    key: 'isUnique',
    title: $t('page.bi.metadata.isUnique'),
    width: 70,
    align: 'center',
    render: (row: Api.Bi.BiIndex) => (row.isUnique ? '✓' : '')
  }
]);

const fkColumns = computed<DataTableColumns<Api.Bi.BiForeignKey>>(() => [
  { key: 'name', title: $t('page.bi.metadata.foreignKeyName'), minWidth: 140 },
  { key: 'columnName', title: $t('page.bi.metadata.columnNameSource'), minWidth: 120 },
  { key: 'refTable', title: $t('page.bi.metadata.refTable'), minWidth: 120 },
  { key: 'refColumn', title: $t('page.bi.metadata.refColumn'), minWidth: 120 }
]);

async function loadDetail() {
  if (!props.tableId) return;
  loading.value = true;
  detail.value = null;
  const { data, error } = await fetchBiTableDetail(props.tableId);
  loading.value = false;
  if (!error && data) {
    detail.value = data;
  }
}

watch(visible, val => {
  if (val) {
    loadDetail();
  }
});
</script>

<template>
  <NDrawer v-model:show="visible" :width="drawerWidth" display-directive="show">
    <NDrawerContent :title="$t('page.bi.metadata.viewTableStructure')" :native-scrollbar="false" closable>
      <NSpin :show="loading">
        <template v-if="detail">
          <NDescriptions :column="appStore.isMobile ? 1 : 2" label-placement="left" bordered size="small">
            <NDescriptionsItem :label="$t('page.bi.metadata.tableName')" :span="2">
              {{ detail.name }}
            </NDescriptionsItem>
            <NDescriptionsItem :label="$t('page.bi.metadata.tableComment')" :span="2">
              {{ detail.comment || '-' }}
            </NDescriptionsItem>
            <NDescriptionsItem :label="$t('page.bi.metadata.rowCount')">
              {{ detail.rowCount }}
            </NDescriptionsItem>
            <NDescriptionsItem :label="$t('page.bi.metadata.columnCount')">
              {{ detail.columns?.length || 0 }}
            </NDescriptionsItem>
          </NDescriptions>

          <NDivider>{{ $t('page.bi.metadata.columnList') }}</NDivider>
          <NDataTable
            :columns="columnColumns"
            :data="detail.columns || []"
            size="small"
            :scroll-x="700"
            :pagination="false"
          />

          <template v-if="detail.indexes && detail.indexes.length > 0">
            <NDivider>{{ $t('page.bi.metadata.indexList') }}</NDivider>
            <NDataTable :columns="indexColumns" :data="detail.indexes" size="small" :pagination="false" />
          </template>

          <template v-if="detail.foreignKeys && detail.foreignKeys.length > 0">
            <NDivider>{{ $t('page.bi.metadata.foreignKeyList') }}</NDivider>
            <NDataTable :columns="fkColumns" :data="detail.foreignKeys" size="small" :pagination="false" />
          </template>
        </template>
        <NEmpty v-else-if="!loading" :description="$t('common.noData')" />
      </NSpin>
    </NDrawerContent>
  </NDrawer>
</template>
