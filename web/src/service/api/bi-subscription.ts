import { request } from '../request';

/** 订阅分页搜索 */
export function fetchBiSubscriptionList(data?: Api.Bi.BiSubscriptionSearchParams) {
  return request<Api.Bi.BiSubscriptionList>({
    url: '/business/bi/subscriptions/search',
    method: 'post',
    data: data ?? {}
  });
}

/** 获取订阅详情 */
export function fetchBiSubscription(id: string) {
  return request<Api.Bi.BiSubscription>({
    url: `/business/bi/subscriptions/${id}`,
    method: 'get'
  });
}

/** 创建订阅 */
export function fetchAddBiSubscription(data: Api.Bi.BiSubscriptionOperateParams) {
  return request<Api.Bi.CreateResult>({
    url: '/business/bi/subscriptions',
    method: 'post',
    data
  });
}

/** 更新订阅 */
export function fetchUpdateBiSubscription(data: Api.Bi.BiSubscriptionOperateParams) {
  return request<Api.Bi.UpdateResult>({
    url: `/business/bi/subscriptions/${data.id}`,
    method: 'put',
    data
  });
}

/** 删除订阅 */
export function fetchDeleteBiSubscription(data: Api.Bi.CommonDeleteParams) {
  return request<null>({
    url: `/business/bi/subscriptions/${data.id}`,
    method: 'delete'
  });
}

/** 批量删除订阅 */
export function fetchBatchDeleteBiSubscription(data: Api.Bi.CommonBatchDeleteParams) {
  return request<null>({
    url: '/business/bi/subscriptions/batch_delete',
    method: 'delete',
    data
  });
}
