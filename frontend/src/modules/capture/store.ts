import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { api, apiError, getToken } from '../../shared/api/client'

export interface Capture {
  id: string
  content: string
  pinned: boolean
  archived: boolean
  created_at: string
}

export const useCaptureStore = defineStore('capture', () => {
  const draft = ref('')
  const draftId = ref<string>(crypto.randomUUID())
  const saving = ref(false)
  const error = ref('')
  const message = ref('')
  const revision = ref(0)
  const quickOpen = ref(false)
  let draftKey = ''

  function initialize() {
    draftKey = ''
    try {
      const payload = JSON.parse(atob((getToken() ?? '').split('.')[1]!.replace(/-/g, '+').replace(/_/g, '/'))) as { sub: string }
      draftKey = `workbench-capture-draft:${payload.sub}`
      const saved = JSON.parse(sessionStorage.getItem(draftKey) ?? 'null') as { content?: string; id?: string } | null
      draft.value = typeof saved?.content === 'string' ? saved.content : ''
      draftId.value = typeof saved?.id === 'string' && /^[0-9a-f-]{36}$/i.test(saved.id) ? saved.id : crypto.randomUUID()
      persist()
    } catch { draft.value = ''; draftId.value = crypto.randomUUID() }
    error.value = ''; message.value = ''
  }
  watch(draft, () => {
    message.value = ''
    draftId.value = crypto.randomUUID()
    persist()
  }, { flush: 'sync' })
  function persist() {
    try { if (draftKey) sessionStorage.setItem(draftKey, JSON.stringify({ content: draft.value, id: draftId.value })) } catch { /* Draft remains in memory. */ }
  }
  async function save() {
    if (saving.value || !draft.value.trim()) return
    saving.value = true; error.value = ''; message.value = ''
    const content = draft.value
    try {
      await api.post('/captures', { id: draftId.value, content })
      if (draft.value === content) draft.value = ''
      message.value = '已记录'; revision.value++
    } catch (cause) { error.value = `保存失败，内容已保留：${apiError(cause)}` }
    finally { saving.value = false }
  }
  function reset() { draftKey = ''; draft.value = ''; quickOpen.value = false; error.value = ''; message.value = '' }
  return { draft, saving, error, message, revision, quickOpen, initialize, save, reset }
})

export const captureApi = {
  list: async (q = '', archived = false, offset = 0) => (await api.get<Capture[]>('/captures', { params: { q, archived, offset } })).data,
  update: async (id: string, changes: Partial<Pick<Capture, 'pinned' | 'archived'>>) => (await api.patch<Capture>(`/captures/${id}`, changes)).data,
}
