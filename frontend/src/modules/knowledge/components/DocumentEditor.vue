<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Save, Trash2, Upload, X } from '@lucide/vue'
import { apiError } from '../../../shared/api/client'
import { confirmDialog } from '../../../shared/confirm'
import { useDialogFocus } from '../../../shared/useDialogFocus'
import MarkdownView from '../../../shared/MarkdownView.vue'
import {
  filesFromDataTransfer,
  isSupportedPulseAttachment,
  PULSE_ATTACHMENT_ACCEPT,
} from '../../../shared/pulse-session'
import RichTextarea from '../../../shared/RichTextarea.vue'
import { knowledgeApi } from '../api'
import { useKnowledgeStore } from '../store'
import type { DocumentInput } from '../types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const store = useKnowledgeStore()
const blank = (): DocumentInput => ({ title: '', body: '', tag_ids: [], entry_ids: [] })
const form = reactive<DocumentInput>(blank())
const pendingFile = ref<File | null>(null)
const extracted = ref('')
const confirmOverwrite = ref(false)
/** 已有文档默认进入阅读态，新建文档直接编辑 */
const mode = ref<'read' | 'edit'>('read')
const dragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const panel = ref<HTMLElement | null>(null)
const entryQuery = ref('')
const title = computed(() => {
  if (!store.editingDocument) return '新建文档'
  return mode.value === 'read' ? store.editingDocument.title || '文档详情' : '编辑文档'
})
const updatedAt = computed(() => {
  const value = store.editingDocument?.updated_at
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString('zh-CN')
})
const shownEntries = computed(() => {
  const q = entryQuery.value.trim().toLowerCase()
  if (!q) return store.entries
  return store.entries.filter(item =>
    item.key.toLowerCase().includes(q)
    || item.value.toLowerCase().includes(q)
    || item.aliases.some(alias => alias.toLowerCase().includes(q)))
})

useDialogFocus(panel, () => store.documentEditorOpen, () => store.closeDocument())

function syncForm() {
  const source = store.editingDocument
  Object.assign(form, source ? {
    title: source.title,
    body: source.body,
    tag_ids: [...source.tag_ids],
    entry_ids: [...source.entry_ids],
  } : blank())
  pendingFile.value = null
  extracted.value = ''
  confirmOverwrite.value = false
  dragging.value = false
}

watch(() => store.documentEditorOpen, (open) => {
  if (!open) return
  mode.value = store.editingDocument ? 'read' : 'edit'
  entryQuery.value = ''
  syncForm()
})

async function ingestFile(file: File | undefined | null) {
  if (!file) return
  if (!isSupportedPulseAttachment(file.name)) {
    store.error = '仅支持 .md / .txt / .docx'
    return
  }
  try {
    const result = await knowledgeApi.extract(file)
    extracted.value = result.body
    pendingFile.value = file
    store.error = ''
    if (!form.body.trim()) {
      form.body = result.body
      confirmOverwrite.value = true
      if (!form.title.trim()) {
        form.title = file.name.replace(/\.[^.]+$/, '') || form.title
      }
    }
  } catch (cause) {
    pendingFile.value = null
    extracted.value = ''
    store.error = apiError(cause)
  }
}

async function onFile(event: Event) {
  const input = event.target as HTMLInputElement
  await ingestFile(input.files?.[0])
  input.value = ''
}

function pickFile() {
  fileInput.value?.click()
}

async function onDrop(event: DragEvent) {
  dragging.value = false
  const file = filesFromDataTransfer(event.dataTransfer)[0]
  await ingestFile(file)
}

function onDragOver(event: DragEvent) {
  if (![...(event.dataTransfer?.types ?? [])].includes('Files')) return
  dragging.value = true
}

function onDragLeave(event: DragEvent) {
  const next = event.relatedTarget as Node | null
  if (next && (event.currentTarget as Node).contains(next)) return
  dragging.value = false
}

function applyExtract() {
  form.body = extracted.value
  confirmOverwrite.value = true
}

