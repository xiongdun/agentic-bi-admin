import { describe, expect, it, vi } from 'vitest';

// Mock heavy deps so chart-config.ts can be imported in isolation.
vi.mock('@/locales', () => ({
  $t: (key: string) => key
}));

vi.mock('@/hooks/common/echarts', () => ({
  // ECOption is a type-only export; provide a plain object cast target.
  useEcharts: () => ({ domRef: { value: null }, setOptions: () => {} })
}));

import type { ChartType } from '../chart-config';

const { isNumeric, getNumericColumns, autoDetectXY, buildChartOption } = await import('../chart-config');

describe('chart-config: isNumeric', () => {
  it('should return true for finite numbers', () => {
    expect(isNumeric(0)).toBe(true);
    expect(isNumeric(42)).toBe(true);
    expect(isNumeric(-1.5)).toBe(true);
  });

  it('should return true for numeric strings', () => {
    expect(isNumeric('0')).toBe(true);
    expect(isNumeric('123')).toBe(true);
    expect(isNumeric('3.14')).toBe(true);
  });

  it('should return false for NaN', () => {
    expect(isNumeric(Number.NaN)).toBe(false);
  });

  it('should return false for empty strings', () => {
    expect(isNumeric('')).toBe(false);
  });

  it('should return false for non-numeric strings', () => {
    expect(isNumeric('abc')).toBe(false);
    expect(isNumeric('12px')).toBe(false);
  });

  it('should return false for null/undefined/objects', () => {
    expect(isNumeric(null)).toBe(false);
    expect(isNumeric(undefined)).toBe(false);
    expect(isNumeric({})).toBe(false);
  });
});

describe('chart-config: getNumericColumns', () => {
  it('should return columns that have at least one numeric value', () => {
    const result = {
      columns: ['name', 'age', 'score'],
      rows: [
        { name: 'Alice', age: 30, score: '95' },
        { name: 'Bob', age: 25, score: '88' }
      ]
    };
    expect(getNumericColumns(result)).toEqual(['age', 'score']);
  });

  it('should return empty for empty rows', () => {
    const result = { columns: ['a', 'b'], rows: [] };
    expect(getNumericColumns(result)).toEqual([]);
  });

  it('should handle missing column values gracefully', () => {
    const result = {
      columns: ['x', 'y'],
      rows: [
        { x: 'foo', y: null },
        { x: 'bar', y: 5 }
      ]
    };
    expect(getNumericColumns(result)).toEqual(['y']);
  });
});

describe('chart-config: autoDetectXY', () => {
  it('should pick first column as X and first non-X numeric column as Y', () => {
    const result = {
      columns: ['category', 'count', 'name'],
      rows: [
        { category: 'A', count: 10, name: 'A' },
        { category: 'B', count: 20, name: 'B' }
      ]
    };
    expect(autoDetectXY(result)).toEqual({ xCol: 'category', yCol: 'count' });
  });

  it('should fall back to second column when no numeric columns exist', () => {
    const result = {
      columns: ['a', 'b', 'c'],
      rows: [{ a: 'x', b: 'y', c: 'z' }]
    };
    expect(autoDetectXY(result)).toEqual({ xCol: 'a', yCol: 'b' });
  });

  it('should return empty strings for empty columns', () => {
    expect(autoDetectXY({ columns: [], rows: [] })).toEqual({ xCol: '', yCol: '' });
  });

  it('should fall back to first column when only one column exists', () => {
    const result = { columns: ['only'], rows: [{ only: 1 }] };
    expect(autoDetectXY(result)).toEqual({ xCol: 'only', yCol: 'only' });
  });
});

