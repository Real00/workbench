<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ExternalLink } from '@lucide/vue'
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

onMounted(async () => {
  loading.value = true
  error.value = ''
  try {
    article.value = await store.loadArticle(String(route.params.id))
  } catch (cause) {
    error.value = apiError(cause)
  } finally {
    loading.value = false
  }
})

function formatTime(value: string | null) {
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
    <Button variant="ghost" class="mb-3 px-0" @click="router.push('/subscription/articles')">
      <ArrowLeft :size="16" />返回文章列表
    </Button>
    <p v-if="error" class="error-banner" role="alert">{{ error }}</p>
    <div v-else-if="loading" class="loading-bar" aria-label="正在加载" />
    <article v-else-if="article" class="mx-auto max-w-3xl">
      <header class="mb-6 space-y-2">
        <p class="eyebrow">{{ store.sourceMap.get(article.source_id)?.name ?? '订阅文章' }}</p>
        <h1 class="text-2xl font-semibold text-text">{{ article.title }}</h1>
        <div class="flex flex-wrap gap-3 text-sm text-muted-foreground">
          <span v-if="article.author">{{ article.author }}</span>
          <span v-if="article.published_at">{{ formatTime(article.published_at) }}</span>
          <span>{{ article.content_format }}</span>
          <a
            v-if="article.url"
            :href="article.url"
            target="_blank"
            rel="noreferrer"
            class="inline-flex items-center gap-1 text-cyan"
          >
            原文 <ExternalLink :size="14" />
          </a>
        </div>
        <img
          v-if="article.cover_url"
          :src="article.cover_url"
          alt=""
          class="mt-4 max-h-72 w-full rounded-xl object-cover"
        />
      </header>
      <ArticleContentView :content="article.content" :format="article.content_format" />
    </article>
  </div>
</template>
