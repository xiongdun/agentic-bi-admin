import { request } from '../request';

// ---- SQL Workbench ----

/** 在沙箱里执行一条 SQL */
export function fetchBiSqlExecute(data: Api.Bi.SqlExecuteRequest) {
  return request<Api.Bi.SqlExecuteResponse>({
    url: '/business/bi/sql/execute',
    method: 'post',
    data
  });
}

/** 对一条 SQL 做 EXPLAIN（沙箱白名单 + 包装 EXPLAIN） */
export function fetchBiSqlExplain(data: Api.Bi.SqlExplainRequest) {
  return request<Api.Bi.SqlExplainResponse>({
    url: '/business/bi/sql/explain',
    method: 'post',
    data
  });
}

/** 查询工作台执行历史（分页） */
export function fetchBiSqlHistory(data: {
  current?: number;
  size?: number;
  datasourceId?: string | null;
  status?: Api.Bi.ExecutionStatus | null;
}) {
  return request<Api.Bi.QueryExecutionList>({
    url: '/business/bi/sql/history',
    method: 'post',
    data
  });
}
