import { AxiosError } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const TOKEN_KEY = 'pulse_access_token'
const DEVICE_ID_KEY = 'workbench_device_id'

const { storage, fetchMock } = vi.hoisted(() => {
  const storage = new Map<string, string>()
  const memoryStorage = (): Storage => ({
    get length() { return storage.size },
    clear: () => storage.clear(),
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => { storage.set(key, value) },
    removeItem: (key: string) => { storage.delete(key) },
    key: (index: number) => [...storage.keys()][index] ?? null,
  })
  const fetchMock = vi.fn()
  vi.stubGlobal('localStorage', memoryStorage())
  vi.stubGlobal('sessionStorage', memoryStorage())
  vi.stubGlobal('fetch', fetchMock)
  return { storage, fetchMock }
})

import {
  api,
  clearToken,
  ensureSession,
  getToken,
  hasFreshToken,
  setDeviceCredentials,
  setToken,
} from './client'

function jwtWithExp(expSeconds: number) {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const payload = btoa(JSON.stringify({ sub: 'user-1', exp: expSeconds }))
  return `${header}.${payload}.sig`
}

beforeEach(() => {
  storage.clear()
  fetchMock.mockReset()
})

describe('hasFreshToken / ensureSession', () => {
  it('过期 JWT 不算新鲜', () => {
    setToken(jwtWithExp(Math.floor(Date.now() / 1000) - 60), true)
    expect(hasFreshToken()).toBe(false)
  })

  it('未过期 JWT 算新鲜', () => {
    setToken(jwtWithExp(Math.floor(Date.now() / 1000) + 3600), true)
    expect(hasFreshToken()).toBe(true)
  })

  it('JWT 过期但有设备凭证时静默换发', async () => {
    setToken(jwtWithExp(Math.floor(Date.now() / 1000) - 60), true)
    localStorage.setItem(DEVICE_ID_KEY, 'desk-1')
    setDeviceCredentials('device-secret')
    const fresh = jwtWithExp(Math.floor(Date.now() / 1000) + 3600)
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ access_token: fresh }),
    })

    await expect(ensureSession()).resolves.toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(localStorage.getItem(TOKEN_KEY)).toBe(fresh)
    expect(hasFreshToken()).toBe(true)
  })

  it('仅有过期 JWT、无设备凭证时失败', async () => {
    setToken(jwtWithExp(Math.floor(Date.now() / 1000) - 60), true)
    await expect(ensureSession()).resolves.toBe(false)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('api 401 interceptor', () => {
  it('确认接口 401 且会话仍新鲜时不踢登录', async () => {
    const fresh = jwtWithExp(Math.floor(Date.now() / 1000) + 3600)
    setToken(fresh, true)
    const assign = vi.fn()
    vi.stubGlobal('window', { location: { pathname: '/progress', assign } })

    const previous = api.defaults.adapter
    api.defaults.adapter = async (config) => {
      const err = new AxiosError('Request failed with status code 401')
      err.config = config
      err.response = {
        data: { error: 'invalid or expired token' },
        status: 401,
        statusText: 'Unauthorized',
        headers: {},
        config,
      }
      throw err
    }
    try {
      await expect(api.post('/ai/confirm', { confirmation_token: 'x' })).rejects.toMatchObject({
        response: { status: 401 },
      })
      expect(getToken()).toBe(fresh)
      expect(assign).not.toHaveBeenCalled()
    } finally {
      api.defaults.adapter = previous
      clearToken()
    }
  })
})
