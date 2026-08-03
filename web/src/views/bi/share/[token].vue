<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { fetchSharedBiChart } from '@/service/api/bi-chart';
import { $t } from '@/locales';
import { useEcharts, type ECOption } from '@/hooks/common/echarts';
import { buildChartOption, type ChartType } from '../shared/chart-config';

defineOptions({ name: 'BiShare' });

const route = useRoute();

const loading = ref<boolean>(false);
const chart = ref<Api.Bi.BiChartShared | null>(null);
const errorMsg = ref<string>('');

const token = computed(() => route.params.token as string);

const chartOption = computed<ECOption>(() => {
  if (!chart.value?.resultSnapshot?.rows?.length || !chart.value.xCol || !chart.value.yCol) {
    return {} as ECOption;
  }
  return buildChartOption(
    {
      columns: chart.value.resultSnapshot.columns,
      rows: chart.value.resultSnapshot.rows
    },
    (chart.value.chartType as ChartType) || 'bar',
    chart.value.xCol,
    chart.value.yCol
  );
});

const { domRef: chartRef, setOptions: setChartOptions } = useEcharts(() => ({}) as ECOption, {
  onRender: instance => {
    if (Object.keys(chartOption.value).length) {
      instance.setOption({ ...chartOption.value, backgroundColor: 'transparent' });
    }
  }
});

function formatSnapshotAt(iso: string): string {
  if (!iso) return '-';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

async function loadChart() {
  loading.value = true;
  errorMsg.value = '';
  try {
    const { data, error } = await fetchSharedBiChart(token.value);
    if (error) {
      errorMsg.value = error.message || $t('common.error');
    } else if (data) {
      chart.value = data;
      // 数据就绪后触发图表渲染
      if (Object.keys(chartOption.value).length) {
        setChartOptions(chartOption.value);
      }
    }
  } catch (e: any) {
    errorMsg.value = e?.message || $t('common.error');
  } finally {
    loading.value = false;
  }
}

watch(token, () => {
  if (token.value) loadChart();
});

onMounted(loadChart);
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 p-24px">
    <div class="w-full max-w-960px bg-white dark:bg-gray-800 rounded-12px shadow-md p-32px">
      <NSpin :show="loading">
        <!-- 头部 -->
        <div class="mb-16px text-center">
          <h1 class="m-0 mb-4px text-22px font-600 text-gray-800 dark:text-gray-100">
            {{ chart?.name || $t('page.bi.chart.sharedTitle') }}
          </h1>
          <div class="text-12px text-gray-500 dark:text-gray-400">
            {{ $t('page.bi.chart.sharedSubtitle') }}
          </div>
        </div>

        <!-- 错误状态 -->
        <div v-if="errorMsg && !loading" class="py-80px text-center">
          <NEmpty size="large" :description="errorMsg">
            <template #icon>
              <icon-ic-round-cloud-off class="text-48px text-gray-400" />
            </template>
          </NEmpty>
        </div>

        <!-- 图表内容 -->
        <template v-else-if="chart">
          <div class="mb-12px text-center text-12px text-gray-500 dark:text-gray-400">
            {{ $t('page.bi.chart.snapshotAt') }}: {{ formatSnapshotAt(chart.snapshotAt) }}
            ·
            {{ chart.resultSnapshot?.rowCount ?? 0 }} {{ $t('page.bi.chart.rowCount') }}
            <span v-if="chart.resultSnapshot?.isTruncated" class="text-orange-500">
              · {{ $t('page.bi.chart.truncated') }}
            </span>
          </div>
          <div ref="chartRef" class="h-450px w-full" />
        </template>

        <!-- 加载中占位 -->
        <div v-else-if="!loading" class="py-80px text-center text-gray-400">
          <NEmpty size="large" />
        </div>
      </NSpin>
    </div>
  </div>
</template>
