import { request } from '../request';

/** 配额配置分页搜索 */
export function fetchBiQuotaList(data?: Api.Bi.BiQuotaConfigSearchParams) {
  return request<Api.Bi.BiQuotaConfigList>({
    url: '/business/bi/quota/search',
    method: 'post',
    data: data ?? {}
  });
}

/** 获取配额配置详情 */
export function fetchBiQuota(id: string) {
  return request<Api.Bi.BiQuotaConfig>({
    url: `/business/bi/quota/${id}`,
    method: 'get'
  });
}

/** 创建配额配置 */
export function fetchAddBiQuota(data: Api.Bi.BiQuotaConfigOperateParams) {
  return request<Api.Bi.CreateResult>({
    url: '/business/bi/quota',
    method: 'post',
    data
  });
}

/** 更新配额配置 */
export function fetchUpdateBiQuota(data: Api.Bi.BiQuotaConfigOperateParams) {
  return request<Api.Bi.UpdateResult>({
    url: `/business/bi/quota/${data.id}`,
    method: 'put',
    data
  });
}

/** 删除配额配置 */
export function fetchDeleteBiQuota(data: Api.Bi.CommonDeleteParams) {
  return request<null>({
    url: `/business/bi/quota/${data.id}`,
    method: 'delete'
  });
}

/** 批量删除配额配置 */
export function fetchBatchDeleteBiQuota(data: Api.Bi.CommonBatchDeleteParams) {
  return request<null>({
    url: '/business/bi/quota',
    method: 'delete',
    data
  });
}
