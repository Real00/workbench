<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ArrowRight, ExternalLink } from '@lucide/vue'
import ArticleContentView from '../../../shared/ArticleContentView.vue'
import { apiError } from '../../../shared/api/client'
import { useSubscriptionStore } from '../store'
import type { SubscriptionArticle } from '../types'
import { Button } from '@/components/ui/button'

const route = useRoute()
const router = useRouter()
const store = useSubscriptionStore()
const article = ref<SubscriptionArticle | null>(null)
const error = ref('')
const loading = ref(true)

async function load(id: string) {
  loading.value = true
  error.value = ''
  try {
    article.value = await store.loadArticle(id)
    window.scrollTo({ top: 0 })
  } catch (cause) {
    error.value = apiError(cause)
  } finally {
    loading.value = false
  }
}

onMounted(() => { void load(String(route.params.id)) })

watch(
  () => route.params.id,
  (id) => {
    if (route.name === 'subscription-article' && id) void load(String(id))
  },
)

// 下一篇范围 = 进入详情前的筛选集合（store 中已加载的文章列表）
const nextArticle = computed(() => {
  const index = store.articles.findIndex(item => item.id === route.params.id)
  if (index < 0) return null
  return store.articles[index + 1] ?? null
})

// 返回列表时带上进入前的筛选与已加载数量，恢复原集合（A48）
function goList() {
  void router.push({ path: '/subscription/articles', query: route.query })
}

function goNext() {
  if (!nextArticle.value) return
  void router.push({ path: `/subscription/articles/${nextArticle.value.id}`, query: route.query })
}

function formatDate(value: string | null) {
  if (!value) return ''
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}
</script>

<template>
  <div>
    <Button variant="ghost" class="mb-3 px-0" @click="goList">
      <ArrowLeft :size="16" />返回文章列表
    </Button>
    <p v-if="error" class="error-banner" role="alert">{{ error }}</p>
    <div v-else-if="loading" class="loading-bar" aria-label="正在加载" />
    <article v-else-if="article" class="mx-auto max-w-3xl">
      <header class="mb-6 space-y-2">
        <p class="eyebrow">{{ store.sourceMap.get(article.source_id)?.name ?? '订阅文章' }}</p>
        <h1 class="text-2xl font-semibold text-text">{{ article.title }}</h1>
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
          <span v-if="article.author">{{ article.author }}</span>
          <span v-if="article.published_at">发布于 {{ formatDate(article.published_at) }}</span>
          <span v-else-if="article.fetched_at">抓取于 {{ formatDate(article.fetched_at) }}</span>
          <a
            v-if="article.url"
            :href="article.url"
            target="_blank"
            rel="noreferrer"
            class="inline-flex items-center gap-1 text-cyan"
          >
            查看原文网页 <ExternalLink :size="14" />
          </a>
        </div>
        <p class="text-xs text-muted-foreground">
          来源：{{ store.sourceMap.get(article.source_id)?.name ?? '未知来源' }}
          <template v-if="article.published_at && article.fetched_at">
            · 抓取于 {{ formatDate(article.fetched_at) }}
          </template>
        </p>
        <img
          v-if="article.cover_url"
          :src="article.cover_url"
          alt=""
          class="mt-4 max-h-72 w-full rounded-xl object-cover"
        />
      </header>
      <ArticleContentView :content="article.content" :format="article.content_format" />
      <footer class="mt-8 flex items-center justify-between gap-3 border-t border-line pt-4">
        <Button variant="outline" @click="goList"><ArrowLeft :size="14" />返回列表</Button>
        <Button v-if="nextArticle" variant="outline" @click="goNext">
          下一篇<ArrowRight :size="14" />
        </Button>
      </footer>
    </article>
  </div>
</template>
