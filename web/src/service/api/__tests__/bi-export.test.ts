import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Mock the request module to avoid pulling in Vue-aware dependencies (auth store, layouts, etc.).
// bi-export.ts imports `request` from `../request`; from this test file that resolves to `../../request`.
const mockRequest = vi.fn();
vi.mock('../../request', () => ({
  request: mockRequest
}));

const { fetchBiChartCsvExport, fetchBiChartsExcelExport, fetchBiDashboardExcelExport } = await import('../bi-export');

describe('BI Export API Service', () => {
  beforeEach(() => {
    mockRequest.mockReset();
    mockRequest.mockResolvedValue({ data: null, error: null });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('fetchBiChartCsvExport', () => {
    it('should GET blob from /business/bi/export/charts/{id}/csv', async () => {
      await fetchBiChartCsvExport('chart-1');
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/export/charts/chart-1/csv',
        method: 'get',
        responseType: 'blob'
      });
    });
  });

  describe('fetchBiChartsExcelExport', () => {
    it('should POST chartIds to /business/bi/export/charts/excel as blob', async () => {
      const payload = { chartIds: ['chart-1', 'chart-2'] };
      await fetchBiChartsExcelExport(payload);
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/export/charts/excel',
        method: 'post',
        data: payload,
        responseType: 'blob'
      });
    });
  });

  describe('fetchBiDashboardExcelExport', () => {
    it('should POST blob to /business/bi/export/dashboards/{id}/excel', async () => {
      await fetchBiDashboardExcelExport('dash-1');
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/export/dashboards/dash-1/excel',
        method: 'post',
        responseType: 'blob'
      });
    });
  });
});
