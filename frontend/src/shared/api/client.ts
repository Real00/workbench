import axios, { AxiosError } from 'axios'

const API_BASE_KEY = 'workbench_api_base'
/** 打包期烧入；未设置时 Tauri 壳回落到云端默认地址 */
const ENV_API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').trim().replace(/\/+$/, '')
/** Tauri 壳（桌面 / Android）未配置时的默认 API */
export const DEFAULT_TAURI_API_BASE = 'https://workbench.reelab.cc'

/** Tauri 壳（桌面 / Android），用于登录页服务器地址等 */
export const isTauriShell = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

/** 桌面壳（排除 Android）：托盘桥、DMG 更新等 */
export const isDesktopShell =
  isTauriShell && typeof navigator !== 'undefined' && !/Android/i.test(navigator.userAgent)

function resolveInitialApiBase() {
  const saved = typeof localStorage !== 'undefined' ? localStorage.getItem(API_BASE_KEY) : null
  if (saved) return saved
  if (ENV_API_BASE) return ENV_API_BASE
  if (isTauriShell) return DEFAULT_TAURI_API_BASE
  return ''
}

let apiBase = resolveInitialApiBase()

/** 当前 API 地址（运行时可变，登录页可设置） */
export function getApiBase() {
  return apiBase
}

export function setApiBase(base: string) {
  apiBase = base.trim().replace(/\/+$/, '')
  if (apiBase) localStorage.setItem(API_BASE_KEY, apiBase)
  else localStorage.removeItem(API_BASE_KEY)
  api.defaults.baseURL = `${apiBase}/api/v1`
}

const DEVICE_ID_KEY = 'workbench_device_id'
const DEVICE_TOKEN_KEY = 'workbench_device_token'

/** 当前设备 ID：绑定设备时生成并持久化，服务端据此识别与吊销 */
export function getDeviceId() {
  if (typeof localStorage === 'undefined') return null
  return localStorage.getItem(DEVICE_ID_KEY)
}

export function ensureDeviceId() {
  if (typeof localStorage === 'undefined') return 'test-device'
  let id = localStorage.getItem(DEVICE_ID_KEY)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(DEVICE_ID_KEY, id)
  }
  return id
}

export function getDeviceToken() {
  if (typeof localStorage === 'undefined') return null
  return localStorage.getItem(DEVICE_TOKEN_KEY)
}

export function setDeviceCredentials(token: string | null) {
  if (typeof localStorage === 'undefined') return
  if (token) localStorage.setItem(DEVICE_TOKEN_KEY, token)
  else localStorage.removeItem(DEVICE_TOKEN_KEY)
}

/** 平台标识：Tauri 壳/网页端 + 操作系统，用于设备命名 */
export function deviceLabel() {
  if (typeof navigator === 'undefined') return '未知设备'
  const ua = navigator.userAgent
  if (/Android/i.test(ua)) {
    return `${isTauriShell ? 'Android 端' : '网页端'}（Android）`
  }
  const platform = /Mac/i.test(ua)
    ? 'macOS'
    : /Win/i.test(ua)
      ? 'Windows'
      : /Linux/i.test(ua)
        ? 'Linux'
        : '未知系统'
  const shell = isDesktopShell ? '桌面端' : isTauriShell ? '客户端' : '网页端'
  return `${shell}（${platform}）`
}

/** 已有会话但缺设备凭证时（如应用升级前登录过），静默补绑定一次 */
export async function bindCurrentDevice(): Promise<boolean> {
  if (getDeviceToken() || !hasToken()) return Boolean(getDeviceToken())
  try {
    const { data } = await api.post<{ device_token: string }>('/auth/devices/bind', {
      device_id: ensureDeviceId(),
      device_name: deviceLabel(),
    })
    setDeviceCredentials(data.device_token ?? null)
    return Boolean(data.device_token)
  } catch {
    return false
  }
}

/** 解析 JWT payload 的过期时间（毫秒）；仅读 exp，不做签名校验 */
function accessTokenExpiresAt(token: string): number | null {
  try {
    const segment = token.split('.')[1]
    if (!segment) return null
    const normalized = segment.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalized + '='.repeat((4 - (normalized.length % 4)) % 4)
    const payload = JSON.parse(atob(padded)) as { exp?: unknown }
    return typeof payload.exp === 'number' ? payload.exp * 1000 : null
  } catch {
    return null
  }
}

/** 本地 JWT 是否仍在有效期内（提前 skewMs 视为过期，给换发留余量） */
export function hasFreshToken(skewMs = 30_000): boolean {
  const token = getToken()
  if (!token) return false
  const expiresAt = accessTokenExpiresAt(token)
  // 无法解析 exp 时交给后续请求 / 服务端判定
  if (expiresAt == null) return true
  return expiresAt > Date.now() + skewMs
}

/**
 * 保证有可用会话：JWT 未过期直接成功；否则用设备长效凭证静默换发。
 * 注意：过期 JWT 仍会占着 localStorage，不能只看 hasToken()。
 */
