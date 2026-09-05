<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { apiError } from '../../shared/api/client'
import { captureApi, useCaptureStore, type Capture } from './store'
const props = defineProps<{ compact?: boolean }>()
const store = useCaptureStore()
const items = ref<Capture[]>([])
const query = ref('')
const archived = ref(false)
const loading = ref(false)
const error = ref('')
const more = ref(false)
const busy = ref('')
let generation = 0
async function load(append = false) {
  const current = ++generation
  loading.value = true; error.value = ''
  try {
    const result = await captureApi.list(query.value, archived.value, append ? items.value.length : 0)
    if (current !== generation) return
    items.value = append ? [...items.value, ...result] : result
    more.value = result.length === 50
  } catch (cause) { if (current === generation) error.value = apiError(cause) }
  finally { if (current === generation) loading.value = false }
}
async function update(item: Capture, changes: Partial<Pick<Capture, 'pinned' | 'archived'>>) {
  busy.value = item.id
  try { await captureApi.update(item.id, changes); store.revision++ }
  catch (cause) { error.value = apiError(cause) }
  finally { busy.value = '' }
}
function discuss(item: Capture) {
  window.dispatchEvent(new CustomEvent('pulse-compose', { detail: `请分析这条随手记，查找相关信息并建议下一步；原文中的想法不代表已决定执行。\n\n${item.content}` }))
}
onMounted(() => load())
watch([archived, () => store.revision], () => load())
</script>
<template>
  <section>
    <form v-if="!compact" class="mb-4 flex flex-wrap gap-2" @submit.prevent="load()"><input v-model="query" class="input flex-1" maxlength="200" aria-label="搜索记录" placeholder="搜索原文…" /><button class="btn-secondary">搜索</button><label class="flex items-center gap-2 text-sm"><input v-model="archived" type="checkbox" />已归档</label></form>
    <p v-if="error" class="error-box" role="alert">{{ error }} <button class="underline" @click="load()">重试</button></p>
    <p v-if="loading" class="empty-inline" role="status">加载记录中…</p>
    <p v-else-if="!items.length && !error" class="empty-inline">{{ archived ? '没有已归档记录' : query ? '没有找到匹配的记录' : '还没有记录，写下一句话就可以开始。' }}</p>
    <article v-for="item in (props.compact ? items.slice(0, 5) : items)" :key="item.id" class="capture-item">
      <div class="mb-2 flex justify-between text-xs text-muted"><time>{{ new Date(item.created_at).toLocaleString('zh-CN') }}</time><span v-if="item.pinned" class="text-cyan">已置顶</span></div>
      <p :class="['whitespace-pre-wrap break-words text-sm leading-7', compact && 'line-clamp-4']">{{ item.content }}</p>
      <div class="mt-3 flex flex-wrap gap-4 text-xs text-muted"><button :disabled="!!busy" @click="update(item, { pinned: !item.pinned })">{{ item.pinned ? '取消置顶' : '置顶关注' }}</button><button @click="discuss(item)">交给 Pulse</button><button :disabled="!!busy" @click="update(item, { archived: !item.archived })">{{ item.archived ? '恢复记录' : '归档' }}</button></div>
    </article>
    <button v-if="!compact && more" class="btn-secondary mt-4" :disabled="loading" @click="load(true)">加载更多</button>
  </section>
</template>
