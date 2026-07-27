import { request } from '../request';
import { getServiceBaseURL } from '@/utils/service';
import { getToken } from '@/store/modules/auth/shared';

const isHttpProxy = import.meta.env.DEV && import.meta.env.VITE_HTTP_PROXY === 'Y';
const { baseURL: chatBaseURL } = getServiceBaseURL(import.meta.env, isHttpProxy);

// ---- Chat sessions ----

/** 创建会话 */
export function fetchBiChatCreate(data: Api.Bi.ChatCreateRequest) {
  return request<Api.Bi.ChatSession>({
    url: '/business/bi/chat/sessions',
    method: 'post',
    data
  });
}

/** 会话列表 */
export function fetchBiChatList(data: { current?: number; size?: number } = {}) {
  return request<Api.Bi.ChatSessionList>({
    url: '/business/bi/chat/sessions',
    method: 'get',
    params: data
  });
}

/** 会话详情（含消息） */
export function fetchBiChatDetail(sessionId: string) {
  return request<Api.Bi.ChatSessionDetail>({
    url: `/business/bi/chat/sessions/${sessionId}`,
    method: 'get'
  });
}

/** 删除会话 */
export function fetchBiChatDelete(sessionId: string) {
  return request({
    url: `/business/bi/chat/sessions/${sessionId}`,
    method: 'delete'
  });
}

// ---- Send (SSE) ----

/** 发送问题（流式 SSE），返回 EventSource。 */
export function openBiChatSend(
  sessionId: string,
  data: Api.Bi.ChatSendRequest,
  handlers: {
    onStep: (step: { node: string; status: string; [k: string]: unknown }) => void;
    onFinal: (data: Record<string, unknown>) => void;
    onError: (msg: string) => void;
    onDone: () => void;
  }
): EventSource {
  // SSE via GET query string 是最稳的；这里用 POST + fetch + ReadableStream 更稳
  // 走和 request lib 同样的 baseURL（dev 模式 + VITE_HTTP_PROXY=Y 时会被 Vite 代理）
  const url = `${chatBaseURL}/business/bi/chat/sessions/${sessionId}/messages`;
  const token = getToken();
  const ctrl = new AbortController();
  fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      Accept: 'text/event-stream'
    },
    body: JSON.stringify(data),
    signal: ctrl.signal
  })
    .then(async resp => {
      if (!resp.ok || !resp.body) {
        // 尝试解析后端的 {"code":..., "msg":...} JSON,避免只看到 "HTTP 401"
        let detail = `HTTP ${resp.status}`;
        try {
          const errBody = await resp.clone().json();
          if (errBody && (errBody.msg || errBody.message)) {
            detail = `HTTP ${resp.status}: ${errBody.msg || errBody.message}`;
          }
        } catch {
          // ignore parse error
        }
        handlers.onError(detail);
        handlers.onDone();
        return;
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        // 按 \n\n 拆 event
        let idx: number;
        while ((idx = buf.indexOf('\n\n')) >= 0) {
          const raw = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          parseSse(raw, handlers);
        }
      }
      if (buf.trim()) parseSse(buf, handlers);
      handlers.onDone();
    })
    .catch(err => {
      handlers.onError(String(err));
      handlers.onDone();
    });
  // 返回一个可 abort 的伪 EventSource
  return { close: () => ctrl.abort() } as unknown as EventSource;
}

function parseSse(
  raw: string,
  handlers: {
    onStep: (step: { node: string; status: string; [k: string]: unknown }) => void;
    onFinal: (data: Record<string, unknown>) => void;
    onError: (msg: string) => void;
    onDone: () => void;
  }
) {
  let event = 'message';
  let dataStr = '';
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      dataStr += line.slice(5).trim();
    }
  }
  if (!dataStr) return;
  if (dataStr === '[DONE]') {
    handlers.onDone();
    return;
  }
  let parsed: unknown = dataStr;
  try {
    parsed = JSON.parse(dataStr);
  } catch {
    // keep string
  }
  if (event === 'step' && parsed && typeof parsed === 'object') {
    handlers.onStep(parsed as { node: string; status: string });
  } else if (event === 'final' && parsed && typeof parsed === 'object') {
    handlers.onFinal(parsed as Record<string, unknown>);
  } else if (event === 'error' && parsed && typeof parsed === 'object') {
    handlers.onError(((parsed as Record<string, unknown>).message as string) ?? String(parsed));
  }
}
