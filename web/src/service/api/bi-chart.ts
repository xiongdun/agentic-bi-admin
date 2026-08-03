import { request } from '../request';

/** 图表分页搜索 */
export function fetchBiChartList(data?: Api.Bi.BiChartSearchParams) {
  return request<Api.Bi.BiChartList>({
    url: '/business/bi/charts/search',
    method: 'post',
    data: data ?? {}
  });
}

/** 获取图表详情 */
export function fetchBiChart(id: string) {
  return request<Api.Bi.BiChart>({
    url: `/business/bi/charts/${id}`,
    method: 'get'
  });
}

/** 保存图表（来源：智能对话 / SQL 工作台） */
export function fetchAddBiChart(data: Api.Bi.BiChartOperateParams) {
  return request<Api.Bi.CreateResult>({
    url: '/business/bi/charts',
    method: 'post',
    data
  });
}

/** 更新图表（名称/说明/标签/图表类型/轴字段；不允许改 sql_text/datasource_id） */
export function fetchUpdateBiChart(data: Api.Bi.BiChartOperateParams) {
  return request<Api.Bi.UpdateResult>({
    url: `/business/bi/charts/${data.id}`,
    method: 'patch',
    data
  });
}

/** 删除图表（软删） */
export function fetchDeleteBiChart(data: Api.Bi.CommonDeleteParams) {
  return request<null>({
    url: `/business/bi/charts/${data.id}`,
    method: 'delete'
  });
}

/** 批量删除图表 */
export function fetchBatchDeleteBiChart(data: Api.Bi.CommonBatchDeleteParams) {
  return request<null>({
    url: '/business/bi/charts/batch_delete',
    method: 'post',
    data
  });
}

/** 刷新图表数据（重跑 SQL） */
export function fetchRefreshBiChart(id: string) {
  return request<Api.Bi.BiChartRefreshResult>({
    url: `/business/bi/charts/${id}/refresh`,
    method: 'post'
  });
}

/** 开启外部分享，返回 share_token */
export function fetchEnableBiChartShare(id: string) {
  return request<Api.Bi.BiChartShareEnableResult>({
    url: `/business/bi/charts/${id}/share/enable`,
    method: 'post'
  });
}

/** 关闭外部分享 */
export function fetchDisableBiChartShare(id: string) {
  return request<null>({
    url: `/business/bi/charts/${id}/share/disable`,
    method: 'post'
  });
}

/** 获取当前用户图表的所有标签（自动补全） */
export function fetchBiChartTags() {
  return request<Api.Bi.BiChartTagsResult>({
    url: '/business/bi/charts/tags',
    method: 'get'
  });
}

/**
 * 免登录查看分享图表（不返回 sqlText）。
 *
 * 该接口不需要登录态，但走同一 request 实例以复用 baseURL 代理。
 * 若分享页独立部署，可改用原生 fetch + getServiceBaseURL。
 */
export function fetchSharedBiChart(token: string) {
  return request<Api.Bi.BiChartShared>({
    url: `/business/bi/charts/shared/${token}`,
    method: 'get'
  });
}
