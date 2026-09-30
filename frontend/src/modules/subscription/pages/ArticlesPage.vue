<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search } from '@lucide/vue'
import AppSelect, { type AppSelectOption } from '../../../shared/AppSelect.vue'
import { ARTICLE_PAGE_SIZE, useSubscriptionStore } from '../store'
import type { SubscriptionArticle } from '../types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const SCROLL_KEY = 'subscription-articles-scroll'

const store = useSubscriptionStore()
const route = useRoute()
const router = useRouter()

const query = ref('') // 输入框中的关键词，回车/点击搜索后生效
const appliedQuery = ref('') // 已生效的关键词
const sourceId = ref('')
// 从路由恢复筛选时抑制「切换来源即重载」，由恢复逻辑自行加载
let hydrating = false

const sourceOptions = computed<AppSelectOption[]>(() => [
  { value: '', label: '全部来源' },
  ...store.sources.map(item => ({ value: item.id, label: item.name })),
])

const filtersActive = computed(() => Boolean(store.articleFilter.source_id || store.articleFilter.q))

const conditionText = computed(() => {
  const parts: string[] = []
  if (store.articleFilter.source_id) {
    parts.push(`来源：${store.sourceMap.get(store.articleFilter.source_id)?.name ?? '未知来源'}`)
  }
  if (store.articleFilter.q) parts.push(`关键词“${store.articleFilter.q}”`)
  return parts.join(' · ')
})

// —— 摘要与时间（A46：阅读层级；发布时间缺失回退抓取时间）——
const excerptCache = new WeakMap<SubscriptionArticle, string>()

