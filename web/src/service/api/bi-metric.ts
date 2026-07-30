import { request } from '../request';

/** 指标分页搜索 */
export function fetchBiMetricList(data?: Api.Bi.BiMetricSearchParams) {
  return request<Api.Bi.BiMetricList>({
    url: '/business/bi/metrics/search',
    method: 'post',
    data: data ?? {}
  });
}

/** 获取指标详情 */
export function fetchBiMetric(id: string) {
  return request<Api.Bi.BiMetric>({
    url: `/business/bi/metrics/${id}`,
    method: 'get'
  });
}

/** 创建指标 */
export function fetchAddBiMetric(data: Api.Bi.BiMetricOperateParams) {
  return request<Api.Bi.CreateResult>({
    url: '/business/bi/metrics',
    method: 'post',
    data
  });
}

/** 更新指标 */
export function fetchUpdateBiMetric(data: Api.Bi.BiMetricOperateParams) {
  return request<Api.Bi.UpdateResult>({
    url: `/business/bi/metrics/${data.id}`,
    method: 'put',
    data
  });
}

/** 删除指标 */
export function fetchDeleteBiMetric(data: Api.Bi.CommonDeleteParams) {
  return request<null>({
    url: `/business/bi/metrics/${data.id}`,
    method: 'delete'
  });
}

/** 批量删除指标 */
export function fetchBatchDeleteBiMetric(data: Api.Bi.CommonBatchDeleteParams) {
  return request<null>({
    url: '/business/bi/metrics',
    method: 'delete',
    data
  });
}

/** 测试指标（在绑定的数据源上执行 SQL 模板） */
export function fetchTestBiMetric(id: string) {
  return request<Api.Bi.BiMetricTestResult>({
    url: `/business/bi/metrics/${id}/test`,
    method: 'post'
  });
}
