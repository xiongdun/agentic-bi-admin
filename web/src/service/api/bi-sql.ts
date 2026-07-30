import { request } from '../request';

/** 执行 SQL（白名单校验 + 自动 LIMIT + 配额限制） */
export function fetchBiSqlRun(data: Api.Bi.SqlRunParams) {
  return request<Api.Bi.SqlExecutionResult>({
    url: '/business/bi/sql/run',
    method: 'post',
    data
  });
}

/** 解析 SQL（不执行，返回 AST 摘要） */
export function fetchBiSqlExplain(data: Api.Bi.SqlExplainParams) {
  return request<Api.Bi.SqlExplainResult>({
    url: '/business/bi/sql/explain',
    method: 'post',
    data
  });
}

/** 格式化 SQL（基于 sqlglot，不执行） */
export function fetchBiSqlFormat(data: Api.Bi.SqlFormatParams) {
  return request<Api.Bi.SqlFormatResult>({
    url: '/business/bi/sql/format',
    method: 'post',
    data
  });
}

/** 查看当前用户的 SQL 执行历史（从审计日志查） */
export function fetchBiSqlHistory(data?: Api.Bi.BiAuditSearchParams) {
  return request<Api.Bi.BiAuditList>({
    url: '/business/bi/sql/history/search',
    method: 'post',
    data: data ?? {}
  });
}

/** 预览表前 100 行 */
export function fetchBiSqlPreview(datasourceId: string, tableName: string) {
  return request<Api.Bi.SqlPreviewResult>({
    url: `/business/bi/sql/preview/${datasourceId}/${encodeURIComponent(tableName)}`,
    method: 'get'
  });
}

/** 根据列元数据生成 SELECT 语句 */
export function fetchBiSqlGenerateSelect(datasourceId: string, tableName: string) {
  return request<Api.Bi.SqlGenerateSelectResult>({
    url: `/business/bi/sql/generate-select/${datasourceId}/${encodeURIComponent(tableName)}`,
    method: 'get'
  });
}
