<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Save, Trash2, X } from '@lucide/vue'
import RichTextarea from '../../../shared/RichTextarea.vue'
import { confirmDialog } from '../../../shared/confirm'
import { useDialogFocus } from '../../../shared/useDialogFocus'
import { useKnowledgeStore } from '../store'
import type { EntryInput } from '../types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const store = useKnowledgeStore()
const blank = (): EntryInput => ({ key: '', value: '', tag_ids: [], document_ids: [], aliases: [] })
const form = reactive<EntryInput>(blank())
const aliasesText = ref('')
const panel = ref<HTMLElement | null>(null)
const documentQuery = ref('')
const title = computed(() => store.editingEntry ? '编辑条目' : '新建条目')
const shownDocuments = computed(() => {
  const q = documentQuery.value.trim().toLowerCase()
  if (!q) return store.documents
  return store.documents.filter(item => item.title.toLowerCase().includes(q) || item.body.toLowerCase().includes(q))
})

useDialogFocus(panel, () => store.entryEditorOpen, () => { store.entryEditorOpen = false })

watch(() => store.entryEditorOpen, (open) => {
  if (!open) return
  documentQuery.value = ''
  const source = store.editingEntry
  Object.assign(form, source ? {
    key: source.key,
    value: source.value,
    tag_ids: [...source.tag_ids],
    document_ids: [...source.document_ids],
    aliases: [...source.aliases],
  } : blank())
  aliasesText.value = (source?.aliases ?? []).join(', ')
})

async function submit() {
  await store.saveEntry({
    ...form,
    aliases: aliasesText.value.split(',').map(item => item.trim()).filter(Boolean),
  })
}
async function removeEntry() {
  const entry = store.editingEntry
  if (!entry) return
  const ok = await confirmDialog({ title: `删除条目「${entry.key}」？`, message: '关联文档上的引用会同步移除，操作无法恢复。', confirmText: '删除条目' })
  if (ok) await store.deleteEntry(entry.id)
}
</script>

<template>
  <Teleport to="body">
    <div v-if="store.entryEditorOpen" class="fixed inset-0 z-50 bg-slate-900/30" @click.self="store.entryEditorOpen = false">
      <aside ref="panel" class="editor-panel" role="dialog" aria-modal="true" :aria-label="title">
        <header class="flex items-center justify-between border-b border-line px-5 py-4">
          <div><p class="eyebrow">Knowledge entry</p><h2 class="mt-1 font-display text-xl text-text">{{ title }}</h2></div>
          <Button aria-label="关闭" @click="store.entryEditorOpen = false" variant="ghost" size="icon"><X :size="18" /></Button>
        </header>
        <form class="editor-form" @submit.prevent="submit">
          <div class="editor-fields space-y-5">
          <p class="text-[12px] text-muted-foreground">条目是一条可检索的知识，比如一条术语、约定或事实。写清内容并关联相关文档后，全局搜索与 AI 引用就能找到它。</p>
          <label class="field-label">名称<Input v-model="form.key" required maxlength="200" placeholder="例如：litellm" /></label>
          <label class="field-label">内容<RichTextarea v-model="form.value" :min-height="128" :maxlength="20000" counter required placeholder="例如：litellm 是 myai 的底层依赖服务之一，用于对接各家云商的大语言模型。" /></label>
          <label class="field-label">其他称呼<small>逗号分隔；正文或搜索中出现这些称呼时，也能找到该条目。</small>
            <Input v-model="aliasesText" maxlength="400" />
          </label>
          <fieldset class="field-label">标签<span v-if="form.tag_ids.length" class="font-normal text-muted-foreground">（已选 {{ form.tag_ids.length }} 个）</span>
            <div class="mt-2 flex flex-wrap gap-2">
              <label v-for="tag in store.tags" :key="tag.id" class="flex items-center gap-2 text-xs text-text-secondary">
                <input v-model="form.tag_ids" type="checkbox" :value="tag.id" class="accent-cyan" />{{ tag.name }}
              </label>
            </div>
          </fieldset>
          <fieldset class="field-label">关联文档<span v-if="form.document_ids.length" class="font-normal text-muted-foreground">（已选 {{ form.document_ids.length }} 篇）</span>
            <Input v-if="store.documents.length" v-model="documentQuery" placeholder="搜索文档标题或正文..." class="mt-2 h-8 text-xs" />
            <div class="mt-2 grid max-h-48 gap-2 overflow-y-auto pr-1">
              <label v-for="document in shownDocuments" :key="document.id" class="flex items-start gap-2 text-xs text-text-secondary">
                <input v-model="form.document_ids" type="checkbox" :value="document.id" class="mt-0.5 accent-cyan" />
                <span>{{ document.title }}</span>
              </label>
              <span v-if="!shownDocuments.length" class="text-muted-foreground">{{ documentQuery ? '没有匹配的文档' : '还没有文档' }}</span>
            </div>
          </fieldset>
          <p v-if="store.error" class="error-box">{{ store.error }}</p>
          </div>
          <footer class="editor-actions">
            <Button v-if="store.editingEntry" type="button" :disabled="store.saving" @click="removeEntry" class="mr-auto" variant="destructive"><Trash2 :size="14" />删除</Button>
            <Button type="button" @click="store.entryEditorOpen = false" variant="outline"><X :size="14" />取消</Button>
            <Button :disabled="store.saving"><Save :size="14" />{{ store.saving ? '保存中…' : '保存条目' }}</Button>
          </footer>
        </form>
      </aside>
    </div>
  </Teleport>
</template>