function excerptOf(article: SubscriptionArticle) {
  const cached = excerptCache.get(article)
  if (cached !== undefined) return cached
  let text = ''
  try {
    const container = document.createElement('div')
    container.innerHTML = article.content || ''
    text = (container.textContent || '').replace(/\s+/g, ' ').trim()
  } catch {
    text = String(article.content || '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()
  }
  const excerpt = text.slice(0, 120)
  excerptCache.set(article, excerpt)
  return excerpt
}

function hasExcerpt(article: SubscriptionArticle) {
  const excerpt = excerptOf(article)
  // 摘要与标题相同（或标题已包含摘要）时不重复展示
  return Boolean(excerpt) && excerpt !== article.title && !article.title.includes(excerpt)
}

function parseDate(value: string | null) {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function timeLabel(article: SubscriptionArticle) {
  const published = parseDate(article.published_at)
  if (published) return { text: published.toLocaleDateString(), label: '发布时间' }
  const fetched = parseDate(article.fetched_at)
  if (fetched) return { text: fetched.toLocaleDateString(), label: '抓取时间' }
  return { text: '—', label: '时间未知' }
}

// —— 筛选 / 分页 ——（A44：重置页码、加载更多；A48：query 保存筛选与已加载数）
async function reload() {
  appliedQuery.value = query.value.trim()
  await store.setArticleFilter({ source_id: sourceId.value, q: appliedQuery.value })
}

function clearFilters() {
  query.value = ''
  appliedQuery.value = ''
  void store.setArticleFilter({ source_id: '', q: '' })
}

function loadMore() {
  void store.loadArticles({ reset: false })
}

function retryArticles() {
  if (store.articles.length) loadMore()
  else void reload()
}

function syncQuery() {
  const next: Record<string, string> = {}
  if (store.articleFilter.source_id) next.source_id = store.articleFilter.source_id
  if (store.articleFilter.q) next.q = store.articleFilter.q
  if (store.articles.length > ARTICLE_PAGE_SIZE) next.n = String(store.articles.length)
  const current = route.query
  const same
    = (current.source_id ?? '') === (next.source_id ?? '')
      && (current.q ?? '') === (next.q ?? '')
      && (current.n ?? '') === (next.n ?? '')
  if (!same) void router.replace({ query: next })
}

watch(
  () => [store.articleFilter.source_id, store.articleFilter.q, store.articles.length],
  () => syncQuery(),
)

watch([sourceId], () => {
  if (!hydrating) void reload()
}, { flush: 'sync' })

// —— 滚动位置（A48：详情返回原位置）——
function saveScrollPosition() {
  try {
    sessionStorage.setItem(SCROLL_KEY, String(window.scrollY))
  } catch {
    /* 忽略存储失败 */
  }
}

function restoreScroll() {
  let saved = 0
  try {
    saved = Number(sessionStorage.getItem(SCROLL_KEY) || 0)
  } catch {
    saved = 0
  }
  if (!saved) return
  try {
    sessionStorage.removeItem(SCROLL_KEY)
  } catch {
    /* 忽略 */
  }
  window.scrollTo({ top: saved })
}

onMounted(() => {
  const querySource = typeof route.query.source_id === 'string' ? route.query.source_id : ''
  const queryText = typeof route.query.q === 'string' ? route.query.q : ''
  const queryCount = Number.parseInt(typeof route.query.n === 'string' ? route.query.n : '', 10)
  const filterChanged
    = querySource !== store.articleFilter.source_id || queryText !== store.articleFilter.q
  hydrating = true
  try {
    sourceId.value = querySource
    query.value = queryText
    appliedQuery.value = queryText
  } finally {
    hydrating = false
  }
  if (filterChanged) {
    void store
      .setArticleFilter({ source_id: querySource, q: queryText })
      .then(() => (Number.isFinite(queryCount) && queryCount > store.articles.length
        ? store.restoreArticleCount(queryCount)
        : undefined))
      .then(restoreScroll)
  } else if (Number.isFinite(queryCount) && queryCount > store.articles.length) {
    void store.restoreArticleCount(queryCount).then(restoreScroll)
  } else {
    restoreScroll()
  }
})

function openArticle(id: string) {
  saveScrollPosition()
  void router.push({ path: `/subscription/articles/${id}`, query: route.query })
}
</script>

<template>
  <div>
    <header class="page-header">
      <div>
        <p class="eyebrow">Articles</p>
        <h1>文章</h1>
        <p>订阅源的更新会自动汇聚在这里，供你阅读</p>
      </div>
    </header>

    <div class="mb-4 flex flex-col gap-3 rounded-xl border border-line bg-panel p-2 md:flex-row md:items-center">
      <div class="min-w-0 w-full sm:min-w-48 sm:w-auto">
        <AppSelect v-model="sourceId" :options="sourceOptions" placeholder="来源" />
      </div>
      <label class="search-box search-box--sm flex-1">
        <Search :size="15" />
        <span class="sr-only">搜索</span>
        <Input
          v-model="query"
          autocomplete="off"
          placeholder="搜索标题、作者或正文..."
          class="!h-full !min-h-0 border-0 bg-transparent !p-0 shadow-none focus-visible:ring-0"
          @keydown.enter="reload"
        />
      </label>
      <Button variant="outline" class="h-8 shrink-0" @click="reload">搜索</Button>
    </div>

    <p v-if="store.articlesError" class="error-box mb-3" role="alert">
      <span>文章加载失败：{{ store.articlesError }}</span>
      <Button variant="link" class="h-auto px-0 text-inherit" @click="retryArticles">重试</Button>
    </p>

    <div v-if="store.articlesLoading && !store.articles.length" class="empty-state">
      <p>正在加载文章…</p>
    </div>
    <div v-else-if="!store.articles.length" class="empty-state">
      <template v-if="filtersActive">
        <h2>未找到匹配文章</h2>
        <p>当前条件：{{ conditionText }}。换个关键词或清空筛选试试。</p>
        <Button variant="outline" @click="clearFilters">清空筛选</Button>
      </template>
      <template v-else>
        <h2>暂无文章</h2>
        <p>添加订阅源并点击刷新，或等待定时任务拉取。</p>
        <Button @click="router.push('/subscription')">前往订阅源</Button>
      </template>
    </div>
    <template v-else>
      <div class="knowledge-table">
        <table class="data-table">
          <thead>
            <tr><th>文章</th><th>时间</th></tr>
          </thead>
          <tbody>
            <tr
              v-for="article in store.articles"
              :key="article.id"
              tabindex="0"
              @click="openArticle(article.id)"
              @keydown.enter="openArticle(article.id)"
            >
              <td class="whitespace-normal">
                <div class="flex items-start gap-3">
                  <img
                    v-if="article.cover_url"
                    :src="article.cover_url"
                    alt=""
                    class="mt-0.5 size-10 shrink-0 rounded object-cover"
                  />
                  <div class="min-w-0">
                    <div class="line-clamp-2"><b>{{ article.title }}</b></div>
                    <p v-if="hasExcerpt(article)" class="mt-1 line-clamp-2 max-w-2xl text-xs text-muted-foreground">
                      {{ excerptOf(article) }}
                    </p>
                    <p class="mt-1 text-xs text-muted-foreground">
                      {{ store.sourceMap.get(article.source_id)?.name ?? '未知来源' }}
                      <template v-if="article.author"> · {{ article.author }}</template>
                    </p>
                  </div>
                </div>
              </td>
              <td class="whitespace-nowrap align-top">
                <span class="text-sm">{{ timeLabel(article).text }}</span>
                <span class="block text-xs text-muted-foreground">{{ timeLabel(article).label }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="mt-3 flex flex-wrap items-center justify-center gap-3 text-sm text-muted-foreground">
        <span>
          已加载 {{ store.articles.length }} 篇<template v-if="!store.hasMoreArticles">，没有更多了</template>
        </span>
        <Button
          v-if="store.hasMoreArticles"
          size="sm"
          variant="outline"
          :disabled="store.articlesLoadingMore || store.articlesLoading"
          @click="loadMore"
        >
          {{ store.articlesLoadingMore ? '加载中…' : '加载更多' }}
        </Button>
      </div>
    </template>
  </div>
</template>