export async function ensureSession(): Promise<boolean> {
  if (hasFreshToken()) return true
  const deviceToken = getDeviceToken()
  const deviceId = getDeviceId()
  if (!deviceToken || !deviceId) return false
  // 先清掉过期 JWT，避免换发前后其它请求继续带坏 token
  clearToken()
  try {
    const response = await fetch(`${getApiBase()}/api/v1/auth/device`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_id: deviceId, device_token: deviceToken }),
    })
    if (!response.ok) {
      setDeviceCredentials(null)
      return false
    }
    const data = await response.json() as { access_token: string }
    setToken(data.access_token, true)
    return true
  } catch {
    return false
  }
}

const TOKEN_KEY = 'pulse_access_token'

export const api = axios.create({
  baseURL: `${apiBase}/api/v1`,
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY) ?? sessionStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(undefined, async (error: AxiosError) => {
  const config = error.config as (AxiosError['config'] & { _deviceRetried?: boolean }) | undefined
  const isAuthPath = Boolean(config?.url?.includes('/auth/login') || config?.url?.includes('/auth/device'))
  if (error.response?.status === 401 && config && !isAuthPath) {
    // 确认接口在旧后端会把「预览令牌过期」也打成 401；本地会话仍新鲜时不要踢登录
    const url = `${config.baseURL ?? ''}${config.url ?? ''}`
    if (url.includes('/ai/confirm') && hasFreshToken()) {
      return Promise.reject(error)
    }
    // JWT 失效但存在设备绑定凭证：清掉坏 token 后静默换发，再重试一次原请求
    if (!config._deviceRetried && getDeviceToken() && getDeviceId()) {
      config._deviceRetried = true
      clearToken()
      if (await ensureSession()) {
        config.headers = config.headers ?? {}
        config.headers.Authorization = `Bearer ${getToken()}`
        return api.request(config)
      }
    }
    clearToken()
    if (window.location.pathname !== '/login') window.location.assign('/login')
  }
  return Promise.reject(error)
})

export function setToken(token: string, persistent: boolean) {
  clearToken()
  ;(persistent ? localStorage : sessionStorage).setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(TOKEN_KEY)
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) ?? sessionStorage.getItem(TOKEN_KEY)
}

export function hasToken() {
  return Boolean(getToken())
}

/** 逐帧读取 SSE 响应体，回调每帧 data 载荷（AI 对话与全局事件总线共用） */
export async function consumeSse<T = unknown>(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: T) => void,
) {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const chunks = buffer.split('\n\n')
    buffer = done ? '' : (chunks.pop() ?? '')
    for (const chunk of chunks) emit(chunk)
    if (done) break
  }

  function emit(chunk: string) {
    const line = chunk.split('\n').find(item => item.startsWith('data: '))
    if (!line) return
    onEvent(JSON.parse(line.slice(6)))
  }
}

export async function streamSse(
  path: string,
  payload: unknown,
  onEvent: (event: unknown) => void,
  signal?: AbortSignal,
  retried = false,
) {
  const token = getToken()
  const response = await fetch(`${getApiBase()}/api/v1${path}`, {
    method: 'POST',
    signal,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  })
  if (response.status === 401 && !path.includes('/auth/login')) {
    if (!retried && getDeviceToken() && getDeviceId()) {
      clearToken()
      if (await ensureSession()) {
        await streamSse(path, payload, onEvent, signal, true)
        return
      }
    }
    clearToken()
    if (window.location.pathname !== '/login') window.location.assign('/login')
    throw new Error('未登录')
  }
  if (!response.ok) {
    let message = `请求失败 (${response.status})`
    try {
      const data = await response.json() as { error?: string; details?: { msg?: string }[] }
      message = data.details?.[0]?.msg ?? data.error ?? message
    } catch {
      /* keep status message */
    }
    throw new Error(message)
  }
  if (!response.body) throw new Error('当前浏览器不支持流式响应')
  await consumeSse(response.body, onEvent)
}

export function apiError(error: unknown) {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { error?: string; details?: { msg?: string }[] } | undefined
    const fromBody = data?.details?.[0]?.msg ?? data?.error
    if (fromBody) return fromBody
    if (error.code === 'ECONNABORTED') return '请求超时，请稍后重试'
    // WKWebView 下 XHR 超时/跨源失败常落成 status 0 + "Network Error"
    if (error.code === 'ERR_NETWORK' || error.message === 'Network Error') {
      return (
        '无法连接服务器（Network Error）。请确认登录时填写的 API 地址可达；'
        + '若仅「检查更新」失败，多半是服务器访问 GitHub 超时或未配置 WORKBENCH_UPDATE_GITHUB_TOKEN。'
      )
    }
    return error.message
  }
  if (typeof error === 'string' && error.trim()) return error
  if (error && typeof error === 'object' && 'message' in error) {
    const message = (error as { message?: unknown }).message
    if (typeof message === 'string' && message.trim()) return message
  }
  return error instanceof Error ? error.message : '请求失败'
}
