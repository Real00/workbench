import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useCaptureStore } from './store'
import { api } from '../../shared/api/client'
vi.mock('../../shared/api/client', () => ({
  api: { post: vi.fn() }, apiError: () => 'offline',
  getToken: () => `header.${btoa(JSON.stringify({ sub: 'alice' }))}.signature`,
}))
const storage = new Map<string, string>()
beforeEach(() => {
  storage.clear(); vi.clearAllMocks(); setActivePinia(createPinia())
  vi.stubGlobal('sessionStorage', { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value) })
})
describe('capture reliability', () => {
  it('keeps failed drafts and reuses the request id after reload', async () => {
    const store = useCaptureStore(); store.initialize(); store.draft = '发布想法'
    vi.mocked(api.post).mockRejectedValueOnce(new Error('offline'))
    await store.save()
    const first = vi.mocked(api.post).mock.calls[0]![1]
    expect(store.draft).toBe('发布想法')
    setActivePinia(createPinia())
    const restored = useCaptureStore(); restored.initialize()
    vi.mocked(api.post).mockResolvedValueOnce({ data: {} })
    await restored.save()
    expect(vi.mocked(api.post).mock.calls[1]![1]).toEqual(first)
    expect(restored.draft).toBe('')
    expect(restored.revision).toBe(1)
  })
  it('does not discard text typed while an earlier save is in flight', async () => {
    const store = useCaptureStore(); store.initialize(); store.draft = '第一条'
    let finish!: (value: unknown) => void
    vi.mocked(api.post).mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    const save = store.save()
    store.draft = '第二条'
    finish({ data: {} }); await save
    expect(store.draft).toBe('第二条')
  })
})
