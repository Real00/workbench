<script setup lang="ts">
import { computed, defineAsyncComponent, ref } from 'vue'
import { BookOpen, FileText, List, Plus, Search, Tags } from '@lucide/vue'
import { useKnowledgeStore } from '../store'
const KnowledgeCanvas = defineAsyncComponent(() => import('../components/KnowledgeCanvas.vue'))

type View = 'list' | 'canvas'
type Kind = 'documents' | 'entries' | 'tags'
const view = ref<View>('list')
const kind = ref<Kind>('documents')
const query = ref('')
const store = useKnowledgeStore()
const needle = computed(() => query.value.trim().toLowerCase())

const filteredDocuments = computed(() => store.documents.filter(item =>
  !needle.value || item.title.toLowerCase().includes(needle.value) || item.body.toLowerCase().includes(needle.value)
))
const filteredEntries = computed(() => store.entries.filter(item =>
  !needle.value || item.key.toLowerCase().includes(needle.value) || item.value.toLowerCase().includes(needle.value)
))
const filteredTags = computed(() => store.tags.filter(item =>
  !needle.value || item.name.toLowerCase().includes(needle.value) || item.explanation.toLowerCase().includes(needle.value)
))

function tagNames(ids: string[]) {
  return ids.map(id => store.tagMap.get(id)?.name).filter(Boolean).join(' / ')
}
</script>

<template>
  <div class="page-wrap">
    <header class="page-header">
      <div>
        <p class="eyebrow">Knowledge</p>
        <h1>知识库</h1>
        <p>{{ store.documents.length }} 篇文档 · {{ store.entries.length }} 条条目 · {{ store.tags.length }} 个标签</p>
      </div>
      <div class="flex gap-2">
        <button class="btn-secondary" @click="store.openTag()"><Tags :size="16" />标签</button>
        <button class="btn-secondary" @click="store.openEntry()"><Plus :size="16" />条目</button>
        <button class="btn-primary" @click="store.openDocument()"><Plus :size="16" />文档</button>
      </div>
    </header>
    <div class="mb-4 flex flex-col gap-3 rounded-xl border border-line bg-panel p-2 md:flex-row md:items-center md:justify-between">
      <div class="flex overflow-x-auto" role="tablist" aria-label="知识视图">
        <button :class="['view-tab', view === 'list' && 'view-tab--active']" @click="view = 'list'"><List :size="15" />列表</button>
        <button :class="['view-tab', view === 'canvas' && 'view-tab--active']" @click="view = 'canvas'"><FileText :size="15" />画布</button>
      </div>
      <label class="search-box"><Search :size="15" /><span class="sr-only">搜索</span><input v-model="query" autocomplete="off" placeholder="搜索标题、正文或条目键..." /></label>
    </div>
    <KnowledgeCanvas v-if="view === 'canvas'" :documents="filteredDocuments" :searching="Boolean(needle)" />
    <template v-else>
      <div class="mb-4 flex gap-2">
        <button :class="['view-tab', kind === 'documents' && 'view-tab--active']" @click="kind = 'documents'">文档</button>
        <button :class="['view-tab', kind === 'entries' && 'view-tab--active']" @click="kind = 'entries'">条目</button>
        <button :class="['view-tab', kind === 'tags' && 'view-tab--active']" @click="kind = 'tags'">标签</button>
      </div>
      <div v-if="kind === 'documents' && store.loading" class="card p-2">
        <div v-for="i in 5" :key="i" class="flex items-center gap-4 px-3 py-3">
          <div class="skeleton h-3.5 w-1/3" /><div class="skeleton h-3 w-1/4" /><div class="skeleton h-3 w-10" />
        </div>
      </div>
      <div v-else-if="kind === 'documents' && !filteredDocuments.length" class="empty-state">
        <BookOpen :size="28" /><h2>{{ needle ? '没有匹配的文档' : '尚无文档' }}</h2><p>{{ needle ? '尝试其他关键词或清除搜索。' : '创建文档，沉淀可检索的工作知识。' }}</p>
        <button v-if="needle" class="btn-secondary" @click="query = ''">清除搜索</button><button v-else class="btn-primary" @click="store.openDocument()">新建文档</button>
      </div>
      <div v-else-if="kind === 'documents'" class="knowledge-table"><table class="data-table">
        <thead><tr><th>标题</th><th>标签</th><th>条目</th></tr></thead>
        <tbody>
          <tr v-for="document in filteredDocuments" :key="document.id" tabindex="0" @keydown.enter="store.openDocument(document)" @click="store.openDocument(document)">
            <td class="text-white">{{ document.title }}</td>
            <td>{{ tagNames(document.tag_ids) || '—' }}</td>
            <td>{{ document.entry_ids.length }}</td>
          </tr>
        </tbody>
      </table></div>
      <div v-else-if="kind === 'entries' && !filteredEntries.length" class="empty-state">
        <h2>{{ needle ? '没有匹配的条目' : '尚无条目' }}</h2><p>条目是键值对，可被多篇文档引用。</p>
        <button v-if="needle" class="btn-secondary" @click="query = ''">清除搜索</button><button v-else class="btn-primary" @click="store.openEntry()">新建条目</button>
      </div>
      <div v-else-if="kind === 'entries'" class="knowledge-table"><table class="data-table">
        <thead><tr><th>键</th><th>值</th><th>标签</th></tr></thead>
        <tbody>
          <tr v-for="entry in filteredEntries" :key="entry.id" tabindex="0" @keydown.enter="store.openEntry(entry)" @click="store.openEntry(entry)">
            <td class="text-white">{{ entry.key }}</td>
            <td class="max-w-xl truncate">{{ entry.value }}</td>
            <td>{{ tagNames(entry.tag_ids) || '—' }}</td>
          </tr>
        </tbody>
      </table></div>
      <div v-else-if="kind === 'tags' && !filteredTags.length" class="empty-state">
        <h2>{{ needle ? '没有匹配的标签' : '尚无标签' }}</h2><p>每个标签需要一句解释，方便检索时理解分类。</p>
        <button v-if="needle" class="btn-secondary" @click="query = ''">清除搜索</button><button v-else class="btn-primary" @click="store.openTag()">新建标签</button>
      </div>
      <div v-else-if="kind === 'tags'" class="knowledge-table"><table class="data-table">
        <thead><tr><th>名称</th><th>解释</th></tr></thead>
        <tbody>
          <tr v-for="tag in filteredTags" :key="tag.id" tabindex="0" @keydown.enter="store.openTag(tag)" @click="store.openTag(tag)">
            <td class="text-white">{{ tag.name }}</td>
            <td>{{ tag.explanation }}</td>
          </tr>
        </tbody>
      </table></div>
    </template>
  </div>
</template>
