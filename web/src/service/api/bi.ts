import { request } from '../request';

// ---- Datasource（数据源管理）----

/** 数据源分页搜索 */
export function fetchBiDatasourceList(data?: Api.Bi.BiDatasourceSearchParams) {
  return request<Api.Bi.BiDatasourceList>({
    url: '/business/bi/datasources/search',
    method: 'post',
    data: data ?? {}
  });
}

/** 获取数据源详情 */
export function fetchBiDatasource(id: string) {
  return request<Api.Bi.BiDatasource>({
    url: `/business/bi/datasources/${id}`,
    method: 'get'
  });
}

/** 创建数据源 */
export function fetchAddBiDatasource(data: Api.Bi.BiDatasourceOperateParams) {
  return request<Api.Bi.CreateResult>({
    url: '/business/bi/datasources',
    method: 'post',
    data
  });
}

/** 更新数据源（password 不传则保留原密文） */
export function fetchUpdateBiDatasource(data: Api.Bi.BiDatasourceOperateParams) {
  return request<Api.Bi.UpdateResult>({
    url: `/business/bi/datasources/${data.id}`,
    method: 'put',
    data
  });
}

/** 删除数据源（软删除） */
export function fetchDeleteBiDatasource(data: Api.Bi.CommonDeleteParams) {
  return request<null>({
    url: `/business/bi/datasources/${data.id}`,
    method: 'delete'
  });
}

/** 批量删除数据源 */
export function fetchBatchDeleteBiDatasource(data: Api.Bi.CommonBatchDeleteParams) {
  return request<null>({
    url: '/business/bi/datasources',
    method: 'delete',
    data
  });
}

/** 测试数据源连接 */
export function fetchTestBiDatasource(id: string) {
  return request<Api.Bi.BiDatasourceTestResult>({
    url: `/business/bi/datasources/${id}/test`,
    method: 'post'
  });
}

/** 同步数据源元数据（表 / 列 / 索引 / 外键） */
export function fetchSyncBiDatasource(id: string) {
  return request<Api.Bi.BiSyncResult>({
    url: `/business/bi/datasources/${id}/sync`,
    method: 'post'
  });
}

// ---- Metadata（元数据查询 — 表 / 列只读 + 表详情聚合）----

/** 表元数据分页搜索 */
export function fetchBiTableList(data?: Api.Bi.BiTableSearchParams) {
  return request<Api.Bi.BiTableList>({
    url: '/business/bi/tables/search',
    method: 'post',
    data: data ?? {}
  });
}

/** 获取表元数据详情 */
export function fetchBiTable(id: string) {
  return request<Api.Bi.BiTable>({
    url: `/business/bi/tables/${id}`,
    method: 'get'
  });
}

/** 查看表详情（含列 / 索引 / 外键聚合） */
export function fetchBiTableDetail(tableId: string) {
  return request<Api.Bi.BiTableDetail>({
    url: `/business/bi/tables/${tableId}/detail`,
    method: 'get'
  });
}

/** 列元数据分页搜索 */
export function fetchBiColumnList(data?: Api.Bi.BiColumnSearchParams) {
  return request<Api.Bi.BiColumnList>({
    url: '/business/bi/columns/search',
    method: 'post',
    data: data ?? {}
  });
}

/** 获取列元数据详情 */
export function fetchBiColumn(id: string) {
  return request<Api.Bi.BiColumn>({
    url: `/business/bi/columns/${id}`,
    method: 'get'
  });
}
