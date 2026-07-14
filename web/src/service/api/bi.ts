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
