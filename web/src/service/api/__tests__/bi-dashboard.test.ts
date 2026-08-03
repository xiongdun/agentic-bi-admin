import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Mock the request module to avoid pulling in Vue-aware dependencies (auth store, layouts, etc.).
// bi-dashboard.ts imports `request` from `../request`; from this test file that resolves to `../../request`.
const mockRequest = vi.fn();
vi.mock('../../request', () => ({
  request: mockRequest
}));

const {
  fetchBiDashboardList,
  fetchBiDashboardDetail,
  fetchCreateBiDashboard,
  fetchUpdateBiDashboard,
  fetchDeleteBiDashboard,
  fetchRefreshBiDashboard,
  fetchPreviewBiDashboard
} = await import('../bi-dashboard');

describe('BI Dashboard API Service', () => {
  beforeEach(() => {
    mockRequest.mockReset();
    mockRequest.mockResolvedValue({ data: null, error: null });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('fetchBiDashboardList', () => {
    it('should POST to /business/bi/dashboards/search with provided params', async () => {
      const params = { current: 1, size: 10, name: 'sales' };
      await fetchBiDashboardList(params);
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/dashboards/search',
        method: 'post',
        data: params
      });
    });

    it('should default to empty object when no params', async () => {
      await fetchBiDashboardList();
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/dashboards/search',
        method: 'post',
        data: {}
      });
    });
  });

  describe('fetchBiDashboardDetail', () => {
    it('should GET dashboard by id', async () => {
      await fetchBiDashboardDetail('abc123');
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/dashboards/abc123',
        method: 'get'
      });
    });
  });

  describe('fetchCreateBiDashboard', () => {
    it('should POST payload to /business/bi/dashboards', async () => {
      const payload = {
        name: 'My Dashboard',
        description: 'desc',
        layout: { items: [{ chartId: 'c1', x: 0, y: 0, w: 6, h: 3 }] }
      };
      await fetchCreateBiDashboard(payload);
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/dashboards',
        method: 'post',
        data: payload
      });
    });

    it('should accept null description', async () => {
      const payload = {
        name: 'No Desc',
        description: null,
        layout: { items: [] }
      };
      await fetchCreateBiDashboard(payload);
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/dashboards',
        method: 'post',
        data: payload
      });
    });
  });

  describe('fetchUpdateBiDashboard', () => {
    it('should PUT payload to /business/bi/dashboards/{id}', async () => {
      const payload = {
        name: 'Updated',
        description: 'updated desc',
        layout: { items: [{ chartId: 'c1', x: 0, y: 0, w: 12, h: 4 }] }
      };
      await fetchUpdateBiDashboard('dash-1', payload);
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/dashboards/dash-1',
        method: 'put',
        data: payload
      });
    });
  });

  describe('fetchDeleteBiDashboard', () => {
    it('should DELETE dashboard by id', async () => {
      await fetchDeleteBiDashboard('dash-9');
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/dashboards/dash-9',
        method: 'delete'
      });
    });
  });

  describe('fetchRefreshBiDashboard', () => {
    it('should POST refresh to /business/bi/dashboards/{id}/refresh', async () => {
      await fetchRefreshBiDashboard('dash-1');
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/dashboards/dash-1/refresh',
        method: 'post'
      });
    });
  });

  describe('fetchPreviewBiDashboard', () => {
    it('should GET preview from /business/bi/dashboards/{id}/preview', async () => {
      await fetchPreviewBiDashboard('dash-1');
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/dashboards/dash-1/preview',
        method: 'get'
      });
    });
  });
});
