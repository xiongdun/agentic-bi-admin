import { request } from '../request';

/** 脱敏规则分页搜索 */
export function fetchBiMaskingList(data?: Api.Bi.BiMaskingRuleSearchParams) {
  return request<Api.Bi.BiMaskingRuleList>({
    url: '/business/bi/masking/search',
    method: 'post',
    data: data ?? {}
  });
}

/** 获取脱敏规则详情 */
export function fetchBiMasking(id: string) {
  return request<Api.Bi.BiMaskingRule>({
    url: `/business/bi/masking/${id}`,
    method: 'get'
  });
}

/** 创建脱敏规则 */
export function fetchAddBiMasking(data: Api.Bi.BiMaskingRuleOperateParams) {
  return request<Api.Bi.CreateResult>({
    url: '/business/bi/masking',
    method: 'post',
    data
  });
}

/** 更新脱敏规则 */
export function fetchUpdateBiMasking(data: Api.Bi.BiMaskingRuleOperateParams) {
  return request<Api.Bi.UpdateResult>({
    url: `/business/bi/masking/${data.id}`,
    method: 'put',
    data
  });
}

/** 删除脱敏规则 */
export function fetchDeleteBiMasking(data: Api.Bi.CommonDeleteParams) {
  return request<null>({
    url: `/business/bi/masking/${data.id}`,
    method: 'delete'
  });
}

/** 批量删除脱敏规则 */
export function fetchBatchDeleteBiMasking(data: Api.Bi.CommonBatchDeleteParams) {
  return request<null>({
    url: '/business/bi/masking',
    method: 'delete',
    data
  });
}
