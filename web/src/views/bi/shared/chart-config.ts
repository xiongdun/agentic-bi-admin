/**
 * BI 图表共享配置 — 智能对话与 SQL 工作台共用。
 *
 * 统一图表类型枚举、i18n 选项、buildChartOption 构建逻辑，避免两处重复实现。
 */
import type { ECOption } from '@/hooks/common/echarts';
import { $t } from '@/locales';

/** 图表类型枚举（与后端 chartType 字段对齐） */
export type ChartType = 'bar' | 'line' | 'pie' | 'scatter' | 'area' | 'radar' | 'funnel' | 'gauge' | 'heatmap';

/** 图表类型下拉选项（统一 9 种，两处共用） */
export const chartTypeOptions: Array<{ label: string; value: ChartType }> = [
  { label: $t('page.bi.metrics.chartTypes.bar'), value: 'bar' },
  { label: $t('page.bi.metrics.chartTypes.line'), value: 'line' },
  { label: $t('page.bi.metrics.chartTypes.area'), value: 'area' },
  { label: $t('page.bi.metrics.chartTypes.pie'), value: 'pie' },
  { label: $t('page.bi.metrics.chartTypes.scatter'), value: 'scatter' },
  { label: $t('page.bi.metrics.chartTypes.radar'), value: 'radar' },
  { label: $t('page.bi.metrics.chartTypes.funnel'), value: 'funnel' },
  { label: $t('page.bi.metrics.chartTypes.gauge'), value: 'gauge' },
  { label: $t('page.bi.metrics.chartTypes.heatmap'), value: 'heatmap' }
];

/** SQL 结果形状（与 Api.Bi.ChatSqlResult 对齐，避免循环依赖） */
export interface ChartSqlResult {
  columns: string[];
  rows: Array<Record<string, any>>;
}

/** 判断值是否为数值 */
export function isNumeric(v: any): boolean {
  if (typeof v === 'number') return !Number.isNaN(v);
  if (typeof v === 'string' && v !== '') return !Number.isNaN(Number(v));
  return false;
}

/** 取数值列名列表 */
export function getNumericColumns(result: ChartSqlResult): string[] {
  const cols = result.columns || [];
  const rows = result.rows || [];
  return cols.filter(c => rows.some(r => isNumeric(r[c])));
}

/**
 * 自动检测 X/Y 轴字段（与 SQL 工作台原 autoDetectChartColumns 逻辑一致）。
 *
 * - X：默认取第一列
 * - Y：默认取首个非 X 的数值列；无数值列时回退到第二列
 */
export function autoDetectXY(result: ChartSqlResult): { xCol: string; yCol: string } {
  const cols = result.columns || [];
  if (!cols.length) return { xCol: '', yCol: '' };
  const xCol = cols[0];
  const numericCols = getNumericColumns(result);
  const yCol = numericCols.find(c => c !== xCol) ?? numericCols[0] ?? cols[1] ?? xCol;
  return { xCol, yCol };
}

/**
 * 构建 ECharts option（统一入口，9 种图表类型）。
 *
 * @param result SQL 结果
 * @param chartType 图表类型
 * @param xCol X 轴/类别字段（pie/funnel/gauge 用作 name，scatter 用作 X 值，heatmap 用作 X 轴）
 * @param yCol Y 轴/数值字段（pie/funnel/gauge 用作 value，scatter 用作 Y 值，heatmap 用作 Y 轴）
 */
