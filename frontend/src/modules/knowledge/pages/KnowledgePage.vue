<script setup lang="ts">
import { computed, defineAsyncComponent, ref } from 'vue'
import { useMediaQuery } from '@vueuse/core'
import { BookOpen, FileText, List, Plus, Search, Tags, Upload, X } from '@lucide/vue'
import { filesFromDataTransfer, PULSE_ATTACHMENT_ACCEPT } from '../../../shared/pulse-session'
import { useKnowledgeStore } from '../store'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { KnowledgeDocument, KnowledgeEntry } from '../types'
const KnowledgeCanvas = defineAsyncComponent(() => import('../components/KnowledgeCanvas.vue'))

type View = 'list' | 'canvas'
type Kind = 'documents' | 'entries' | 'tags'
const view = ref<View>('list')
const kind = ref<Kind>('documents')
const query = ref('')
const tagFilter = ref('')
const store = useKnowledgeStore()
const needle = computed(() => query.value.trim().toLowerCase())
const fileInput = ref<HTMLInputElement | null>(null)
const dragging = ref(false)
const isNarrow = useMediaQuery('(max-width: 768px)')
const expandedEntryIds = ref<string[]>([])
const documentSurface = computed(() => view.value === 'canvas' || kind.value === 'documents')
const documentMap = computed(() => new Map(store.documents.map(item => [item.id, item])))

function matchesTagFilter(tagIds: string[]) {
  return !tagFilter.value || tagIds.includes(tagFilter.value)
}

const filteredDocuments = computed(() => store.documents.filter(item =>
  matchesTagFilter(item.tag_ids)
  && (!needle.value || item.title.toLowerCase().includes(needle.value) || item.body.toLowerCase().includes(needle.value))
))
const filteredEntries = computed(() => store.entries.filter(item =>
  matchesTagFilter(item.tag_ids)
  && (!needle.value || item.key.toLowerCase().includes(needle.value) || item.value.toLowerCase().includes(needle.value))
))
const filteredTags = computed(() => store.tags.filter(item =>
  !needle.value || item.name.toLowerCase().includes(needle.value) || item.explanation.toLowerCase().includes(needle.value)
))

function tagDocumentCount(tagId: string) {
  return store.documents.filter(item => item.tag_ids.includes(tagId)).length
}

function tagEntryCount(tagId: string) {
  return store.entries.filter(item => item.tag_ids.includes(tagId)).length
}

/** 从标签表跳到对应内容：复用列表的标签筛选，展示完整关联集合 */
function viewTagContent(tagId: string, target: Kind) {
  tagFilter.value = tagId
  kind.value = target
  view.value = 'list'
}

function clearFilters() {
  query.value = ''
  tagFilter.value = ''
}

function entryDocuments(entry: KnowledgeEntry) {
  return entry.document_ids
    .map(id => documentMap.value.get(id))
    .filter((item): item is KnowledgeDocument => Boolean(item))
}

function toggleEntryExpanded(id: string) {
  expandedEntryIds.value = expandedEntryIds.value.includes(id)
    ? expandedEntryIds.value.filter(item => item !== id)
    : [...expandedEntryIds.value, id]
}

/** 摘要：去掉 Markdown 记号并压成一行，帮助区分同名或长标题文档 */
function documentSummary(body: string) {
  const plain = body.replace(/[#>*`~[\]()!_-]/g, ' ').replace(/\s+/g, ' ').trim()
  return plain.length > 64 ? `${plain.slice(0, 64)}…` : plain
}

function documentSource(document: KnowledgeDocument) {
  return document.has_raw ? document.raw_filename || '已导入原文件' : '手动创建'
}

function formatDate(value?: string) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('zh-CN')
}

function documentMeta(document: KnowledgeDocument) {
  const updated = formatDate(document.updated_at)
  return [
    documentSource(document),
    `${document.entry_ids.length} 条条目`,
    updated ? `更新于 ${updated}` : '',
  ].filter(Boolean).join(' · ')
}

function pickFiles() {
  fileInput.value?.click()
}

async function onFilesSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const files = [...(input.files ?? [])]
  input.value = ''
  if (files.length) await store.importDocuments(files)
}

