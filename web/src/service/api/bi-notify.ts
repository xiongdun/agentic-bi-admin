import { request } from '../request';

/** 消息记录分页搜索 */
export function fetchBiNotifyList(data?: Api.Bi.BiNotifyRecordSearchParams) {
  return request<Api.Bi.BiNotifyRecordList>({
    url: '/business/bi/notify/search',
    method: 'post',
    data: data ?? {}
  });
}

/** 获取未读消息数（铃铛组件轮询） */
export function fetchBiNotifyUnreadCount() {
  return request<Api.Bi.BiNotifyUnreadCount>({
    url: '/business/bi/notify/unread-count',
    method: 'get'
  });
}

/** 标记消息已读 */
export function fetchMarkBiNotifyRead(id: string) {
  return request<null>({
    url: `/business/bi/notify/${id}/read`,
    method: 'put'
  });
}