export function buildChartOption(result: ChartSqlResult, chartType: ChartType, xCol: string, yCol: string): ECOption {
  const rows = result.rows || [];
  if (!rows.length || !xCol || !yCol) return {} as ECOption;

  switch (chartType) {
    case 'pie': {
      return {
        tooltip: { trigger: 'item' },
        legend: { orient: 'vertical', left: 'left' },
        series: [
          {
            type: 'pie',
            radius: '60%',
            name: yCol,
            data: rows.map(r => ({ name: String(r[xCol] ?? ''), value: Number(r[yCol]) || 0 }))
          }
        ]
      } as ECOption;
    }

    case 'scatter': {
      return {
        tooltip: { trigger: 'item' },
        xAxis: { type: 'value', name: xCol },
        yAxis: { type: 'value', name: yCol },
        series: [
          {
            type: 'scatter',
            name: yCol,
            data: rows.map(r => [Number(r[xCol]) || 0, Number(r[yCol]) || 0])
          }
        ]
      } as ECOption;
    }

    case 'radar': {
      // 雷达图：每个维度对应一个 xCol 类别，每行一个数据系列
      const indicators = rows.map(r => ({
        name: String(r[xCol] ?? ''),
        max: Math.max(...rows.map(rr => Number(rr[yCol]) || 0)) * 1.2 || 100
      }));
      return {
        tooltip: { trigger: 'item' },
        radar: { indicator: indicators },
        series: [
          {
            type: 'radar',
            name: yCol,
            data: [{ value: rows.map(r => Number(r[yCol]) || 0), name: yCol }]
          }
        ]
      } as ECOption;
    }

    case 'funnel': {
      return {
        tooltip: { trigger: 'item', formatter: '{b}: {c}' },
        legend: { orient: 'vertical', left: 'left' },
        series: [
          {
            type: 'funnel',
            name: yCol,
            sort: 'descending',
            data: rows.map(r => ({ name: String(r[xCol] ?? ''), value: Number(r[yCol]) || 0 }))
          }
        ]
      } as ECOption;
    }

    case 'gauge': {
      // 仪表盘：取第一行 Y 值，归一化到 0-100
      const value = Number(rows[0]?.[yCol]) || 0;
      return {
        tooltip: { formatter: '{a} <br/>{b}: {c}%' },
        series: [
          {
            type: 'gauge',
            name: yCol,
            progress: { show: true, width: 18 },
            axisLine: { lineStyle: { width: 18 } },
            detail: { valueAnimation: true, formatter: '{value}' },
            data: [{ value, name: xCol }]
          }
        ]
      } as ECOption;
    }

    case 'heatmap': {
      // 热力图：X 轴=类别，Y 轴=数值列名（这里简化为单列数值的热力分布）
      const xData = rows.map(r => String(r[xCol] ?? ''));
      const yData = [yCol];
      const data: Array<[number, number, number]> = rows.map((r, i) => [i, 0, Number(r[yCol]) || 0]);
      const values = data.map(d => d[2]);
      const min = Math.min(...values);
      const max = Math.max(...values);
      return {
        tooltip: { position: 'top' },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true, top: '15%' },
        xAxis: { type: 'category', data: xData },
        yAxis: { type: 'category', data: yData },
        visualMap: {
          min: min === max ? min - 1 : min,
          max: max === min ? max + 1 : max,
          calculable: true,
          orient: 'horizontal',
          left: 'center',
          bottom: '0%'
        },
        series: [
          {
            type: 'heatmap',
            name: yCol,
            data,
            label: { show: true }
          }
        ]
      } as ECOption;
    }

    case 'area': {
      // 面积图：基于 line，叠加 areaStyle
      return {
        tooltip: { trigger: 'axis' },
        legend: { data: [yCol], top: 0 },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true, top: '15%' },
        xAxis: { type: 'category', data: rows.map(r => String(r[xCol] ?? '')) },
        yAxis: { type: 'value' },
        series: [
          {
            type: 'line',
            name: yCol,
            areaStyle: {},
            data: rows.map(r => Number(r[yCol]) || 0)
          }
        ]
      } as ECOption;
    }

    // bar / line 默认分支
    default: {
      return {
        tooltip: { trigger: 'axis' },
        legend: { data: [yCol], top: 0 },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true, top: '15%' },
        xAxis: { type: 'category', data: rows.map(r => String(r[xCol] ?? '')) },
        yAxis: { type: 'value' },
        series: [
          {
            type: chartType as 'bar' | 'line',
            name: yCol,
            data: rows.map(r => Number(r[yCol]) || 0)
          }
        ]
      } as ECOption;
    }
  }
}
