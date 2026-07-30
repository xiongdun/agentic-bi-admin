import { request } from '../request';

// ---- LLM Provider ----

/** Provider 分页搜索 */
export function fetchBiLLMProviderList(data?: Api.Bi.BiLLMProviderSearchParams) {
  return request<Api.Bi.BiLLMProviderList>({
    url: '/business/bi/llm/providers/search',
    method: 'post',
    data: data ?? {}
  });
}

/** 获取 Provider 详情（API Key 脱敏） */
export function fetchBiLLMProvider(id: string) {
  return request<Api.Bi.BiLLMProvider>({
    url: `/business/bi/llm/providers/${id}`,
    method: 'get'
  });
}

/** 创建 Provider（API Key 加密存储） */
export function fetchAddBiLLMProvider(data: Api.Bi.BiLLMProviderOperateParams) {
  return request<Api.Bi.CreateResult>({
    url: '/business/bi/llm/providers',
    method: 'post',
    data
  });
}

/** 更新 Provider（不传 apiKey 则保留原密文） */
export function fetchUpdateBiLLMProvider(data: Api.Bi.BiLLMProviderOperateParams) {
  return request<Api.Bi.UpdateResult>({
    url: `/business/bi/llm/providers/${data.id}`,
    method: 'put',
    data
  });
}

/** 删除 Provider */
export function fetchDeleteBiLLMProvider(data: Api.Bi.CommonDeleteParams) {
  return request<null>({
    url: `/business/bi/llm/providers/${data.id}`,
    method: 'delete'
  });
}

/** 批量删除 Provider */
export function fetchBatchDeleteBiLLMProvider(data: Api.Bi.CommonBatchDeleteParams) {
  return request<null>({
    url: '/business/bi/llm/providers',
    method: 'delete',
    data
  });
}

/** 测试 Provider 连接（发送测试 prompt 并返回响应 + 耗时） */
export function fetchTestBiLLMProvider(id: string) {
  return request<Api.Bi.BiLLMTestResult>({
    url: `/business/bi/llm/providers/${id}/test`,
    method: 'post'
  });
}

// ---- LLM Model ----

/** 模型分页搜索 */
export function fetchBiLLMModelList(data?: Api.Bi.BiLLMModelSearchParams) {
  return request<Api.Bi.BiLLMModelList>({
    url: '/business/bi/llm/models/search',
    method: 'post',
    data: data ?? {}
  });
}

/** 获取模型详情 */
export function fetchBiLLMModel(id: string) {
  return request<Api.Bi.BiLLMModel>({
    url: `/business/bi/llm/models/${id}`,
    method: 'get'
  });
}

/** 创建模型 */
export function fetchAddBiLLMModel(data: Api.Bi.BiLLMModelOperateParams) {
  return request<Api.Bi.CreateResult>({
    url: '/business/bi/llm/models',
    method: 'post',
    data
  });
}

/** 更新模型 */
export function fetchUpdateBiLLMModel(data: Api.Bi.BiLLMModelOperateParams) {
  return request<Api.Bi.UpdateResult>({
    url: `/business/bi/llm/models/${data.id}`,
    method: 'put',
    data
  });
}

/** 删除模型 */
export function fetchDeleteBiLLMModel(data: Api.Bi.CommonDeleteParams) {
  return request<null>({
    url: `/business/bi/llm/models/${data.id}`,
    method: 'delete'
  });
}

/** 批量删除模型 */
export function fetchBatchDeleteBiLLMModel(data: Api.Bi.CommonBatchDeleteParams) {
  return request<null>({
    url: '/business/bi/llm/models',
    method: 'delete',
    data
  });
}
