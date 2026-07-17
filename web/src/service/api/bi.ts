import { request } from '../request';

// ---- Datasource ----

/** 搜索数据源 */
export function fetchBiDatasourceList(data: Api.Bi.DatasourceSearchParams) {
  return request<Api.Bi.DatasourceList>({
    url: '/business/bi/datasources/search',
    method: 'post',
    data
  });
}

/** 创建数据源 */
export function fetchCreateBiDatasource(data: Api.Bi.DatasourceAddParams) {
  return request<{ createdId: string }>({
    url: '/business/bi/datasources',
    method: 'post',
    data
  });
}

/** 更新数据源 */
export function fetchUpdateBiDatasource(id: string, data: Api.Bi.DatasourceUpdateParams) {
  return request<{ updatedId: string }>({
    url: `/business/bi/datasources/${id}`,
    method: 'patch',
    data
  });
}

/** 删除数据源 */
export function fetchDeleteBiDatasource(id: string) {
  return request({
    url: `/business/bi/datasources/${id}`,
    method: 'delete'
  });
}

/** 测试数据源连接 */
export function fetchTestBiDatasource(id: string) {
  return request<Api.Bi.DatasourceTestResult>({
    url: `/business/bi/datasources/${id}/test`,
    method: 'post'
  });
}

/** 同步元数据 */
export function fetchSyncBiDatasource(id: string) {
  return request<Api.Bi.DatasourceSyncResult>({
    url: `/business/bi/datasources/${id}/sync`,
    method: 'post'
  });
}

/** 一键生成/重建电商 demo 库 */
export function fetchBootstrapBiDemo() {
  return request<Api.Bi.DemoBootstrapResult>({
    url: '/business/bi/datasources/demo',
    method: 'post'
  });
}

// ---- Table / Column ----

/** 搜索已同步的表 */
export function fetchBiTableList(data: Api.Bi.BiTableSearchParams) {
  return request<Api.Bi.BiTableList>({
    url: '/business/bi/metadata/tables/search',
    method: 'post',
    data
  });
}

/** 获取表详情（含列） */
export function fetchBiTableDetail(id: string) {
  return request<Api.Bi.BiTableDetail>({
    url: `/business/bi/metadata/tables/${id}`,
    method: 'get'
  });
}

// ---- LLM Provider / Model ----

/** 搜索 LLM 提供商 */
export function fetchBiModelProviderList(data: Api.Bi.ModelProviderSearchParams) {
  return request<Api.Bi.ModelProviderList>({
    url: '/business/bi/llm/providers/search',
    method: 'post',
    data
  });
}

/** 创建 LLM 提供商 */
export function fetchCreateBiModelProvider(data: Api.Bi.ModelProviderAddParams) {
  return request<{ createdId: string }>({
    url: '/business/bi/llm/providers',
    method: 'post',
    data
  });
}

/** 更新 LLM 提供商 */
export function fetchUpdateBiModelProvider(id: string, data: Api.Bi.ModelProviderUpdateParams) {
  return request<{ updatedId: string }>({
    url: `/business/bi/llm/providers/${id}`,
    method: 'patch',
    data
  });
}

/** 删除 LLM 提供商 */
export function fetchDeleteBiModelProvider(id: string) {
  return request({
    url: `/business/bi/llm/providers/${id}`,
    method: 'delete'
  });
}

/** 测试 LLM 提供商连通性 */
export function fetchTestBiModelProvider(id: string) {
  return request<Api.Bi.ModelProviderTestResult>({
    url: `/business/bi/llm/providers/${id}/test`,
    method: 'post'
  });
}

/** 搜索 LLM 模型 */
export function fetchBiModelList(data: Api.Bi.BiModelSearchParams) {
  return request<Api.Bi.BiModelList>({
    url: '/business/bi/llm/models/search',
    method: 'post',
    data
  });
}

/** 创建 LLM 模型 */
export function fetchCreateBiModel(data: Api.Bi.BiModelAddParams) {
  return request<{ createdId: string }>({
    url: '/business/bi/llm/models',
    method: 'post',
    data
  });
}

/** 更新 LLM 模型 */
export function fetchUpdateBiModel(id: string, data: Api.Bi.BiModelUpdateParams) {
  return request<{ updatedId: string }>({
    url: `/business/bi/llm/models/${id}`,
    method: 'patch',
    data
  });
}

/** 删除 LLM 模型 */
export function fetchDeleteBiModel(id: string) {
  return request({
    url: `/business/bi/llm/models/${id}`,
    method: 'delete'
  });
}

// ---- Audit ----

/** 分页查询审计日志 */
export function fetchBiAuditList(data: Api.Bi.AuditSearchParams) {
  return request<Api.Common.PaginatingQueryRecord<Api.Bi.AuditLog>>({
    url: '/business/bi/audit/logs',
    method: 'get',
    params: data
  });
}

/** 审计详情（含原始 SQL） */
export function fetchBiAuditDetail(id: string) {
  return request<Api.Bi.AuditDetail | null>({
    url: `/business/bi/audit/logs/${id}`,
    method: 'get'
  });
}

/** 审计 KPI 统计 */
export function fetchBiAuditStats(params?: { startTime?: string; endTime?: string }) {
  return request<Api.Bi.AuditStats>({
    url: '/business/bi/audit/stats',
    method: 'get',
    params
  });
}

/** 按天趋势 */
export function fetchBiAuditTrend(params?: { days?: number; action?: string }) {
  return request<Api.Bi.DailyTrendItem[]>({
    url: '/business/bi/audit/trend',
    method: 'get',
    params
  });
}

/** 时段热力图 */
export function fetchBiAuditHeatmap(params?: { days?: number }) {
  return request<Api.Bi.HeatmapPoint[]>({
    url: '/business/bi/audit/heatmap',
    method: 'get',
    params
  });
}

/** 导出审计 CSV */
export function exportBiAuditCsv(params?: Api.Bi.AuditSearchParams) {
  return request<Blob, 'blob'>({
    url: '/business/bi/audit/export',
    method: 'get',
    params,
    responseType: 'blob'
  });
}