function cancelEdit() {
  if (!store.editingDocument) {
    store.closeDocument()
    return
  }
  syncForm()
  mode.value = 'read'
}

async function submit() {
  const ok = await store.saveDocument({ ...form }, pendingFile.value)
  if (ok && store.documentEditorOpen) mode.value = 'read'
}

async function removeDocument() {
  const document = store.editingDocument
  if (!document) return
  const ok = await confirmDialog({ title: `删除文档「${document.title}」？`, message: '正文与已导入的原文件将一起删除，已关联的条目会保留。', confirmText: '删除文档' })
  if (ok) await store.deleteDocument(document.id)
}
</script>

<template>
  <Teleport to="body">
    <div v-if="store.documentEditorOpen" class="fixed inset-0 z-50 bg-slate-900/30" @click.self="store.closeDocument()">
      <aside ref="panel" class="editor-panel doc-editor-panel" role="dialog" aria-modal="true" :aria-label="title">
        <header class="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
          <div class="min-w-0"><p class="eyebrow">Knowledge document</p><h2 class="mt-1 truncate font-display text-xl text-text">{{ title }}</h2></div>
          <Button aria-label="关闭" @click="store.closeDocument()" variant="ghost" size="icon"><X :size="18" /></Button>
        </header>
        <form class="editor-form" @submit.prevent="submit">
          <div class="editor-fields space-y-5">
            <template v-if="mode === 'read' && store.editingDocument">
              <p class="text-[12px] text-muted-foreground">
                <template v-if="updatedAt">更新于 {{ updatedAt }} · </template>
                <template v-if="store.editingDocument.has_raw">原文件 {{ store.editingDocument.raw_filename }}</template>
                <template v-else>未导入原文件</template>
                · {{ form.tag_ids.length }} 个标签 · {{ form.entry_ids.length }} 条关联条目
              </p>
              <div class="min-h-[220px] rounded-lg border border-line bg-ink p-4">
                <MarkdownView :source="form.body" />
              </div>
              <div v-if="form.tag_ids.length" class="flex flex-wrap gap-1.5">
                <Badge v-for="tagId in form.tag_ids" :key="tagId" variant="secondary">{{ store.tagMap.get(tagId)?.name ?? '未知标签' }}</Badge>
              </div>
              <div v-if="form.entry_ids.length" class="rounded-xl border border-line bg-panel-2 p-4">
                <p class="text-[12px] font-medium text-text-secondary">关联知识条目</p>
                <ul class="mt-2 space-y-1 text-[12px] text-text-secondary">
                  <li v-for="entryId in form.entry_ids" :key="entryId">
                    <b class="text-text">{{ store.entryMap.get(entryId)?.key ?? '未知条目' }}</b>
                    <template v-if="store.entryMap.get(entryId)"> · {{ store.entryMap.get(entryId)?.value }}</template>
                  </li>
                </ul>
              </div>
            </template>
            <template v-else>
              <label class="field-label">标题<Input v-model="form.title" required maxlength="200" /></label>
              <div class="field-label">
                <span>正文</span>
                <small>支持 Markdown；正文会用于全局搜索与 AI 引用。</small>
                <RichTextarea v-model="form.body" :min-height="220" :max-height="640" :maxlength="200000" mono toolbar />
              </div>
              <div class="field-label">
                <span>导入文件</span>
                <small>拖入或选择 .md / .txt / .docx，仅提取文字到正文；图片等其余内容不会导入，原文件会完整保留。</small>
                <button
                  type="button"
                  class="knowledge-import-drop relative"
                  :class="{ 'knowledge-import-drop--active': dragging }"
                  @click="pickFile"
                  @dragover.prevent="onDragOver"
                  @dragleave="onDragLeave"
                  @drop.prevent="onDrop"
                >
                  <span class="flex items-center gap-2 text-sm text-text">
                    <Upload :size="16" />
                    {{ pendingFile ? pendingFile.name : '拖拽到此处，或点击选择文件' }}
                  </span>
                  <span class="text-[12px] text-muted-foreground">
                    <template v-if="store.editingDocument?.has_raw">
                      已有原文件 {{ store.editingDocument.raw_filename }}；重新导入会替换它。
                    </template>
                    <template v-else>单文件导入，抽出文字后可再编辑。</template>
                  </span>
                  <input
                    ref="fileInput"
                    type="file"
                    :accept="PULSE_ATTACHMENT_ACCEPT"
                    @change="onFile"
                    @click.stop
                  >
                </button>
              </div>
              <div v-if="extracted && store.editingDocument?.body && form.body !== extracted" class="rounded-xl border border-line bg-panel-2 p-4">
                <p class="text-[12px] text-muted-foreground">抽出的文字尚未覆盖当前内容，确认后才会写入编辑区；保存时原文件会完整保留。</p>
                <pre class="mt-3 max-h-32 overflow-auto text-[12px] text-text-secondary">{{ extracted }}</pre>
                <Button type="button" @click="applyExtract" class="mt-3" variant="outline">用抽出的文字覆盖</Button>
              </div>
              <p v-else-if="confirmOverwrite && pendingFile" class="text-[12px] text-muted-foreground">已使用 {{ pendingFile.name }} 的文字内容，保存时原文件会完整保留。</p>
              <fieldset class="field-label">标签<span v-if="form.tag_ids.length" class="font-normal text-muted-foreground">（已选 {{ form.tag_ids.length }} 个）</span>
                <div class="mt-2 flex flex-wrap gap-2">
                  <label v-for="tag in store.tags" :key="tag.id" class="flex items-center gap-2 text-xs text-text-secondary">
                    <input v-model="form.tag_ids" type="checkbox" :value="tag.id" class="accent-cyan" />{{ tag.name }}
                  </label>
                  <span v-if="!store.tags.length" class="text-muted-foreground">还没有标签</span>
                </div>
              </fieldset>
              <fieldset class="field-label">关联知识条目<span v-if="form.entry_ids.length" class="font-normal text-muted-foreground">（已选 {{ form.entry_ids.length }} 个）</span>
                <Input v-if="store.entries.length" v-model="entryQuery" placeholder="搜索条目名称或内容..." class="mt-2 h-8 text-xs" />
                <div class="mt-2 grid max-h-48 gap-2 overflow-y-auto pr-1">
                  <label v-for="entry in shownEntries" :key="entry.id" class="flex items-start gap-2 text-xs text-text-secondary">
                    <input v-model="form.entry_ids" type="checkbox" :value="entry.id" class="mt-0.5 accent-cyan" />
                    <span><b class="text-text">{{ entry.key }}</b> · {{ entry.value }}</span>
                  </label>
                  <span v-if="!shownEntries.length" class="text-muted-foreground">{{ entryQuery ? '没有匹配的条目' : '还没有条目' }}</span>
                </div>
              </fieldset>
              <p v-if="store.error" class="error-box">{{ store.error }}</p>
            </template>
          </div>
          <footer class="editor-actions">
            <template v-if="mode === 'read'">
              <Button v-if="store.editingDocument" type="button" :disabled="store.saving" @click="removeDocument" class="mr-auto" variant="destructive"><Trash2 :size="14" />删除</Button>
              <Button type="button" @click="store.closeDocument()" variant="outline"><X :size="14" />关闭</Button>
              <Button type="button" @click="mode = 'edit'">编辑文档</Button>
            </template>
            <template v-else>
              <Button v-if="store.editingDocument" type="button" :disabled="store.saving" @click="removeDocument" class="mr-auto" variant="destructive"><Trash2 :size="14" />删除</Button>
              <Button type="button" @click="cancelEdit" variant="outline"><X :size="14" />取消</Button>
              <Button type="submit" :disabled="store.saving"><Save :size="14" />{{ store.saving ? '保存中…' : '保存文档' }}</Button>
            </template>
          </footer>
        </form>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
/* 文档抽屉比默认 560px 更宽，给阅读与编辑留出空间；手机上仍占满全宽 */
.doc-editor-panel {
  width: min(100%, 760px);
}
</style>
