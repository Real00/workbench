<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Save, Trash2, Upload, X } from '@lucide/vue'
import { apiError } from '../../../shared/api/client'
import { confirmDialog } from '../../../shared/confirm'
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
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const store = useKnowledgeStore()
const blank = (): DocumentInput => ({ title: '', body: '', tag_ids: [], entry_ids: [] })
const form = reactive<DocumentInput>(blank())
const pendingFile = ref<File | null>(null)
const extracted = ref('')
const confirmOverwrite = ref(false)
const bodyPreview = ref(false)
const dragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const title = computed(() => store.editingDocument ? '编辑文档' : '新建文档')

watch(() => store.documentEditorOpen, (open) => {
  if (!open) return
  bodyPreview.value = false
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

async function submit() {
  await store.saveDocument({ ...form }, pendingFile.value)
}
async function removeDocument() {
  const document = store.editingDocument
  if (!document) return
  const ok = await confirmDialog({ title: `删除文档「${document.title}」？`, message: '正文与已导入的原件将删除，已关联的条目会保留。', confirmText: '删除文档' })
  if (ok) await store.deleteDocument(document.id)
}
</script>

<template>
  <Teleport to="body">
    <div v-if="store.documentEditorOpen" class="fixed inset-0 z-50 bg-slate-900/30" @click.self="store.closeDocument()">
      <aside class="editor-panel" role="dialog" aria-modal="true" :aria-label="title">
        <header class="flex items-center justify-between border-b border-line px-5 py-4">
          <div><p class="eyebrow">Knowledge document</p><h2 class="mt-1 font-display text-xl text-text">{{ title }}</h2></div>
          <Button aria-label="关闭" @click="store.closeDocument()" variant="ghost" size="icon"><X :size="18" /></Button>
        </header>
        <form class="space-y-5 overflow-y-auto p-5" @submit.prevent="submit">
          <label class="field-label">标题<Input v-model="form.title" required maxlength="200" /></label>
          <div class="field-label">
            <span class="flex items-center justify-between gap-3">正文
              <span class="flex gap-1">
                <Button type="button" variant="ghost" :class="['kind-option', !bodyPreview && 'kind-option--active']" @click="bodyPreview = false">编辑</Button>
                <Button type="button" variant="ghost" :class="['kind-option', bodyPreview && 'kind-option--active']" @click="bodyPreview = true">预览</Button>
              </span>
            </span>
            <small>UTF-8 Markdown，供 Pulse grep 与阅读渲染</small>
            <RichTextarea v-if="!bodyPreview" v-model="form.body" :min-height="360" :max-height="640" :maxlength="200000" mono toolbar />
            <div v-else class="mt-2 min-h-[360px] rounded-lg border border-line bg-ink p-4">
              <MarkdownView :source="form.body" />
            </div>
          </div>
          <div class="field-label">
            <span>导入 Markdown / Word</span>
            <small>拖入或选择 .md / .txt / .docx；保存时原件归档到 raw/</small>
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
                  已有原件 {{ store.editingDocument.raw_filename }}；重新导入会替换归档。
                </template>
                <template v-else>单文件导入，抽出正文后可再编辑。</template>
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
            <p class="text-[12px] text-muted-foreground">抽出的正文尚未覆盖当前内容。确认后才会写入编辑区；保存时原件进 raw/，不会再抽一次。</p>
            <pre class="mt-3 max-h-32 overflow-auto text-[12px] text-text-secondary">{{ extracted }}</pre>
            <Button type="button" @click="applyExtract" class="mt-3" variant="outline">用抽出的正文覆盖</Button>
          </div>
          <p v-else-if="confirmOverwrite && pendingFile" class="text-[12px] text-muted-foreground">已使用 {{ pendingFile.name }} 的抽出正文，保存时只归档原件。</p>
          <fieldset class="field-label">标签
            <div class="mt-2 flex flex-wrap gap-2">
              <label v-for="tag in store.tags" :key="tag.id" class="flex items-center gap-2 text-xs text-text-secondary">
                <input v-model="form.tag_ids" type="checkbox" :value="tag.id" class="accent-cyan" />{{ tag.name }}
              </label>
              <span v-if="!store.tags.length" class="text-muted-foreground">还没有标签</span>
            </div>
          </fieldset>
          <fieldset class="field-label">关联知识条目
            <div class="mt-2 grid gap-2">
              <label v-for="entry in store.entries" :key="entry.id" class="flex items-start gap-2 text-xs text-text-secondary">
                <input v-model="form.entry_ids" type="checkbox" :value="entry.id" class="mt-0.5 accent-cyan" />
                <span><b class="text-text">{{ entry.key }}</b> · {{ entry.value }}</span>
              </label>
              <span v-if="!store.entries.length" class="text-muted-foreground">还没有条目</span>
            </div>
          </fieldset>
          <p v-if="store.error" class="error-box">{{ store.error }}</p>
          <footer class="flex justify-end gap-2 border-t border-line pt-5">
            <Button v-if="store.editingDocument" type="button" :disabled="store.saving" @click="removeDocument" class="mr-auto" variant="destructive"><Trash2 :size="14" />删除</Button>
            <Button type="button" @click="store.closeDocument()" variant="outline"><X :size="14" />取消</Button>
            <Button :disabled="store.saving"><Save :size="14" />{{ store.saving ? '保存中…' : '保存文档' }}</Button>
          </footer>
        </form>
      </aside>
    </div>
  </Teleport>
</template>
