import { request } from '../request';

/**
 * 导出单图表 CSV（Blob 下载，基于结果快照）。
 *
 * 注意：响应是 CSV 文件流而非 JSON，调用方需以 Blob 接收并触发下载。
 * 第二个泛型参数 `'blob'` 用于让 `request` 走非 JSON 的响应分支。
 */
export function fetchBiChartCsvExport(chartId: string) {
  return request<Blob, 'blob'>({
    url: `/business/bi/export/charts/${chartId}/csv`,
    method: 'get',
    responseType: 'blob'
  });
}

/** 批量导出图表 Excel（Blob 下载，每图表一个 Sheet） */
export function fetchBiChartsExcelExport(data: { chartIds: string[] }) {
  return request<Blob, 'blob'>({
    url: '/business/bi/export/charts/excel',
    method: 'post',
    data,
    responseType: 'blob'
  });
}

/** 导出仪表盘 Excel（Blob 下载，概览 Sheet + 每图表一个 Sheet） */
export function fetchBiDashboardExcelExport(dashboardId: string) {
  return request<Blob, 'blob'>({
    url: `/business/bi/export/dashboards/${dashboardId}/excel`,
    method: 'post',
    responseType: 'blob'
  });
}