async function onDrop(event: DragEvent) {
  dragging.value = false
  if (!documentSurface.value || store.uploading) return
  const files = filesFromDataTransfer(event.dataTransfer)
  if (files.length) await store.importDocuments(files)
}

function onDragOver(event: DragEvent) {
  if (!documentSurface.value || store.uploading) return
  if (![...(event.dataTransfer?.types ?? [])].includes('Files')) return
  dragging.value = true
}

function onDragLeave(event: DragEvent) {
  const next = event.relatedTarget as Node | null
  if (next && (event.currentTarget as Node).contains(next)) return
  dragging.value = false
}
</script>

<template>
  <div
    class="page-wrap knowledge-page"
    :class="{ 'knowledge-page--drop': dragging && documentSurface }"
    @dragover.prevent="onDragOver"
    @dragleave="onDragLeave"
    @drop.prevent="onDrop"
  >
    <input
      ref="fileInput"
      type="file"
      class="sr-only"
      aria-label="选择要导入的文档"
      multiple
      :accept="PULSE_ATTACHMENT_ACCEPT"
      @change="onFilesSelected"
    >
    <header class="page-header">
      <div>
        <p class="eyebrow">Knowledge</p>
        <h1>知识库</h1>
        <p>{{ store.documents.length }} 篇文档 · {{ store.entries.length }} 条条目 · {{ store.tags.length }} 个标签</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <Button aria-label="管理标签" @click="store.openTag()" variant="ghost"><Tags :size="16" /><span class="hidden sm:inline">标签</span></Button>
        <Button aria-label="新建条目" @click="store.openEntry()" variant="ghost"><Plus :size="16" /><span class="hidden sm:inline">条目</span></Button>
        <Button aria-label="上传文档" :disabled="store.uploading" @click="pickFiles" variant="outline">
          <Upload :size="16" /><span class="hidden sm:inline">{{ store.uploading ? '上传中…' : '上传文档' }}</span>
        </Button>
        <Button @click="store.openDocument()"><Plus :size="16" />文档</Button>
      </div>
    </header>
    <p v-if="store.error" class="error-box mb-4">{{ store.error }}</p>
    <p v-if="dragging && documentSurface" class="mb-4 rounded-xl border border-dashed border-cyan bg-panel-2 px-4 py-3 text-sm text-muted-foreground">
      松开即可导入 .md / .txt / .docx，每份文件会建成一篇文档。
    </p>
    <div class="mb-4 flex flex-col gap-3 rounded-xl border border-line bg-panel p-2 md:flex-row md:items-center md:justify-between">
      <div class="segmented-tabs" role="group" aria-label="知识视图">
        <Button type="button" variant="ghost" :class="['view-tab', view === 'list' && 'view-tab--active']" :aria-pressed="view === 'list'" @click="view = 'list'"><List :size="15" />列表</Button>
        <Button type="button" variant="ghost" :class="['view-tab', view === 'canvas' && 'view-tab--active']" :aria-pressed="view === 'canvas'" @click="view = 'canvas'"><FileText :size="15" />画布</Button>
      </div>
      <label class="search-box"><Search :size="15" /><span class="sr-only">搜索</span><Input v-model="query" autocomplete="off" :placeholder="view === 'canvas' ? '搜索文档标题与正文...' : '搜索标题、正文或条目名称...'" class="h-auto min-h-0 border-0 bg-transparent p-0 shadow-none focus-visible:ring-0" /></label>
    </div>
    <KnowledgeCanvas v-if="view === 'canvas'" :documents="filteredDocuments" :searching="Boolean(needle)" />
    <template v-else>
      <div class="content-tabs mb-4" role="group" aria-label="内容类型">
        <Button type="button" variant="ghost" :class="['view-tab', kind === 'documents' && 'view-tab--active']" :aria-pressed="kind === 'documents'" @click="kind = 'documents'">文档</Button>
        <Button type="button" variant="ghost" :class="['view-tab', kind === 'entries' && 'view-tab--active']" :aria-pressed="kind === 'entries'" @click="kind = 'entries'">条目</Button>
        <Button type="button" variant="ghost" :class="['view-tab', kind === 'tags' && 'view-tab--active']" :aria-pressed="kind === 'tags'" @click="kind = 'tags'">标签</Button>
      </div>
      <div v-if="tagFilter && kind !== 'tags'" class="mb-4 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        正在查看标签「{{ store.tagMap.get(tagFilter)?.name ?? '未知标签' }}」的{{ kind === 'documents' ? '文档' : '条目' }}
        <Button type="button" variant="ghost" size="sm" @click="clearFilters"><X :size="14" />清除筛选</Button>
      </div>
      <div v-if="kind === 'documents' && store.loading" class="card p-2">
        <div v-for="i in 5" :key="i" class="flex items-center gap-4 px-3 py-3">
          <div class="skeleton h-3.5 w-1/3" /><div class="skeleton h-3 w-1/4" /><div class="skeleton h-3 w-10" />
        </div>
      </div>
      <div v-else-if="kind === 'documents' && !filteredDocuments.length" class="empty-state">
        <BookOpen :size="28" /><h2>{{ needle || tagFilter ? '没有匹配的文档' : '尚无文档' }}</h2><p>{{ needle || tagFilter ? '尝试其他关键词，或清除筛选条件。' : '创建文档，或拖入 / 选择 .md、.txt、.docx 导入。' }}</p>
        <div class="flex flex-wrap justify-center gap-2">
          <Button v-if="needle || tagFilter" @click="clearFilters" variant="outline">清除筛选</Button>
          <template v-else>
            <Button :disabled="store.uploading" @click="pickFiles" variant="outline"><Upload :size="16" />上传文档</Button>
            <Button @click="store.openDocument()">新建文档</Button>
          </template>
        </div>
      </div>
      <template v-else-if="kind === 'documents'">
        <!-- 手机：紧凑列表，不横滚即可查找与打开 -->
        <ul v-if="isNarrow" class="divide-y divide-line rounded-xl border border-line bg-panel">
          <li v-for="document in filteredDocuments" :key="document.id">
            <button type="button" class="flex w-full flex-col gap-1 px-4 py-3 text-left" @click="store.openDocument(document)">
              <b class="text-sm text-text">{{ document.title }}</b>
              <span v-if="documentSummary(document.body)" class="line-clamp-2 text-[12px] text-muted-foreground">{{ documentSummary(document.body) }}</span>
              <span class="text-[12px] text-muted-foreground">{{ documentMeta(document) }}</span>
            </button>
          </li>
        </ul>
        <div v-else class="knowledge-table"><table class="data-table">
          <thead><tr><th>标题</th><th>标签</th></tr></thead>
          <tbody>
            <tr v-for="document in filteredDocuments" :key="document.id" tabindex="0" @keydown.enter="store.openDocument(document)" @click="store.openDocument(document)">
              <td>
                <span class="knowledge-title"><span class="document-symbol"><FileText :size="17" /></span><b>{{ document.title }}</b></span>
                <span v-if="documentSummary(document.body)" class="mt-1.5 line-clamp-2 pl-7 text-[12px] leading-5 text-muted-foreground">{{ documentSummary(document.body) }}</span>
                <span class="mt-0.5 block pl-7 text-[12px] text-muted-foreground">{{ documentMeta(document) }}</span>
              </td>
              <td><div class="flex flex-wrap gap-1.5"><Badge v-for="tagId in document.tag_ids" :key="tagId" variant="secondary">{{ store.tagMap.get(tagId)?.name ?? '未知标签' }}</Badge><span v-if="!document.tag_ids.length" class="text-muted-foreground">—</span></div></td>
            </tr>
          </tbody>
        </table></div>
      </template>
      <div v-else-if="kind === 'entries' && !filteredEntries.length" class="empty-state">
        <h2>{{ needle || tagFilter ? '没有匹配的条目' : '尚无条目' }}</h2><p>条目是一条可检索的知识，可关联到多篇文档。</p>
        <Button v-if="needle || tagFilter" @click="clearFilters" variant="outline">清除筛选</Button><Button v-else @click="store.openEntry()">新建条目</Button>
      </div>
      <div v-else-if="kind === 'entries'" class="knowledge-table"><table class="data-table">
        <thead><tr><th>名称</th><th>内容</th><th>标签</th></tr></thead>
        <tbody>
          <tr v-for="entry in filteredEntries" :key="entry.id" tabindex="0" @keydown.enter="store.openEntry(entry)" @click="store.openEntry(entry)">
            <td><span class="knowledge-key">{{ entry.key }}</span></td>
            <td class="max-w-xl">
              <span :class="expandedEntryIds.includes(entry.id) ? 'block whitespace-pre-wrap break-words' : 'line-clamp-2 break-words'">{{ entry.value }}</span>
              <button v-if="entry.value.length > 96" type="button" class="mt-1 text-xs text-cyan hover:underline" @click.stop="toggleEntryExpanded(entry.id)">
                {{ expandedEntryIds.includes(entry.id) ? '收起' : '展开全文' }}
              </button>
              <span v-if="entryDocuments(entry).length" class="mt-1.5 block text-[12px] text-muted-foreground">
                关联文档：<template v-for="(document, index) in entryDocuments(entry)" :key="document.id"><button type="button" class="text-cyan hover:underline" @click.stop="store.openDocument(document)">{{ document.title }}</button><span v-if="index < entryDocuments(entry).length - 1">、</span></template>
              </span>
            </td>
            <td><div class="flex flex-wrap gap-1.5"><Badge v-for="tagId in entry.tag_ids" :key="tagId" variant="secondary">{{ store.tagMap.get(tagId)?.name ?? '未知标签' }}</Badge><span v-if="!entry.tag_ids.length" class="text-muted-foreground">—</span></div></td>
          </tr>
        </tbody>
      </table></div>
      <div v-else-if="kind === 'tags' && !filteredTags.length" class="empty-state">
        <h2>{{ needle ? '没有匹配的标签' : '尚无标签' }}</h2><p>每个标签需要一句解释，方便检索时理解分类。</p>
        <Button v-if="needle" @click="query = ''" variant="outline">清除搜索</Button><Button v-else @click="store.openTag()">新建标签</Button>
      </div>
      <div v-else-if="kind === 'tags'" class="knowledge-table"><table class="data-table">
        <thead><tr><th>名称</th><th>解释</th><th>关联内容</th></tr></thead>
        <tbody>
          <tr v-for="tag in filteredTags" :key="tag.id" tabindex="0" @keydown.enter="store.openTag(tag)" @click="store.openTag(tag)">
            <td><Badge variant="secondary">{{ tag.name }}</Badge></td>
            <td>{{ tag.explanation }}</td>
            <td>
              <span class="text-[12px] text-muted-foreground">{{ tagDocumentCount(tag.id) }} 篇文档 · {{ tagEntryCount(tag.id) }} 条条目</span>
              <span v-if="tagDocumentCount(tag.id) || tagEntryCount(tag.id)" class="mt-1 flex gap-3 text-[12px]">
                <button v-if="tagDocumentCount(tag.id)" type="button" class="text-cyan hover:underline" @click.stop="viewTagContent(tag.id, 'documents')">查看文档</button>
                <button v-if="tagEntryCount(tag.id)" type="button" class="text-cyan hover:underline" @click.stop="viewTagContent(tag.id, 'entries')">查看条目</button>
              </span>
              <span v-else class="text-[12px] text-muted-foreground">暂未使用</span>
            </td>
          </tr>
        </tbody>
      </table></div>
    </template>
  </div>
</template>
