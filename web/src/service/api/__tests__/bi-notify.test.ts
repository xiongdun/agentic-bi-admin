import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Mock the request module to avoid pulling in Vue-aware dependencies (auth store, layouts, etc.).
// bi-notify.ts imports `request` from `../request`; from this test file that resolves to `../../request`.
const mockRequest = vi.fn();
vi.mock('../../request', () => ({
  request: mockRequest
}));

const { fetchBiNotifyList, fetchBiNotifyUnreadCount, fetchMarkBiNotifyRead } = await import('../bi-notify');

describe('BI Notify API Service', () => {
  beforeEach(() => {
    mockRequest.mockReset();
    mockRequest.mockResolvedValue({ data: null, error: null });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('fetchBiNotifyList', () => {
    it('should POST to /business/bi/notify/search with provided params', async () => {
      const params = { current: 1, size: 10, status: 'success' as const, isRead: false };
      await fetchBiNotifyList(params);
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/notify/search',
        method: 'post',
        data: params
      });
    });

    it('should default to empty object when no params', async () => {
      await fetchBiNotifyList();
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/notify/search',
        method: 'post',
        data: {}
      });
    });
  });

  describe('fetchBiNotifyUnreadCount', () => {
    it('should GET /business/bi/notify/unread-count', async () => {
      await fetchBiNotifyUnreadCount();
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/notify/unread-count',
        method: 'get'
      });
    });
  });

  describe('fetchMarkBiNotifyRead', () => {
    it('should PUT /business/bi/notify/{id}/read', async () => {
      await fetchMarkBiNotifyRead('notify-1');
      expect(mockRequest).toHaveBeenCalledWith({
        url: '/business/bi/notify/notify-1/read',
        method: 'put'
      });
    });
  });
});
