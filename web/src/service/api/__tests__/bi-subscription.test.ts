import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Mock the request module to avoid pulling in Vue-aware dependencies (auth store, layouts, etc.).
// bi-subscription.ts imports `request` from `../request`; from this test file that resolves to `../../request`.
const mockRequest = vi.fn();
vi.mock('../../request', () => ({
  request: mockRequest
}));

const {
  fetchBiSubscriptionList,
  fetchBiSubscription,
  fetchAddBiSubscription,
  fetchUpdateBiSubscription,
  fetchDeleteBiSubscription,
  fetchBatchDeleteBiSubscription
} = await import('../bi-subscription');

describe('BI Subscription API Service', () => {
  beforeEach(() => {
    mockRequest.mockReset();
    mockRequest.mockResolvedValue({ data: null, error: null });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('fetchBiSubscriptionList', () => {
    it('should POST to /business/bi/subscriptions/search with provided params', async () => {
      const params = { current: 1, size: 10, name: 'daily' };
      await fetchBiSubscriptionList(params);
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/subscriptions/search',
        method: 'post',
        data: params
      });
    });

    it('should default to empty object when no params', async () => {
      await fetchBiSubscriptionList();
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/subscriptions/search',
        method: 'post',
        data: {}
      });
    });
  });

  describe('fetchBiSubscription', () => {
    it('should GET subscription by id', async () => {
      await fetchBiSubscription('sub-123');
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/subscriptions/sub-123',
        method: 'get'
      });
    });
  });

  describe('fetchAddBiSubscription', () => {
    it('should POST payload to /business/bi/subscriptions', async () => {
      const payload = {
        name: '每日经营日报',
        dashboardId: 'dash-1',
        cronExpr: '0 9 * * *',
        statusType: '1' as const
      };
      await fetchAddBiSubscription(payload);
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/subscriptions',
        method: 'post',
        data: payload
      });
    });
  });

  describe('fetchUpdateBiSubscription', () => {
    it('should PUT payload to /business/bi/subscriptions/{id}', async () => {
      const payload = {
        id: 'sub-1',
        name: 'Updated',
        dashboardId: 'dash-1',
        cronExpr: '0 9 * * *'
      };
      await fetchUpdateBiSubscription(payload);
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/subscriptions/sub-1',
        method: 'put',
        data: payload
      });
    });
  });

  describe('fetchDeleteBiSubscription', () => {
    it('should DELETE subscription by id', async () => {
      await fetchDeleteBiSubscription({ id: 'sub-9' });
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/subscriptions/sub-9',
        method: 'delete'
      });
    });
  });

  describe('fetchBatchDeleteBiSubscription', () => {
    it('should DELETE /business/bi/subscriptions/batch_delete with ids payload', async () => {
      const payload = { ids: ['sub-1', 'sub-2'] };
      await fetchBatchDeleteBiSubscription(payload);
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/subscriptions/batch_delete',
        method: 'delete',
        data: payload
      });
    });
  });
});
