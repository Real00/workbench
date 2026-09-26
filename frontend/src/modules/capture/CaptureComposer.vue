<script setup lang="ts">
import { useId, onMounted } from 'vue'
import { useCaptureStore } from './store'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

const props = defineProps<{ autofocus?: boolean }>()
const inputId = useId()
const store = useCaptureStore()
function onComposerKeydown(event: KeyboardEvent) {
  if (!event.isComposing && (event.metaKey || event.ctrlKey) && event.key === 'Enter') {
    event.preventDefault()
    store.save()
  }
}
onMounted(() => {
  if (props.autofocus) document.getElementById(inputId)?.focus()
})
</script>
<template>
  <form class="capture-composer" @submit.prevent="store.save()">
    <label class="field-label" :for="inputId">随手记</label>
    <Textarea
      :id="inputId"
      v-model="store.draft"
      class="mt-3 min-h-28"
      maxlength="20000"
      placeholder="一个想法、一段资讯、一个待研究的问题……先记下来。"
      @keydown="onComposerKeydown"
    />
    <div class="mt-3 flex items-center justify-between gap-3"><p class="text-xs text-muted-foreground">无需分类 · ⌘ / Ctrl + Enter 保存</p><Button :disabled="store.saving || !store.draft.trim()">{{ store.saving ? '保存中…' : '记下来' }}</Button></div>
    <p v-if="store.error" class="error-box mt-3" role="alert">{{ store.error }}</p><p v-if="store.message" class="mt-3 text-sm text-cyan" role="status">{{ store.message }}</p>
  </form>
</template>
