import { clearToken, consumeSse, ensureSession, getApiBase, getDeviceId, getDeviceToken, getToken } from './client'

export type ChangeScope = 'progress' | 'knowledge' | 'capture' | 'ai-settings' | 'all'

export interface ChangeEvent {
  type: 'changed'
  scope: ChangeScope
  action: string
}

const RECONNECT_DELAYS = [1_000, 2_000, 5_000, 10_000, 30_000]

/**
 * 常驻订阅全局数据变更总线（GET /api/v1/events）。
 *
 * 用 fetch 流式而非原生 EventSource：连接需要带 Bearer 头，而桌面壳
 * WebView 与网页端都支持流式 fetch（AI 对话已验证）。断线按指数退避
 * 重连；JWT 失效时用设备凭证静默换发一次。返回退订函数。
 */
export function subscribeEvents(onEvent: (event: ChangeEvent) => void): () => void {
  const controller = new AbortController()
  void (async () => {
    let attempt = 0
    let refreshed = false
    while (!controller.signal.aborted && getToken()) {
      try {
        const response = await fetch(`${getApiBase()}/api/v1/events`, {
          signal: controller.signal,
          headers: { Authorization: `Bearer ${getToken()}` },
        })
        if (response.status === 401) {
          // 设备凭证换发只尝试一轮，避免坏 token 造成快速无限循环
          if (!refreshed && getDeviceToken() && getDeviceId()) {
            refreshed = true
            clearToken()
            if (await ensureSession()) continue
          }
          clearToken()
          if (window.location.pathname !== '/login') window.location.assign('/login')
          return
        }
        if (!response.ok || !response.body) throw new Error(`事件流连接失败 (${response.status})`)
        refreshed = false
        attempt = 0
        await consumeSse<ChangeEvent>(response.body, onEvent)
      } catch {
        if (controller.signal.aborted) return
      }
      await sleep(RECONNECT_DELAYS[Math.min(attempt, RECONNECT_DELAYS.length - 1)], controller.signal)
      attempt += 1
    }
  })()
  return () => controller.abort()
}

function sleep(ms: number, signal: AbortSignal) {
  return new Promise<void>(resolve => {
    const timer = setTimeout(finish, ms)
    function finish() {
      clearTimeout(timer)
      signal.removeEventListener('abort', finish)
      resolve()
    }
    signal.addEventListener('abort', finish)
  })
}
