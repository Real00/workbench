import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { apiError } from '../../shared/api/client'
import { subscriptionApi } from './api'
import type {
  PluginInput,
  SourceInput,
  SubscriptionArticle,
  SubscriptionPlugin,
  SubscriptionSource,
} from './types'

export const useSubscriptionStore = defineStore('subscription', () => {
  const plugins = ref<SubscriptionPlugin[]>([])
  const sources = ref<SubscriptionSource[]>([])
  const articles = ref<SubscriptionArticle[]>([])
  const loading = ref(false)
  const saving = ref(false)
  const refreshing = ref<string | null>(null)
  const error = ref('')
  const initialized = ref(false)

  const pluginMap = computed(() => new Map(plugins.value.map(item => [item.id, item])))
  const sourceMap = computed(() => new Map(sources.value.map(item => [item.id, item])))

  async function initialize() {
    loading.value = true
    error.value = ''
    try {
      const [pluginData, sourceData, articleData] = await Promise.all([
        subscriptionApi.getPlugins(),
        subscriptionApi.getSources(),
        subscriptionApi.getArticles({ limit: 50 }),
      ])
      plugins.value = pluginData
      sources.value = sourceData
      articles.value = articleData
      initialized.value = true
    } catch (cause) {
      error.value = apiError(cause)
    } finally {
      loading.value = false
    }
  }

  async function refresh() {
    try {
      const [pluginData, sourceData, articleData] = await Promise.all([
        subscriptionApi.getPlugins(),
        subscriptionApi.getSources(),
        subscriptionApi.getArticles({ limit: 50 }),
      ])
      plugins.value = pluginData
      sources.value = sourceData
      articles.value = articleData
    } catch {
      /* SSE 后台刷新失败不打扰 */
    }
  }

  async function runSave(action: () => Promise<void>) {
    saving.value = true
    error.value = ''
    try {
      await action()
      return true
    } catch (cause) {
      error.value = apiError(cause)
      return false
    } finally {
      saving.value = false
    }
  }

  async function savePlugin(payload: PluginInput, id?: string) {
    return runSave(async () => {
      if (id) await subscriptionApi.updatePlugin(id, payload)
      else await subscriptionApi.createPlugin(payload)
      await refresh()
    })
  }

  async function removePlugin(id: string) {
    return runSave(async () => {
      await subscriptionApi.deletePlugin(id)
      await refresh()
    })
  }

  async function saveSource(payload: SourceInput, id?: string) {
    return runSave(async () => {
      if (id) await subscriptionApi.updateSource(id, payload)
      else await subscriptionApi.createSource(payload)
      await refresh()
    })
  }

  async function removeSource(id: string) {
    return runSave(async () => {
      await subscriptionApi.deleteSource(id)
      await refresh()
    })
  }

  async function refreshSource(id: string) {
    refreshing.value = id
    error.value = ''
    try {
      await subscriptionApi.refreshSource(id)
      await refresh()
      return true
    } catch (cause) {
      error.value = apiError(cause)
      await refresh()
      return false
    } finally {
      refreshing.value = null
    }
  }

  async function loadArticles(params?: { source_id?: string; q?: string }) {
    articles.value = await subscriptionApi.getArticles({ ...params, limit: 50 })
  }

  async function loadArticle(id: string) {
    return subscriptionApi.getArticle(id)
  }

  return {
    plugins,
    sources,
    articles,
    loading,
    saving,
    refreshing,
    error,
    initialized,
    pluginMap,
    sourceMap,
    initialize,
    refresh,
    savePlugin,
    removePlugin,
    saveSource,
    removeSource,
    refreshSource,
    loadArticles,
    loadArticle,
  }
})
