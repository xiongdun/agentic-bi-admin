import { request } from '../request';

// ---- Metric ----

/** 分页搜索 metric */
export function fetchBiMetricList(data: Api.Bi.MetricSearchParams) {
  return request<Api.Bi.MetricList>({
    url: '/business/bi/metrics/search',
    method: 'post',
    data
  });
}

/** 创建 metric */
export function fetchCreateBiMetric(data: Api.Bi.MetricCreateParams) {
  return request<{ createdId: string }>({
    url: '/business/bi/metrics',
    method: 'post',
    data
  });
}

/** 更新 metric */
export function fetchUpdateBiMetric(id: string, data: Api.Bi.MetricUpdateParams) {
  return request<{ updatedId: string }>({
    url: `/business/bi/metrics/${id}`,
    method: 'patch',
    data
  });
}

/** 删除 metric */
export function fetchDeleteBiMetric(id: string) {
  return request({
    url: `/business/bi/metrics/${id}`,
    method: 'delete'
  });
}

/** 校验 metric SQL 模板（占位符 + sqlglot + 白名单） */
export function fetchTestBiMetric(id: string) {
  return request<Api.Bi.MetricTestResult>({
    url: `/business/bi/metrics/${id}/test`,
    method: 'post'
  });
}
