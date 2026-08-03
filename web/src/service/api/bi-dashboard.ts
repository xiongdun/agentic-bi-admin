import { request } from '../request';

/** 仪表盘分页搜索 */
export function fetchBiDashboardList(data?: Api.Bi.BiDashboardSearchParams) {
  return request<Api.Bi.BiDashboardList>({
    url: '/business/bi/dashboards/search',
    method: 'post',
    data: data ?? {}
  });
}

/** 获取仪表盘详情（含完整 layout） */
export function fetchBiDashboardDetail(id: string) {
  return request<Api.Bi.BiDashboardDetail>({
    url: `/business/bi/dashboards/${id}`,
    method: 'get'
  });
}

/** 创建仪表盘 */
export function fetchCreateBiDashboard(data: Api.Bi.BiDashboardPayload) {
  return request<Api.Bi.CreateResult>({
    url: '/business/bi/dashboards',
    method: 'post',
    data
  });
}

/** 更新仪表盘（名称/说明/layout） */
export function fetchUpdateBiDashboard(id: string, data: Api.Bi.BiDashboardPayload) {
  return request<Api.Bi.UpdateResult>({
    url: `/business/bi/dashboards/${id}`,
    method: 'put',
    data
  });
}

/** 删除仪表盘（软删） */
export function fetchDeleteBiDashboard(id: string) {
  return request<null>({
    url: `/business/bi/dashboards/${id}`,
    method: 'delete'
  });
}

/** 全量刷新仪表盘所有图表数据 */
export function fetchRefreshBiDashboard(id: string) {
  return request<Api.Bi.BiDashboardRefreshResult>({
    url: `/business/bi/dashboards/${id}/refresh`,
    method: 'post'
  });
}

/** 预览仪表盘（不刷新，用 BiChart 已有快照） */
export function fetchPreviewBiDashboard(id: string) {
  return request<Api.Bi.BiDashboardPreview>({
    url: `/business/bi/dashboards/${id}/preview`,
    method: 'get'
  });
}
