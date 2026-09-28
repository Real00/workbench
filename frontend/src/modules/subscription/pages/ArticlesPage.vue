<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@lucide/vue'
import AppSelect, { type AppSelectOption } from '../../../shared/AppSelect.vue'
import { useSubscriptionStore } from '../store'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const store = useSubscriptionStore()
const router = useRouter()
const query = ref('')
const sourceId = ref('')

const sourceOptions = computed<AppSelectOption[]>(() => [
  { value: '', label: '全部来源' },
  ...store.sources.map(item => ({ value: item.id, label: item.name })),
])

async function reload() {
  await store.loadArticles({
    source_id: sourceId.value || undefined,
    q: query.value.trim() || undefined,
  })
}

watch([sourceId], () => { void reload() })

function formatTime(value: string | null) {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

function openArticle(id: string) {
  void router.push(`/subscription/articles/${id}`)
}
</script>

<template>
  <div class="page-wrap">
    <header class="page-header">
      <div>
        <p class="eyebrow">Articles</p>
        <h1>文章</h1>
        <p>由订阅源刷新解析入库</p>
      </div>
    </header>

    <div class="mb-4 flex flex-col gap-3 rounded-xl border border-line bg-panel p-2 md:flex-row md:items-center">
      <div class="min-w-48">
        <AppSelect v-model="sourceId" :options="sourceOptions" placeholder="来源" />
      </div>
      <label class="search-box !h-8 !min-h-8 flex-1">
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

    <div v-if="!store.articles.length" class="empty-state">
      <h2>暂无文章</h2>
      <p>新建订阅源并点击刷新，或等待定时任务拉取。</p>
    </div>
    <div v-else class="knowledge-table">
      <table class="data-table">
        <thead>
          <tr><th>标题</th><th>来源</th><th>作者</th><th>发布时间</th></tr>
        </thead>
        <tbody>
          <tr
            v-for="article in store.articles"
            :key="article.id"
            tabindex="0"
            @click="openArticle(article.id)"
            @keydown.enter="openArticle(article.id)"
          >
            <td>
              <div class="flex items-start gap-3">
                <img
                  v-if="article.cover_url"
                  :src="article.cover_url"
                  alt=""
                  class="mt-0.5 size-10 rounded object-cover"
                />
                <b>{{ article.title }}</b>
              </div>
            </td>
            <td>{{ store.sourceMap.get(article.source_id)?.name ?? '—' }}</td>
            <td>{{ article.author || '—' }}</td>
            <td>{{ formatTime(article.published_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
