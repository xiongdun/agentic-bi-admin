<script lang="tsx">
import { computed, defineComponent, h } from 'vue';
import { NButton, NEmpty, NTag, NTooltip } from 'naive-ui';
import { $t } from '@/locales';
import { useEcharts, type ECOption } from '@/hooks/common/echarts';
import { buildChartOption, type ChartType } from './chart-config';

/**
 * 仪表盘内单个图表卡片 — 在 gridstack item 内动态挂载。
 *
 * 接收 refresh/preview item 数据，渲染：
 * - status=success 或有 resultSnapshot：显示 ECharts 图表
 * - status=failed：显示错误信息占位
 * - status=deleted 或 chartMeta=null：显示已删除占位
 * - 编辑模式：右上角显示移除按钮
 */
export interface DashboardChartCardProps {
  chartId: string;
  item: Api.Bi.BiDashboardRefreshItem | Api.Bi.BiDashboardPreviewItem | null;
  isEditMode: boolean;
}

export default defineComponent({
  name: 'BiDashboardChartCard',
  props: {
    chartId: { type: String, required: true },
    item: { type: Object as () => DashboardChartCardProps['item'], default: null },
    isEditMode: { type: Boolean, default: false }
  },
  emits: ['remove'],
  setup(p, { emit }) {
    const chartMeta = computed(() => p.item?.chartMeta ?? null);
    const snapshot = computed(() => p.item?.resultSnapshot ?? null);

    // 判断状态：refresh item 有 status 字段；preview item 可能无 status
    const status = computed<'success' | 'failed' | 'deleted'>(() => {
      const item = p.item as Api.Bi.BiDashboardRefreshItem | null;
      if (item?.status === 'failed') return 'failed';
      if (item?.status === 'deleted' || !chartMeta.value) return 'deleted';
      return 'success';
    });

    const errorMessage = computed(() => {
      const item = p.item as Api.Bi.BiDashboardRefreshItem | null;
      return item?.errorMessage || '';
    });

    const option = computed<ECOption>(() => {
      if (status.value !== 'success') return {} as ECOption;
      const snap = snapshot.value;
      const meta = chartMeta.value;
      if (!snap?.rows?.length || !meta?.xCol || !meta?.yCol) return {} as ECOption;
      return buildChartOption(
        { columns: snap.columns, rows: snap.rows },
        (meta.chartType as ChartType) || 'bar',
        meta.xCol,
        meta.yCol
      );
    });

    const { domRef } = useEcharts<ECOption>(() => option.value, {
      onRender: instance => {
        if (Object.keys(option.value).length) {
          instance.setOption({ ...option.value, backgroundColor: 'transparent' });
        }
      }
    });

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

    function statusLabel(s: 'success' | 'failed' | 'deleted'): string {
      if (s === 'success') return $t('page.bi.dashboard.statusSuccess');
      if (s === 'failed') return $t('page.bi.dashboard.statusFailed');
      return $t('page.bi.dashboard.statusDeleted');
    }

    function statusTagType(s: 'success' | 'failed' | 'deleted'): 'success' | 'error' | 'warning' {
      if (s === 'success') return 'success';
      if (s === 'failed') return 'error';
      return 'warning';
    }

    return () =>
      h('div', { class: 'dashboard-card-root h-full w-full flex flex-col' }, [
        // 顶部标题栏
        h('div', { class: 'flex items-center justify-between gap-4px px-8px pt-4px flex-shrink-0' }, [
          h('div', { class: 'flex items-center gap-4px min-w-0 flex-1' }, [
            h(
              NTooltip,
              { trigger: 'hover' },
              {
                trigger: () =>
                  h(
                    'span',
                    { class: 'text-13px font-500 truncate' },
                    chartMeta.value?.name || $t('page.bi.dashboard.chartDeleted')
                  ),
                default: () => chartMeta.value?.name || ''
              }
            ),
            chartMeta.value
              ? h(NTag, { size: 'small', type: 'primary', bordered: false }, () =>
                  chartTypeLabel(chartMeta.value?.chartType ?? 'bar')
                )
              : null
          ]),
          h('div', { class: 'flex items-center gap-4px flex-shrink-0' }, [
            status.value === 'success'
              ? null
              : h(NTag, { size: 'small', type: statusTagType(status.value), bordered: false }, () =>
                  statusLabel(status.value)
                ),
            p.isEditMode
              ? h(
                  NButton,
                  {
                    size: 'tiny',
                    type: 'error',
                    quaternary: true,
                    circle: true,
                    onClick: () => emit('remove', p.chartId)
                  },
                  { icon: () => h('icon-ic-round-close', { class: 'text-icon' }) }
                )
              : null
          ])
        ]),
        // 内容区
        h('div', { class: 'flex-1 min-h-0 relative' }, [
          status.value === 'success'
            ? h('div', { ref: domRef, class: 'h-full w-full' })
            : status.value === 'failed'
              ? h('div', { class: 'h-full w-full flex flex-col items-center justify-center gap-8px px-12px' }, [
                  h(NEmpty, { size: 'small', description: $t('page.bi.dashboard.refreshFailed') }),
                  errorMessage.value
                    ? h(
                        NTooltip,
                        { trigger: 'hover', maxWidth: 400 },
                        {
                          trigger: () =>
                            h(
                              'div',
                              { class: 'text-11px text-red-500 line-clamp-2 text-center max-w-240px' },
                              errorMessage.value
                            ),
                          default: () => errorMessage.value
                        }
                      )
                    : null
                ])
              : h(
                  'div',
                  { class: 'h-full w-full flex items-center justify-center' },
                  h(NEmpty, { size: 'small', description: $t('page.bi.dashboard.chartDeleted') })
                )
        ])
      ]);
  }
});
</script>

<style scoped>
.dashboard-card-root {
  background: var(--n-card-color, transparent);
}
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
