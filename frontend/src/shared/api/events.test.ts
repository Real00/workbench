import { beforeEach, describe, expect, it, vi } from 'vitest'
import { clearToken, ensureSession } from './client'
import { subscribeEvents, type ChangeEvent } from './events'

vi.mock('./client', () => ({
  // 模拟常驻连接：回调一次事件后挂起，等待 abort
  consumeSse: vi.fn(async (_body: unknown, onEvent: (event: unknown) => void) => {
    onEvent({ type: 'changed', scope: 'progress', action: 'created' })
    await new Promise<void>(() => {})
  }),
  ensureSession: vi.fn(async () => true),
  clearToken: vi.fn(),
  getApiBase: vi.fn(() => ''),
  getDeviceId: vi.fn(() => 'device-1'),
  getDeviceToken: vi.fn(() => 'device-token'),
  getToken: vi.fn(() => 'jwt'),
}))

const fetchMock = vi.fn()
vi.stubGlobal('fetch', fetchMock)

function sseResponse(status: number) {
  return {
    status,
    ok: status < 400,
    body: status < 400 ? new ReadableStream<Uint8Array>({ start() { /* 常驻不关闭 */ } }) : null,
  }
}

describe('subscribeEvents', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('连接成功后回调收到的变更事件', async () => {
    fetchMock.mockResolvedValue(sseResponse(200))
    const events: ChangeEvent[] = []
    const stop = subscribeEvents(event => events.push(event))
    await vi.waitFor(() => expect(events).toHaveLength(1))
    expect(events[0]).toEqual({ type: 'changed', scope: 'progress', action: 'created' })
    expect(ensureSession).not.toHaveBeenCalled()
    stop()
  })

  it('401 时用设备凭证换发一次后重连', async () => {
    fetchMock.mockResolvedValueOnce(sseResponse(401)).mockResolvedValue(sseResponse(200))
    const events: ChangeEvent[] = []
    const stop = subscribeEvents(event => events.push(event))
    await vi.waitFor(() => expect(events).toHaveLength(1))
    expect(clearToken).toHaveBeenCalled()
    expect(ensureSession).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    stop()
  })
})
