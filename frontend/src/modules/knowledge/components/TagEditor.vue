<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Save, Trash2, X } from '@lucide/vue'
import { useKnowledgeStore } from '../store'
import { confirmDialog } from '../../../shared/confirm'
import { useDialogFocus } from '../../../shared/useDialogFocus'
import type { TagInput } from '../types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'

const store = useKnowledgeStore()
const blank = (): TagInput => ({ name: '', explanation: '' })
const form = reactive<TagInput>(blank())
const panel = ref<HTMLElement | null>(null)
const title = computed(() => store.editingTag ? '编辑标签' : '新建标签')
/** 影响范围：从现有文档与条目统计该标签的使用情况 */
const usage = computed(() => {
  const id = store.editingTag?.id
  if (!id) return null
  return {
    documents: store.documents.filter(item => item.tag_ids.includes(id)).length,
    entries: store.entries.filter(item => item.tag_ids.includes(id)).length,
  }
})

useDialogFocus(panel, () => store.tagEditorOpen, () => { store.tagEditorOpen = false })

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
  const ok = await confirmDialog({ title: `删除标签「${tag.name}」？`, message: `使用该标签的 ${usage.value?.documents ?? 0} 篇文档和 ${usage.value?.entries ?? 0} 条条目会自动解除关联。`, confirmText: '删除标签' })
  if (ok) await store.deleteTag(tag.id)
}
</script>

<template>
  <Teleport to="body">
    <div v-if="store.tagEditorOpen" class="fixed inset-0 z-50 bg-slate-900/30" @click.self="store.tagEditorOpen = false">
      <aside ref="panel" class="editor-panel" role="dialog" aria-modal="true" :aria-label="title">
        <header class="flex items-center justify-between border-b border-line px-5 py-4">
          <div><p class="eyebrow">Knowledge tag</p><h2 class="mt-1 font-display text-xl text-text">{{ title }}</h2></div>
          <Button aria-label="关闭" @click="store.tagEditorOpen = false" variant="ghost" size="icon"><X :size="16" /></Button>
        </header>
        <form class="editor-form" @submit.prevent="submit">
          <div class="editor-fields">
            <div class="tag-editor-content space-y-5">
              <label class="field-label">名称<Input v-model="form.name" required maxlength="40" /></label>
              <label class="field-label">解释<Textarea v-model="form.explanation" class="min-h-28" required maxlength="2000" /></label>
              <p class="text-[12px] text-muted-foreground">
                <template v-if="usage">该标签目前被 {{ usage.documents }} 篇文档、{{ usage.entries }} 条条目使用；重命名或删除会影响这些内容。</template>
                <template v-else>保存后即可在文档与条目上使用，方便按主题检索与筛选。</template>
              </p>
              <p v-if="store.error" class="error-box">{{ store.error }}</p>
            </div>
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

<style scoped>
/* 短表单收紧内容宽度，让主动作更靠近内容 */
.tag-editor-content {
  max-width: 420px;
}
</style>
