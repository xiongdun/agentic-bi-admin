import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Mock the request module to avoid pulling in Vue-aware dependencies (auth store, layouts, etc.).
// bi-masking.ts imports `request` from `../request`; from this test file that resolves to `../../request`.
const mockRequest = vi.fn();
vi.mock('../../request', () => ({
  request: mockRequest
}));

const {
  fetchBiMaskingList,
  fetchBiMasking,
  fetchAddBiMasking,
  fetchUpdateBiMasking,
  fetchDeleteBiMasking,
  fetchBatchDeleteBiMasking
} = await import('../bi-masking');

describe('BI Masking API Service', () => {
  beforeEach(() => {
    mockRequest.mockReset();
    mockRequest.mockResolvedValue({ data: null, error: null });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('fetchBiMaskingList', () => {
    it('should POST to /business/bi/masking/search with provided params', async () => {
      const params = { current: 1, size: 10, name: 'phone-mask' };
      await fetchBiMaskingList(params);
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/masking/search',
        method: 'post',
        data: params
      });
    });

    it('should default to empty object when no params', async () => {
      await fetchBiMaskingList();
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/masking/search',
        method: 'post',
        data: {}
      });
    });
  });

  describe('fetchBiMasking', () => {
    it('should GET masking rule by id', async () => {
      await fetchBiMasking('abc123');
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/masking/abc123',
        method: 'get'
      });
    });
  });

  describe('fetchAddBiMasking', () => {
    it('should POST payload to /business/bi/masking', async () => {
      const payload = {
        name: 'Phone Mask',
        columnPattern: '^phone$',
        maskType: 'phone' as const,
        maskChar: '*',
        keepPrefix: 3,
        keepSuffix: 4,
        statusType: '1' as const
      };
      await fetchAddBiMasking(payload);
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/masking',
        method: 'post',
        data: payload
      });
    });
  });

  describe('fetchUpdateBiMasking', () => {
    it('should PUT payload to /business/bi/masking/{id}', async () => {
      const payload = {
        id: 'mask-1',
        name: 'Updated',
        columnPattern: '^phone$',
        maskType: 'phone' as const
      };
      await fetchUpdateBiMasking(payload);
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/masking/mask-1',
        method: 'put',
        data: payload
      });
    });
  });

  describe('fetchDeleteBiMasking', () => {
    it('should DELETE masking rule by id', async () => {
      await fetchDeleteBiMasking({ id: 'mask-9' });
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/masking/mask-9',
        method: 'delete'
      });
    });
  });

  describe('fetchBatchDeleteBiMasking', () => {
    it('should DELETE /business/bi/masking with ids payload', async () => {
      const payload = { ids: ['mask-1', 'mask-2'] };
      await fetchBatchDeleteBiMasking(payload);
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/masking',
        method: 'delete',
        data: payload
      });
    });
  });
});
