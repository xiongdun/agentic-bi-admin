import { request } from '../request';
import { getServiceBaseURL } from '@/utils/service';
import { getToken } from '@/store/modules/auth/shared';

const isHttpProxy = import.meta.env.DEV && import.meta.env.VITE_HTTP_PROXY === 'Y';
const { baseURL } = getServiceBaseURL(import.meta.env, isHttpProxy);

// ---- Chat Session（会话管理）----

/** 创建对话会话 */
export function fetchAddBiChatSession(data?: Api.Bi.BiChatSessionCreateParams) {
  return request<Api.Bi.CreateResult>({
    url: '/business/bi/chat/sessions',
    method: 'post',
    data: data ?? { title: '新对话' }
  });
}

/** 查看当前用户的会话列表 */
export function fetchBiChatSessionList(data?: Api.Bi.BiChatSessionSearchParams) {
  return request<Api.Bi.BiChatSessionList>({
    url: '/business/bi/chat/sessions/search',
    method: 'post',
    data: data ?? {}
  });
}

/** 删除对话会话（级联删除消息，仅会话创建人可删除） */
export function fetchDeleteBiChatSession(data: Api.Bi.CommonDeleteParams) {
  return request<Api.Bi.DeleteResult>({
    url: `/business/bi/chat/sessions/${data.id}`,
    method: 'delete'
  });
}

/** 查看会话消息列表（按时间正序） */
export function fetchBiChatMessages(sessionId: string, data?: Api.Bi.BiChatMessageSearchParams) {
  return request<Api.Bi.BiChatMessageList>({
    url: `/business/bi/chat/sessions/${sessionId}/messages/search`,
    method: 'post',
    data: data ?? {}
  });
}

// ---- Chat Send（发送消息 — SSE 流式响应）----

/**
 * 发送对话消息，返回原生 fetch Response 用于 SSE 流式接收。
 *
 * 不能用 axios 的 `request`，因为 axios 不支持 ReadableStream 流式读取。
 * 这里手写 fetch 调用，复用 `getServiceBaseURL` 保证开发环境走 `/proxy-default` 代理前缀，
 * 与 `request` 实例的 baseURL 保持一致。
 *
 * 事件类型：`step` / `final` / `error` / `heartbeat`，见 `Api.Bi.ChatEvent`。
 */
export function sendBiChatMessage(data: Api.Bi.ChatSendParams): Promise<Response> {
  const token = getToken();
  return fetch(`${baseURL}/business/bi/chat/send`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: token ? `Bearer ${token}` : ''
    },
    body: JSON.stringify(data)
  });
}
