import axios, { AxiosError } from 'axios'

/** 网页端同源部署留空；桌面端 / 跨源部署通过 VITE_API_BASE_URL 指向云端 API（如 https://api.example.com） */
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

const TOKEN_KEY = 'pulse_access_token'

export const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY) ?? sessionStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(undefined, (error: AxiosError) => {
  if (error.response?.status === 401 && !error.config?.url?.includes('/auth/login')) {
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

export async function streamSse(
  path: string,
  payload: unknown,
  onEvent: (event: unknown) => void,
  signal?: AbortSignal,
) {
  const token = getToken()
  const response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
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
  const reader = response.body.getReader()
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

export function apiError(error: unknown) {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { error?: string; details?: { msg?: string }[] } | undefined
    return data?.details?.[0]?.msg ?? data?.error ?? error.message
  }
  return error instanceof Error ? error.message : '请求失败'
}
