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

/** 文章列表单页条数（后端单次请求 limit 上限 100，页大小须 ≤ 100） */
export const ARTICLE_PAGE_SIZE = 50

export interface ArticleFilter {
  source_id: string
  q: string
}

function sameFilter(a: ArticleFilter, b: ArticleFilter) {
  return (a.source_id ?? '') === (b.source_id ?? '') && (a.q ?? '') === (b.q ?? '')
}

export const useSubscriptionStore = defineStore('subscription', () => {
  const plugins = ref<SubscriptionPlugin[]>([])
  const sources = ref<SubscriptionSource[]>([])
  const articles = ref<SubscriptionArticle[]>([])
  const loading = ref(false)
  const saving = ref(false)
  const refreshing = ref<string | null>(null)
  const error = ref('')
  const initialized = ref(false)

  // —— 文章列表分页与筛选状态（A44/A48：筛选、已加载数量保留在 store，可跨页面恢复）——
  const articleFilter = ref<ArticleFilter>({ source_id: '', q: '' })
  const hasMoreArticles = ref(false)
  const articlesLoading = ref(false)
  const articlesLoadingMore = ref(false)
  const articlesError = ref('')
  // 手动刷新的当次结果（仅本次会话，用于区分“成功但无新文章”与“失败”）
  const refreshResults = ref<Record<string, { upserted: number; status: string }>>({})

  const pluginMap = computed(() => new Map(plugins.value.map(item => [item.id, item])))
  const sourceMap = computed(() => new Map(sources.value.map(item => [item.id, item])))

  /** 按页大小分块拉取文章，规避后端单次 limit=100 的上限 */
  async function fetchArticleRange(offset: number, limit: number, filter: ArticleFilter) {
    const out: SubscriptionArticle[] = []
    while (out.length < limit) {
      const size = Math.min(ARTICLE_PAGE_SIZE, limit - out.length)
      const page = await subscriptionApi.getArticles({
        source_id: filter.source_id || undefined,
        q: filter.q || undefined,
        offset: offset + out.length,
        limit: size,
      })
      out.push(...page)
      if (page.length < size) break
    }
    return out
  }

  async function initialize() {
    loading.value = true
    error.value = ''
    try {
      const [pluginData, sourceData] = await Promise.all([
        subscriptionApi.getPlugins(),
        subscriptionApi.getSources(),
      ])
      plugins.value = pluginData
      sources.value = sourceData
      initialized.value = true
    } catch (cause) {
      error.value = apiError(cause)
    } finally {
      loading.value = false
    }
    await loadArticles({ reset: true })
  }

  async function refresh() {
    try {
      const [pluginData, sourceData] = await Promise.all([
        subscriptionApi.getPlugins(),
        subscriptionApi.getSources(),
      ])
      plugins.value = pluginData
      sources.value = sourceData
      // 文章列表保留筛选与已加载数量，只静默更新内容（A48）
      const filter = { ...articleFilter.value }
      const count = articles.value.length
      if (count > 0) {
        // 多取 1 条用于判断后面是否还有更多
        const fresh = await fetchArticleRange(0, count + 1, filter)
        if (sameFilter(filter, articleFilter.value)) {
          articles.value = fresh.slice(0, count)
          hasMoreArticles.value = fresh.length > count
        }
      } else {
        await loadArticles({ reset: true })
      }
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
      const result = await subscriptionApi.refreshSource(id)
      refreshResults.value = {
        ...refreshResults.value,
        [id]: { upserted: result.upserted, status: result.status },
      }
      await refresh()
      return true
    } catch (cause) {
      error.value = apiError(cause)
      refreshResults.value = {
        ...refreshResults.value,
        [id]: { upserted: 0, status: 'error' },
      }
      await refresh()
      return false
    } finally {
      refreshing.value = null
    }
  }

  /**
   * 加载文章列表。
   * - reset=true：按当前筛选从第一页重载（同时重置“已加载数量”）。
   * - reset=false：在已加载内容后追加一页（“加载更多”）。
   */
  async function loadArticles(options: { reset?: boolean } = {}) {
    const reset = options.reset !== false
    if (reset) {
      articlesLoading.value = true
    } else {
      if (articlesLoading.value || articlesLoadingMore.value || !hasMoreArticles.value) return
      articlesLoadingMore.value = true
    }
    articlesError.value = ''
    try {
      const filter = { ...articleFilter.value }
      if (reset) {
        const first = await fetchArticleRange(0, ARTICLE_PAGE_SIZE, filter)
        articles.value = first
        hasMoreArticles.value = first.length === ARTICLE_PAGE_SIZE
      } else {
        const more = await fetchArticleRange(articles.value.length, ARTICLE_PAGE_SIZE, filter)
        if (sameFilter(filter, articleFilter.value)) {
          articles.value = [...articles.value, ...more]
          hasMoreArticles.value = more.length === ARTICLE_PAGE_SIZE
        }
      }
    } catch (cause) {
      articlesError.value = apiError(cause)
    } finally {
      articlesLoading.value = false
      articlesLoadingMore.value = false
    }
  }

  /** 更新筛选并从第一页重载（重置已加载数量） */
  function setArticleFilter(filter: Partial<ArticleFilter>) {
    articleFilter.value = { source_id: filter.source_id ?? '', q: filter.q ?? '' }
    return loadArticles({ reset: true })
  }

  /** 返回列表时恢复之前“加载更多”累积的条数（A48：页码语义 = 已加载数量） */
  async function restoreArticleCount(count: number) {
    if (count <= articles.value.length) return
    articlesLoading.value = true
    articlesError.value = ''
    try {
      const filter = { ...articleFilter.value }
      // 多取 1 条用于判断后面是否还有更多
      const fresh = await fetchArticleRange(0, count + 1, filter)
      if (sameFilter(filter, articleFilter.value)) {
        articles.value = fresh.slice(0, count)
        hasMoreArticles.value = fresh.length > count
      }
    } catch (cause) {
      articlesError.value = apiError(cause)
    } finally {
      articlesLoading.value = false
    }
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
    articleFilter,
    hasMoreArticles,
    articlesLoading,
    articlesLoadingMore,
    articlesError,
    refreshResults,
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
    setArticleFilter,
    restoreArticleCount,
    loadArticle,
  }
})
