<script lang="tsx">
import { computed, defineComponent, h, type PropType } from 'vue';
import { useEcharts, type ECOption } from '@/hooks/common/echarts';
import { buildChartOption, type ChartType } from './chart-config';

/**
 * 图表缩略图共享组件 — 仪表盘列表与详情页共用。
 *
 * 与原 charts/index.vue 内联 ChartThumbnail 行为一致：
 * - snapshot 无 rows 或 xCol/yCol 缺失时返回空 option（显示空容器）
 * - 背景透明，由父容器控制尺寸
 */
export interface ChartThumbnailProps {
  /** SQL 结果快照（columns + rows） */
  snapshot: { columns: string[]; rows: Array<Record<string, any>> } | null | undefined;
  /** 图表类型 */
  chartType: string;
  /** X 轴字段名 */
  xCol?: string | null;
  /** Y 轴字段名 */
  yCol?: string | null;
  /** 容器高度类名（默认 h-160px） */
  heightClass?: string;
}

export default defineComponent({
  name: 'BiChartThumbnail',
  props: {
    snapshot: { type: Object as PropType<ChartThumbnailProps['snapshot']>, default: null },
    chartType: { type: String, default: 'bar' },
    xCol: { type: [String, null] as unknown as PropType<string | null | undefined>, default: '' },
    yCol: { type: [String, null] as unknown as PropType<string | null | undefined>, default: '' },
    heightClass: { type: String, default: 'h-160px' }
  },
  setup(p) {
    const option = computed<ECOption>(() => {
      const snap = p.snapshot;
      if (!snap?.rows?.length || !p.xCol || !p.yCol) return {} as ECOption;
      return buildChartOption(
        { columns: snap.columns, rows: snap.rows },
        (p.chartType as ChartType) || 'bar',
        p.xCol,
        p.yCol
      );
    });
    const { domRef } = useEcharts<ECOption>(() => option.value, {
      onRender: instance => {
        if (Object.keys(option.value).length) {
          instance.setOption({ ...option.value, backgroundColor: 'transparent' });
        }
      }
    });
    return () => h('div', { ref: domRef, class: ['w-full', p.heightClass] });
  }
});
</script>
