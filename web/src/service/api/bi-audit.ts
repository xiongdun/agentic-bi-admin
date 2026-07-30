import { request } from '../request';

/** 搜索审计日志（支持按日志类型 / 操作人 / 时间范围 / 资源类型筛选） */
export function fetchBiAuditLogList(data?: Api.Bi.BiAuditSearchParams) {
  return request<Api.Bi.BiAuditList>({
    url: '/business/bi/audit/search',
    method: 'post',
    data: data ?? {}
  });
}

/** 查看审计日志详情 */
export function fetchBiAuditLog(id: string) {
  return request<Api.Bi.BiAuditLog>({
    url: `/business/bi/audit/${id}`,
    method: 'get'
  });
}

/** 审计日志统计（总数 / 成功 / 失败 / 按事件类型 / 按操作 / 按用户分组） */
export function fetchBiAuditStats(data?: Api.Bi.BiAuditStatsParams) {
  return request<Api.Bi.BiAuditStats>({
    url: '/business/bi/audit/stats',
    method: 'post',
    data: data ?? {}
  });
}

/**
 * 导出审计日志为 CSV（UTF-8 BOM，最多 10000 条）。
 *
 * 注意：响应是 CSV 文本而非 JSON，调用方需以 Blob 接收并触发下载。
 * 第二个泛型参数 `'blob'` 用于让 `request` 走非 JSON 的响应分支。
 */
export function fetchExportBiAuditLogs(data?: Api.Bi.BiAuditSearchParams) {
  return request<Blob, 'blob'>({
    url: '/business/bi/audit/export',
    method: 'post',
    data: data ?? {},
    responseType: 'blob'
  });
}
