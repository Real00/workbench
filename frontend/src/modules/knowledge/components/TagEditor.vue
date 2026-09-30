<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { Save, Trash2, X } from '@lucide/vue'
import { useKnowledgeStore } from '../store'
import { confirmDialog } from '../../../shared/confirm'
import type { TagInput } from '../types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'

const store = useKnowledgeStore()
const blank = (): TagInput => ({ name: '', explanation: '' })
const form = reactive<TagInput>(blank())
const title = computed(() => store.editingTag ? '编辑标签' : '新建标签')

watch(() => store.tagEditorOpen, (open) => {
  if (!open) return
  const source = store.editingTag
  Object.assign(form, source ? { name: source.name, explanation: source.explanation } : blank())
})

async function submit() {
  await store.saveTag({ ...form })
}
async function removeTag() {
  const tag = store.editingTag
  if (!tag) return
  const ok = await confirmDialog({ title: `删除标签「${tag.name}」？`, message: '使用该标签的条目会自动解除关联。', confirmText: '删除标签' })
  if (ok) await store.deleteTag(tag.id)
}
</script>

<template>
  <Teleport to="body">
    <div v-if="store.tagEditorOpen" class="fixed inset-0 z-50 bg-slate-900/30" @click.self="store.tagEditorOpen = false">
      <aside class="editor-panel" role="dialog" aria-modal="true" :aria-label="title">
        <header class="flex items-center justify-between border-b border-line px-5 py-4">
          <div><p class="eyebrow">Knowledge tag</p><h2 class="mt-1 font-display text-xl text-text">{{ title }}</h2></div>
          <Button aria-label="关闭" @click="store.tagEditorOpen = false" variant="ghost" size="icon"><X :size="18" /></Button>
        </header>
        <form class="editor-form" @submit.prevent="submit">
          <div class="editor-fields space-y-5">
          <label class="field-label">名称<Input v-model="form.name" required maxlength="40" /></label>
          <label class="field-label">解释<Textarea v-model="form.explanation" class="min-h-28" required maxlength="2000" /></label>
          <p v-if="store.error" class="error-box">{{ store.error }}</p>
          </div>
          <footer class="editor-actions">
            <Button v-if="store.editingTag" type="button" :disabled="store.saving" @click="removeTag" class="mr-auto" variant="destructive"><Trash2 :size="14" />删除</Button>
            <Button type="button" @click="store.tagEditorOpen = false" variant="outline"><X :size="14" />取消</Button>
            <Button :disabled="store.saving"><Save :size="14" />{{ store.saving ? '保存中…' : '保存标签' }}</Button>
          </footer>
        </form>
      </aside>
    </div>
  </Teleport>
</template>
