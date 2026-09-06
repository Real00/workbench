import axios, { AxiosError } from 'axios'

const API_BASE_KEY = 'workbench_api_base'
/** 打包期默认值：桌面端可留空，登录页会写入运行时地址；网页端同源部署为空即同源 */
const ENV_API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''
export const isDesktopShell = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

let apiBase =
  (typeof localStorage !== 'undefined' ? localStorage.getItem(API_BASE_KEY) : null) ?? ENV_API_BASE

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

/** 平台标识：桌面壳/网页端 + 操作系统，用于设备命名 */
export function deviceLabel() {
  if (typeof navigator === 'undefined') return '未知设备'
  const platform = /Mac/i.test(navigator.userAgent)
    ? 'macOS'
    : /Win/i.test(navigator.userAgent)
      ? 'Windows'
      : /Linux/i.test(navigator.userAgent)
        ? 'Linux'
        : '未知系统'
  return `${isDesktopShell ? '桌面端' : '网页端'}（${platform}）`
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

/** 无有效 JWT 时，用设备绑定凭证静默换发新会话；成功返回 true */
export async function ensureSession(): Promise<boolean> {
  if (hasToken()) return true
  const deviceToken = getDeviceToken()
  const deviceId = getDeviceId()
  if (!deviceToken || !deviceId) return false
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
    // JWT 过期但存在设备绑定凭证：静默换发后重试一次原请求
    if (!config._deviceRetried && getDeviceToken() && getDeviceId()) {
      config._deviceRetried = true
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
    return data?.details?.[0]?.msg ?? data?.error ?? error.message
  }
  return error instanceof Error ? error.message : '请求失败'
}
