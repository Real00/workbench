<script setup lang="ts">
import { useId, ref, onMounted } from 'vue'
import { useCaptureStore } from './store'
const props = defineProps<{ autofocus?: boolean }>()
const input = ref<HTMLTextAreaElement | null>(null)
onMounted(() => { if (props.autofocus) input.value?.focus() })
const inputId = useId()
const store = useCaptureStore()
</script>
<template>
  <form class="capture-composer" @submit.prevent="store.save()">
    <label class="field-label" :for="inputId">随手记</label>
    <textarea ref="input" :id="inputId" v-model="store.draft" class="input mt-3 min-h-28 py-3" maxlength="20000" placeholder="一个想法、一段资讯、一个待研究的问题……先记下来。" @keydown="event => { if (!event.isComposing && (event.metaKey || event.ctrlKey) && event.key === 'Enter') { event.preventDefault(); store.save() } }" />
    <div class="mt-3 flex items-center justify-between gap-3"><p class="text-xs text-muted">无需分类 · ⌘ / Ctrl + Enter 保存</p><button class="btn-primary" :disabled="store.saving || !store.draft.trim()">{{ store.saving ? '保存中…' : '记下来' }}</button></div>
    <p v-if="store.error" class="error-box mt-3" role="alert">{{ store.error }}</p><p v-if="store.message" class="mt-3 text-sm text-cyan" role="status">{{ store.message }}</p>
  </form>
</template>