describe('chart-config: buildChartOption', () => {
  const sampleResult = {
    columns: ['month', 'sales'],
    rows: [
      { month: 'Jan', sales: 100 },
      { month: 'Feb', sales: 200 },
      { month: 'Mar', sales: 150 }
    ]
  };

  it('should return empty option when rows is empty', () => {
    const opt = buildChartOption({ columns: ['a', 'b'], rows: [] }, 'bar', 'a', 'b');
    expect(opt).toEqual({});
  });

  it('should return empty option when xCol is missing', () => {
    const opt = buildChartOption(sampleResult, 'bar', '', 'sales');
    expect(opt).toEqual({});
  });

  it('should return empty option when yCol is missing', () => {
    const opt = buildChartOption(sampleResult, 'bar', 'month', '');
    expect(opt).toEqual({});
  });

  it('should build bar chart with category x-axis and value y-axis', () => {
    const opt = buildChartOption(sampleResult, 'bar', 'month', 'sales') as any;
    expect(opt.series[0].type).toBe('bar');
    expect(opt.xAxis.data).toEqual(['Jan', 'Feb', 'Mar']);
    expect(opt.series[0].data).toEqual([100, 200, 150]);
  });

  it('should build line chart with same shape as bar', () => {
    const opt = buildChartOption(sampleResult, 'line', 'month', 'sales') as any;
    expect(opt.series[0].type).toBe('line');
    expect(opt.series[0].data).toEqual([100, 200, 150]);
  });

  it('should build area chart as line with areaStyle', () => {
    const opt = buildChartOption(sampleResult, 'area', 'month', 'sales') as any;
    expect(opt.series[0].type).toBe('line');
    expect(opt.series[0].areaStyle).toBeDefined();
  });

  it('should build pie chart with name/value pairs', () => {
    const opt = buildChartOption(sampleResult, 'pie', 'month', 'sales') as any;
    expect(opt.series[0].type).toBe('pie');
    expect(opt.series[0].data).toEqual([
      { name: 'Jan', value: 100 },
      { name: 'Feb', value: 200 },
      { name: 'Mar', value: 150 }
    ]);
  });

  it('should build funnel chart with name/value pairs', () => {
    const opt = buildChartOption(sampleResult, 'funnel', 'month', 'sales') as any;
    expect(opt.series[0].type).toBe('funnel');
    expect(opt.series[0].sort).toBe('descending');
    expect(opt.series[0].data).toHaveLength(3);
  });

  it('should build scatter chart with [x, y] pairs', () => {
    const opt = buildChartOption(sampleResult, 'scatter', 'month', 'sales') as any;
    expect(opt.series[0].type).toBe('scatter');
    expect(opt.series[0].data[0]).toHaveLength(2);
  });

  it('should build radar chart with indicators from rows', () => {
    const opt = buildChartOption(sampleResult, 'radar', 'month', 'sales') as any;
    expect(opt.series[0].type).toBe('radar');
    expect(opt.radar.indicator).toHaveLength(3);
    expect(opt.radar.indicator[0].name).toBe('Jan');
  });

  it('should build gauge chart using first row value', () => {
    const opt = buildChartOption(sampleResult, 'gauge', 'month', 'sales') as any;
    expect(opt.series[0].type).toBe('gauge');
    expect(opt.series[0].data[0].value).toBe(100);
    expect(opt.series[0].data[0].name).toBe('month');
  });

  it('should build heatmap chart with x/y category axes', () => {
    const opt = buildChartOption(sampleResult, 'heatmap', 'month', 'sales') as any;
    expect(opt.series[0].type).toBe('heatmap');
    expect(opt.xAxis.data).toEqual(['Jan', 'Feb', 'Mar']);
    expect(opt.yAxis.data).toEqual(['sales']);
    expect(opt.series[0].data[0]).toEqual([0, 0, 100]);
  });

  it('should coerce non-numeric y values to 0', () => {
    const result = {
      columns: ['m', 'v'],
      rows: [
        { m: 'A', v: 'not-a-number' },
        { m: 'B', v: null }
      ]
    };
    const opt = buildChartOption(result, 'bar', 'm', 'v') as any;
    expect(opt.series[0].data).toEqual([0, 0]);
  });

  it('should handle unknown chartType by falling through to default branch (bar/line shape)', () => {
    // The default branch casts chartType to 'bar' | 'line'; passing an unknown
    // still produces the default-shape option. We assert the series data is present.
    const opt = buildChartOption(sampleResult, 'unknown' as ChartType, 'month', 'sales') as any;
    expect(opt.series).toBeDefined();
    expect(opt.series[0].data).toEqual([100, 200, 150]);
  });
});
