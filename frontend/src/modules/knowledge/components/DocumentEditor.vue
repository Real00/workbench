<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Save, Trash2, X } from '@lucide/vue'
import { apiError } from '../../../shared/api/client'
import { confirmDialog } from '../../../shared/confirm'
import MarkdownView from '../../../shared/MarkdownView.vue'
import RichTextarea from '../../../shared/RichTextarea.vue'
import { knowledgeApi } from '../api'
import { useKnowledgeStore } from '../store'
import type { DocumentInput } from '../types'

const store = useKnowledgeStore()
const blank = (): DocumentInput => ({ title: '', body: '', tag_ids: [], entry_ids: [] })
const form = reactive<DocumentInput>(blank())
const pendingFile = ref<File | null>(null)
const extracted = ref('')
const confirmOverwrite = ref(false)
const bodyPreview = ref(false)
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
})

async function onFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    const result = await knowledgeApi.extract(file)
    extracted.value = result.body
    pendingFile.value = file
    store.error = ''
    if (!store.editingDocument?.body) {
      form.body = result.body
      confirmOverwrite.value = true
    }
  } catch (cause) {
    pendingFile.value = null
    extracted.value = ''
    store.error = apiError(cause)
  }
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
    <div v-if="store.documentEditorOpen" class="fixed inset-0 z-50 bg-black/65" @click.self="store.documentEditorOpen = false">
      <aside class="editor-panel" role="dialog" aria-modal="true" :aria-label="title">
        <header class="flex items-center justify-between border-b border-line px-5 py-4">
          <div><p class="eyebrow">Knowledge document</p><h2 class="mt-1 font-display text-xl text-white">{{ title }}</h2></div>
          <button class="icon-btn" aria-label="关闭" @click="store.documentEditorOpen = false"><X :size="18" /></button>
        </header>
        <form class="space-y-5 overflow-y-auto p-5" @submit.prevent="submit">
          <label class="field-label">标题<input v-model="form.title" class="input" required maxlength="200" /></label>
          <div class="field-label">
            <span class="flex items-center justify-between gap-3">正文
              <span class="flex gap-1">
                <button type="button" :class="['kind-option', !bodyPreview && 'kind-option--active']" @click="bodyPreview = false">编辑</button>
                <button type="button" :class="['kind-option', bodyPreview && 'kind-option--active']" @click="bodyPreview = true">预览</button>
              </span>
            </span>
            <small>UTF-8 Markdown，供 Pulse grep 与阅读渲染</small>
            <RichTextarea v-if="!bodyPreview" v-model="form.body" :min-height="360" :max-height="640" :maxlength="200000" mono toolbar />
            <div v-else class="mt-2 min-h-[360px] rounded-lg border border-line bg-[#09141f] p-4">
              <MarkdownView :source="form.body" />
            </div>
          </div>
          <label class="field-label">导入 Markdown / Word
            <input type="file" class="mt-2 text-xs text-muted" accept=".md,.txt,.docx" @change="onFile" />
          </label>
          <div v-if="extracted && store.editingDocument?.body && form.body !== extracted" class="rounded-xl border border-line bg-panel-2 p-4">
            <p class="text-[12px] text-muted">抽出的正文尚未覆盖当前内容。确认后才会写入编辑区；保存时原件进 raw/，不会再抽一次。</p>
            <pre class="mt-3 max-h-32 overflow-auto text-[12px] text-slate-300">{{ extracted }}</pre>
            <button type="button" class="btn-secondary mt-3" @click="applyExtract">用抽出的正文覆盖</button>
          </div>
          <p v-else-if="confirmOverwrite && pendingFile" class="text-[12px] text-muted">已使用 {{ pendingFile.name }} 的抽出正文，保存时只归档原件。</p>
          <fieldset class="field-label">标签
            <div class="mt-2 flex flex-wrap gap-2">
              <label v-for="tag in store.tags" :key="tag.id" class="flex items-center gap-2 text-xs text-slate-300">
                <input v-model="form.tag_ids" type="checkbox" :value="tag.id" class="accent-cyan" />{{ tag.name }}
              </label>
              <span v-if="!store.tags.length" class="text-muted">还没有标签</span>
            </div>
          </fieldset>
          <fieldset class="field-label">关联知识条目
            <div class="mt-2 grid gap-2">
              <label v-for="entry in store.entries" :key="entry.id" class="flex items-start gap-2 text-xs text-slate-300">
                <input v-model="form.entry_ids" type="checkbox" :value="entry.id" class="mt-0.5 accent-cyan" />
                <span><b class="text-white">{{ entry.key }}</b> · {{ entry.value }}</span>
              </label>
              <span v-if="!store.entries.length" class="text-muted">还没有条目</span>
            </div>
          </fieldset>
          <p v-if="store.error" class="error-box">{{ store.error }}</p>
          <footer class="flex justify-end gap-2 border-t border-line pt-5">
            <button v-if="store.editingDocument" type="button" class="btn-danger mr-auto" :disabled="store.saving" @click="removeDocument"><Trash2 :size="14" />删除</button>
            <button type="button" class="btn-secondary" @click="store.documentEditorOpen = false"><X :size="14" />取消</button>
            <button class="btn-primary" :disabled="store.saving"><Save :size="14" />{{ store.saving ? '保存中…' : '保存文档' }}</button>
          </footer>
        </form>
      </aside>
    </div>
  </Teleport>
</template>
