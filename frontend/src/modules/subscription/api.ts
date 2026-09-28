import { api } from '../../shared/api/client'
import type {
  PluginInput,
  SourceInput,
  SubscriptionArticle,
  SubscriptionPlugin,
  SubscriptionSource,
} from './types'

const base = '/subscription'

export const subscriptionApi = {
  getPlugins: async () => (await api.get<SubscriptionPlugin[]>(`${base}/plugins`)).data,
  getPlugin: async (id: string) => (await api.get<SubscriptionPlugin>(`${base}/plugins/${id}`)).data,
  createPlugin: async (payload: PluginInput) => (
    await api.post<SubscriptionPlugin>(`${base}/plugins`, payload)
  ).data,
  updatePlugin: async (id: string, payload: Partial<PluginInput>) => (
    await api.patch<SubscriptionPlugin>(`${base}/plugins/${id}`, payload)
  ).data,
  deletePlugin: async (id: string) => api.delete(`${base}/plugins/${id}`),
  trialPlugin: async (id: string, payload: { body: string; url?: string; config?: Record<string, unknown> }) => (
    await api.post<{ articles: SubscriptionArticle[]; count: number }>(`${base}/plugins/${id}/trial`, payload)
  ).data,

  getSources: async () => (await api.get<SubscriptionSource[]>(`${base}/sources`)).data,
  getSource: async (id: string) => (await api.get<SubscriptionSource>(`${base}/sources/${id}`)).data,
  createSource: async (payload: SourceInput) => (
    await api.post<SubscriptionSource>(`${base}/sources`, payload)
  ).data,
  updateSource: async (id: string, payload: Partial<SourceInput>) => (
    await api.patch<SubscriptionSource>(`${base}/sources/${id}`, payload)
  ).data,
  deleteSource: async (id: string) => api.delete(`${base}/sources/${id}`),
  refreshSource: async (id: string) => (
    await api.post<{ source_id: string; upserted: number; status: string }>(`${base}/sources/${id}/refresh`)
  ).data,

  getArticles: async (params?: { source_id?: string; q?: string; offset?: number; limit?: number }) => (
    await api.get<SubscriptionArticle[]>(`${base}/articles`, { params })
  ).data,
  getArticle: async (id: string) => (await api.get<SubscriptionArticle>(`${base}/articles/${id}`)).data,
}
