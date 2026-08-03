import { request } from '../request';

/** 提交异步查询 */
export function fetchBiAsyncRun(data: Api.Bi.BiAsyncRunPayload) {
  return request<Api.Bi.BiAsyncRunResult>({
    url: '/business/bi/sql/async-run',
    method: 'post',
    data
  });
}

/** 任务列表分页 */
export function fetchBiAsyncTaskSearch(data: Api.Bi.BiQueryTaskSearchParams) {
  return request<Api.Bi.BiQueryTaskList>({
    url: '/business/bi/sql/tasks/search',
    method: 'post',
    data
  });
}

/** 任务详情（轮询用，2s 间隔） */
export function fetchBiAsyncTask(taskId: string) {
  return request<Api.Bi.BiQueryTask>({
    url: `/business/bi/sql/tasks/${taskId}`,
    method: 'get'
  });
}

/** 获取结果预览 */
export function fetchBiAsyncTaskResult(taskId: string) {
  return request<Api.Bi.BiQueryTaskResult>({
    url: `/business/bi/sql/tasks/${taskId}/result`,
    method: 'get'
  });
}

/** 取消任务 */
export function fetchBiAsyncTaskCancel(taskId: string) {
  return request<null>({
    url: `/business/bi/sql/tasks/${taskId}/cancel`,
    method: 'post'
  });
}

/** 删除任务 */
export function fetchBiAsyncTaskDelete(taskId: string) {
  return request<null>({
    url: `/business/bi/sql/tasks/${taskId}`,
    method: 'delete'
  });
}

/**
 * 构造 CSV 下载 URL（直接打开，浏览器自动触发下载）。
 * 注意：直接 window.open 不会带 Authorization 头，需通过 axios 单独下载。
 */
export function buildBiAsyncDownloadUrl(taskId: string): string {
  return `/business/bi/sql/tasks/${taskId}/download`;
}
