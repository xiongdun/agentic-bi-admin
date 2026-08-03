<script setup lang="tsx">
import { onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { fetchBiDatasourceList } from '@/service/api/bi';
import { fetchBiChartList, fetchBiChartTags, fetchDeleteBiChart } from '@/service/api/bi-chart';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';
import ChartThumbnail from '../shared/chart-thumbnail.vue';

defineOptions({ name: 'BiCharts' });

const router = useRouter();
const { hasAuth } = useAuth();

const searchParams = reactive<Api.Bi.BiChartSearchParams>({
  current: 1,
  size: 12,
  name: undefined,
  tags: undefined,
  datasourceId: undefined
});

const loading = ref<boolean>(false);
const list = ref<Api.Bi.BiChart[]>([]);
const total = ref<number>(0);

const datasourceMap = ref<Record<string, Api.Bi.BiDatasource>>({});
const datasourceOptions = ref<{ label: string; value: string }[]>([]);
const tagOptions = ref<{ label: string; value: string }[]>([]);

async function loadDatasources() {
  const { data } = await fetchBiDatasourceList({ current: 1, size: 999 });
  if (data?.records) {
    const map: Record<string, Api.Bi.BiDatasource> = {};
    data.records.forEach(d => {
      map[d.id] = d;
    });
    datasourceMap.value = map;
    datasourceOptions.value = data.records.map(d => ({ label: `${d.name} (${d.dbType})`, value: d.id }));
  }
}

async function loadTags() {
  const { data } = await fetchBiChartTags();
  if (data?.tags) {
    tagOptions.value = data.tags.map(t => ({ label: t, value: t }));
  }
}

async function getData() {
  loading.value = true;
  try {
    const { data } = await fetchBiChartList(searchParams);
    if (data) {
      list.value = data.records;
      total.value = data.total;
    }
  } finally {
    loading.value = false;
  }
}

function getDataByPage(page: number) {
  searchParams.current = page;
  getData();
}

function resetSearchParams() {
  Object.assign(searchParams, {
    current: 1,
    name: null,
    tags: null,
    datasourceId: null
  });
  getData();
}

function openDetail(id: string) {
  router.push({ name: 'bi_chart-detail', params: { id } });
}

async function handleDelete(id: string) {
  const { error } = await fetchDeleteBiChart({ id });
  if (!error) {
    window.$message?.success($t('common.deleteSuccess'));
    getData();
  }
}

function parseTags(tags: string | null | undefined): string[] {
  if (!tags) return [];
  return tags
    .split(',')
    .map(t => t.trim())
    .filter(Boolean);
}

function datasourceName(id: string): string {
  return datasourceMap.value[id]?.name || id;
}

function chartTypeLabel(type: string): string {
  const labels: Record<string, App.I18n.I18nKey> = {
    bar: 'page.bi.metrics.chartTypes.bar',
    line: 'page.bi.metrics.chartTypes.line',
    area: 'page.bi.metrics.chartTypes.area',
    pie: 'page.bi.metrics.chartTypes.pie',
    scatter: 'page.bi.metrics.chartTypes.scatter',
    radar: 'page.bi.metrics.chartTypes.radar',
    funnel: 'page.bi.metrics.chartTypes.funnel',
    gauge: 'page.bi.metrics.chartTypes.gauge',
    heatmap: 'page.bi.metrics.chartTypes.heatmap'
  };
  const key = labels[type];
  return key ? $t(key) : type;
}

function formatSnapshotAt(iso: string): string {
  if (!iso) return '-';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

// ---- 内联图表缩略图组件 ----
// 已抽出为 shared/chart-thumbnail.vue，列表与仪表盘详情页共用。

onMounted(() => {
  loadDatasources();
  loadTags();
  getData();
});
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <!-- 搜索栏 -->
    <NCard :bordered="false" size="small" class="card-wrapper">
      <NCollapse :default-expanded-names="['chart-search']">
        <NCollapseItem :title="$t('common.search')" name="chart-search">
          <NForm :model="searchParams" label-placement="left" :label-width="80">
            <NGrid responsive="screen" item-responsive>
              <NFormItemGi span="24 s:12 m:8" :label="$t('page.bi.chart.name')" path="name" class="pr-24px">
                <NInput
                  v-model:value="searchParams.name"
                  clearable
                  :placeholder="$t('page.bi.chart.searchPlaceholder')"
                />
              </NFormItemGi>
              <NFormItemGi span="24 s:12 m:8" :label="$t('page.bi.chart.tags')" path="tags" class="pr-24px">
                <NSelect
                  v-model:value="searchParams.tags"
                  :options="tagOptions"
                  clearable
                  filterable
                  :placeholder="$t('page.bi.chart.filterByTag')"
                />
              </NFormItemGi>
              <NFormItemGi
                span="24 s:12 m:8"
                :label="$t('page.bi.chart.datasource')"
                path="datasourceId"
                class="pr-24px"
              >
                <NSelect
                  v-model:value="searchParams.datasourceId"
                  :options="datasourceOptions"
                  clearable
                  filterable
                  :placeholder="$t('page.bi.chart.filterByDatasource')"
                />
              </NFormItemGi>
              <NFormItemGi span="24">
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

    <!-- 列表 -->
    <NCard :title="$t('page.bi.chart.title')" :bordered="false" size="small" class="card-wrapper sm:flex-1-hidden">
      <template #header-extra>
        <NSpace align="center" :size="12">
          <span class="text-12px text-gray-500">{{ $t('page.bi.chart.totalCharts', { count: total }) }}</span>
          <NButton size="small" @click="getData">
            <template #icon><icon-ic-round-refresh class="text-icon" /></template>
            {{ $t('common.refresh') }}
          </NButton>
        </NSpace>
      </template>
      <NSpin :show="loading">
        <NEmpty v-if="!list.length" :description="$t('page.bi.chart.empty')" class="py-80px" />
        <div v-else class="grid grid-cols-1 gap-16px sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          <NCard
            v-for="item in list"
            :key="item.id"
            size="small"
            hoverable
            class="cursor-pointer chart-card"
            @click="openDetail(item.id)"
          >
            <!-- 缩略图 -->
            <div class="chart-thumb-wrapper">
              <ChartThumbnail
                v-if="item.resultSnapshot?.rows?.length"
                :snapshot="item.resultSnapshot"
                :chart-type="item.chartType"
                :x-col="item.xCol"
                :y-col="item.yCol"
                height-class="h-160px"
              />
              <NEmpty v-else size="small" :description="$t('common.noData')" class="py-20px" />
            </div>
            <!-- 信息 -->
            <div class="mt-8px flex flex-col gap-4px">
              <div class="flex items-center gap-6px">
                <NTooltip trigger="hover">
                  <template #trigger>
                    <span class="flex-1 truncate text-14px font-500">{{ item.name }}</span>
                  </template>
                  {{ item.name }}
                </NTooltip>
                <NTag v-if="item.isPublic" size="small" type="success">
                  {{ $t('page.bi.chart.publicLabel') }}
                </NTag>
              </div>
              <div class="flex items-center gap-6px text-12px text-gray-500">
                <NTag size="small" type="primary">{{ chartTypeLabel(item.chartType) }}</NTag>
                <span class="truncate">{{ datasourceName(item.datasourceId) }}</span>
              </div>
              <div v-if="parseTags(item.tags).length" class="flex flex-wrap gap-4px">
                <NTag v-for="tag in parseTags(item.tags)" :key="tag" size="small" type="info" round>
                  {{ tag }}
                </NTag>
              </div>
              <div class="text-11px text-gray-400">
                {{ $t('page.bi.chart.snapshotAt') }}: {{ formatSnapshotAt(item.snapshotAt) }}
              </div>
            </div>
            <!-- 操作 -->
            <template #action>
              <NSpace justify="space-between" align="center">
                <NButton size="small" type="primary" ghost @click.stop="openDetail(item.id)">
                  <template #icon><icon-ic-round-open-in-new class="text-icon" /></template>
                  {{ $t('page.bi.chart.viewDetail') }}
                </NButton>
                <NPopconfirm v-if="hasAuth('B_BI_CHART_DELETE')" @positive-click="handleDelete(item.id)">
                  <template #trigger>
                    <NButton size="small" type="error" ghost @click.stop>
                      <template #icon><icon-ic-round-delete class="text-icon" /></template>
                      {{ $t('common.delete') }}
                    </NButton>
                  </template>
                  {{ $t('page.bi.chart.deleteConfirm') }}
                </NPopconfirm>
              </NSpace>
            </template>
          </NCard>
        </div>
      </NSpin>
      <div v-if="total > 0" class="mt-16px flex justify-end">
        <NPagination
          :page="searchParams.current"
          :page-size="searchParams.size"
          :item-count="total"
          show-size-picker
          :page-sizes="[12, 24, 48]"
          @update:page="getDataByPage"
          @update:page-size="(ps: number) => {
            searchParams.size = ps;
            searchParams.current = 1;
            getData();
          }"
        />
      </div>
    </NCard>
  </div>
</template>

<style scoped>
.chart-card {
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}
.chart-card:hover {
  transform: translateY(-2px);
}
.chart-thumb-wrapper {
  height: 160px;
  overflow: hidden;
  border-radius: 4px;
}
</style>
