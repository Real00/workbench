import { api } from '../../shared/api/client'
import type { DocumentInput, EntryInput, KnowledgeDocument, KnowledgeEntry, KnowledgeTag, TagInput } from './types'

const base = '/knowledge'

export const knowledgeApi = {
  getTags: async (query = '') => (await api.get<KnowledgeTag[]>(`${base}/tags`, { params: query ? { q: query } : {} })).data,
  createTag: async (payload: TagInput) => (await api.post<KnowledgeTag>(`${base}/tags`, payload)).data,
  updateTag: async (id: string, payload: Partial<TagInput>) => (await api.patch<KnowledgeTag>(`${base}/tags/${id}`, payload)).data,
  deleteTag: async (id: string) => api.delete(`${base}/tags/${id}`),
  getEntries: async (query = '', tagId?: string) => (
    await api.get<KnowledgeEntry[]>(`${base}/entries`, { params: { ...(query ? { q: query } : {}), ...(tagId ? { tag_id: tagId } : {}) } })
  ).data,
  createEntry: async (payload: EntryInput) => (await api.post<KnowledgeEntry>(`${base}/entries`, payload)).data,
  updateEntry: async (id: string, payload: Partial<EntryInput>) => (await api.patch<KnowledgeEntry>(`${base}/entries/${id}`, payload)).data,
  deleteEntry: async (id: string) => api.delete(`${base}/entries/${id}`),
  getDocuments: async (query = '', tagId?: string) => (
    await api.get<KnowledgeDocument[]>(`${base}/documents`, { params: { ...(query ? { q: query } : {}), ...(tagId ? { tag_id: tagId } : {}) } })
  ).data,
  getDocument: async (id: string) => (await api.get<KnowledgeDocument>(`${base}/documents/${id}`)).data,
  createDocument: async (payload: DocumentInput) => (await api.post<KnowledgeDocument>(`${base}/documents`, payload)).data,
  updateDocument: async (id: string, payload: Partial<DocumentInput>) => (await api.patch<KnowledgeDocument>(`${base}/documents/${id}`, payload)).data,
  moveDocument: async (id: string, canvas_x: number, canvas_y: number) => (
    await api.patch<KnowledgeDocument>(`${base}/documents/${id}/canvas`, { canvas_x, canvas_y })
  ).data,
  deleteDocument: async (id: string) => api.delete(`${base}/documents/${id}`),
  extract: async (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return (await api.post<{ filename: string; body: string }>(`${base}/extract`, form, {
      timeout: 60_000,
      transformRequest: [(data, headers) => {
        if (headers && 'delete' in headers) headers.delete('Content-Type')
        return data
      }],
    })).data
  },
  importDocument: async (id: string, file: File, applyBody = false) => {
    const form = new FormData()
    form.append('file', file)
    return (await api.post<KnowledgeDocument>(`${base}/documents/${id}/import`, form, {
      timeout: 60_000,
      params: { apply_body: applyBody ? '1' : '0' },
      transformRequest: [(data, headers) => {
        if (headers && 'delete' in headers) headers.delete('Content-Type')
        return data
      }],
    })).data
  },
}
