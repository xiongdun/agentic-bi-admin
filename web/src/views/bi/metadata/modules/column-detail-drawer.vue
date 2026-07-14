<script setup lang="tsx">
import { ref, watch } from 'vue';
import { NDataTable, NDescriptions, NDescriptionsItem, NDrawer, NDrawerContent, NEmpty, NTag } from 'naive-ui';
import { fetchBiTableDetail } from '@/service/api';
import { $t } from '@/locales';

defineOptions({ name: 'ColumnDetailDrawer' });

const props = defineProps<{
  table: Api.Bi.BiTable | null;
}>();

const visible = ref(false);
const tableId = ref<string | null>(null);
const detail = ref<Api.Bi.BiTableDetail | null>(null);
const loading = ref(false);

async function loadDetail(id: string) {
  loading.value = true;
  try {
    const { data, error } = await fetchBiTableDetail(id);
    if (!error && data) {
      detail.value = data;
    }
  } finally {
    loading.value = false;
  }
}

function open(id: string) {
  tableId.value = id;
  detail.value = null;
  visible.value = true;
  loadDetail(id);
}

function close() {
  visible.value = false;
}

const columnColumns = [
  {
    key: 'ordinal',
    title: $t('page.bi.metadata.column.ordinal'),
    width: 64
  },
  {
    key: 'name',
    title: $t('page.bi.metadata.column.name'),
    minWidth: 140
  },
  {
    key: 'dataType',
    title: $t('page.bi.metadata.column.dataType'),
    minWidth: 120
  },
  {
    key: 'nullable',
    title: $t('page.bi.metadata.column.nullable'),
    width: 90,
    render: (row: Api.Bi.BiColumn) => (
      <NTag size="small" type={row.nullable ? 'default' : 'warning'}>
        {row.nullable ? 'YES' : 'NO'}
      </NTag>
    )
  },
  {
    key: 'role',
    title: $t('page.bi.metadata.column.isDimension') + ' / ' + $t('page.bi.metadata.column.isMetric'),
    width: 140,
    render: (row: Api.Bi.BiColumn) => (
      <NSpace size={4}>
        {row.isDimension && <NTag size="small" type="info">D</NTag>}
        {row.isMetric && <NTag size="small" type="success">M</NTag>}
      </NSpace>
    )
  },
  {
    key: 'sampleValues',
    title: $t('page.bi.metadata.column.sampleValues'),
    minWidth: 200,
    render: (row: Api.Bi.BiColumn) =>
      row.sampleValues && row.sampleValues.length
        ? row.sampleValues.slice(0, 5).join(', ') + (row.sampleValues.length > 5 ? '…' : '')
        : '-'
  }
];

defineExpose({ open, close });

watch(visible, v => {
  if (!v) {
    detail.value = null;
  }
});

watch(
  () => props.table?.id,
  () => {
    detail.value = null;
  }
);
</script>

<template>
  <NDrawer v-model:show="visible" :width="900" placement="right">
    <NDrawerContent
      :title="table ? $t('page.bi.metadata.table.detailTitle', { name: table.name }) : ''"
      :native-scrollbar="false"
      :loading="loading"
    >
      <NEmpty v-if="!detail" :description="$t('common.noData')" />

      <template v-else>
        <NDescriptions
          v-if="detail.description || detail.tags?.length"
          :column="2"
          size="small"
          bordered
          class="mb-12px"
        >
          <NDescriptionsItem :span="2" :label="$t('page.bi.metadata.table.description')">
            {{ detail.description || '-' }}
          </NDescriptionsItem>
          <NDescriptionsItem :span="2" :label="$t('page.bi.metadata.table.tags')">
            <NSpace v-if="detail.tags && detail.tags.length">
              <NTag v-for="t in detail.tags" :key="t" size="small" type="info">{{ t }}</NTag>
            </NSpace>
            <span v-else>-</span>
          </NDescriptionsItem>
        </NDescriptions>

        <NDataTable
          :columns="columnColumns"
          :data="detail.columns"
          :row-key="row => row.id"
          size="small"
          :pagination="false"
          :scroll-x="700"
        />
      </template>
    </NDrawerContent>
  </NDrawer>
</template>
