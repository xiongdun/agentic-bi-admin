import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Mock the request module to avoid pulling in Vue-aware dependencies (auth store, layouts, etc.).
// bi-quota.ts imports `request` from `../request`; from this test file that resolves to `../../request`.
const mockRequest = vi.fn();
vi.mock('../../request', () => ({
  request: mockRequest
}));

const {
  fetchBiQuotaList,
  fetchBiQuota,
  fetchAddBiQuota,
  fetchUpdateBiQuota,
  fetchDeleteBiQuota,
  fetchBatchDeleteBiQuota
} = await import('../bi-quota');

describe('BI Quota API Service', () => {
  beforeEach(() => {
    mockRequest.mockReset();
    mockRequest.mockResolvedValue({ data: null, error: null });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('fetchBiQuotaList', () => {
    it('should POST to /business/bi/quota/search with provided params', async () => {
      const params = { current: 1, size: 10, name: 'global-quota' };
      await fetchBiQuotaList(params);
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/quota/search',
        method: 'post',
        data: params
      });
    });

    it('should default to empty object when no params', async () => {
      await fetchBiQuotaList();
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/quota/search',
        method: 'post',
        data: {}
      });
    });
  });

  describe('fetchBiQuota', () => {
    it('should GET quota config by id', async () => {
      await fetchBiQuota('abc123');
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/quota/abc123',
        method: 'get'
      });
    });
  });

  describe('fetchAddBiQuota', () => {
    it('should POST payload to /business/bi/quota', async () => {
      const payload = {
        name: 'Global Quota',
        scopeType: 'global' as const,
        maxRows: 10000,
        timeoutSeconds: 30,
        statusType: '1' as const
      };
      await fetchAddBiQuota(payload);
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/quota',
        method: 'post',
        data: payload
      });
    });
  });

  describe('fetchUpdateBiQuota', () => {
    it('should PUT payload to /business/bi/quota/{id}', async () => {
      const payload = {
        id: 'quota-1',
        name: 'Updated',
        scopeType: 'user' as const
      };
      await fetchUpdateBiQuota(payload);
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/quota/quota-1',
        method: 'put',
        data: payload
      });
    });
  });

  describe('fetchDeleteBiQuota', () => {
    it('should DELETE quota config by id', async () => {
      await fetchDeleteBiQuota({ id: 'quota-9' });
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/quota/quota-9',
        method: 'delete'
      });
    });
  });

  describe('fetchBatchDeleteBiQuota', () => {
    it('should DELETE /business/bi/quota with ids payload', async () => {
      const payload = { ids: ['quota-1', 'quota-2'] };
      await fetchBatchDeleteBiQuota(payload);
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/quota',
        method: 'delete',
        data: payload
      });
    });
  });
});
