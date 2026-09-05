<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Save, Trash2, X } from '@lucide/vue'
import { useKnowledgeStore } from '../store'
import type { EntryInput } from '../types'

const store = useKnowledgeStore()
const blank = (): EntryInput => ({ key: '', value: '', tag_ids: [], document_ids: [], aliases: [] })
const form = reactive<EntryInput>(blank())
const aliasesText = ref('')
const title = computed(() => store.editingEntry ? '编辑条目' : '新建条目')

watch(() => store.entryEditorOpen, (open) => {
  if (!open) return
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
</script>

<template>
  <Teleport to="body">
    <div v-if="store.entryEditorOpen" class="fixed inset-0 z-50 bg-black/65" @click.self="store.entryEditorOpen = false">
      <aside class="editor-panel" role="dialog" aria-modal="true" :aria-label="title">
        <header class="flex items-center justify-between border-b border-line px-5 py-4">
          <div><p class="eyebrow">Knowledge entry</p><h2 class="mt-1 font-display text-xl text-white">{{ title }}</h2></div>
          <button class="icon-btn" aria-label="关闭" @click="store.entryEditorOpen = false"><X :size="18" /></button>
        </header>
        <form class="space-y-5 overflow-y-auto p-5" @submit.prevent="submit">
          <label class="field-label">键 / 概念<input v-model="form.key" class="input" required maxlength="200" /></label>
          <label class="field-label">值<textarea v-model="form.value" class="input min-h-28 py-3" required maxlength="20000" /></label>
          <label class="field-label">别名<small>逗号分隔，写入正文供 grep 命中同义词</small>
            <input v-model="aliasesText" class="input" maxlength="400" />
          </label>
          <fieldset class="field-label">标签
            <div class="mt-2 flex flex-wrap gap-2">
              <label v-for="tag in store.tags" :key="tag.id" class="flex items-center gap-2 text-xs text-slate-300">
                <input v-model="form.tag_ids" type="checkbox" :value="tag.id" class="accent-cyan" />{{ tag.name }}
              </label>
            </div>
          </fieldset>
          <fieldset class="field-label">挂到文档
            <div class="mt-2 grid gap-2">
              <label v-for="document in store.documents" :key="document.id" class="flex items-center gap-2 text-xs text-slate-300">
                <input v-model="form.document_ids" type="checkbox" :value="document.id" class="accent-cyan" />{{ document.title }}
              </label>
            </div>
          </fieldset>
          <p v-if="store.error" class="error-box">{{ store.error }}</p>
          <footer class="flex justify-end gap-2 border-t border-line pt-5">
            <button v-if="store.editingEntry" type="button" class="btn-danger mr-auto" :disabled="store.saving" @click="store.deleteEntry(store.editingEntry.id)"><Trash2 :size="14" />删除</button>
            <button type="button" class="btn-secondary" @click="store.entryEditorOpen = false"><X :size="14" />取消</button>
            <button class="btn-primary" :disabled="store.saving"><Save :size="14" />{{ store.saving ? '保存中…' : '保存条目' }}</button>
          </footer>
        </form>
      </aside>
    </div>
  </Teleport>
</template>
