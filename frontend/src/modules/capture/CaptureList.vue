<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { Archive, NotebookPen, Search } from '@lucide/vue'
import { apiError } from '../../shared/api/client'
import { captureApi, useCaptureStore, type Capture } from './store'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
function resetFilters() {
  query.value = ''
  archived.value = false
  load()
}
function focusComposer() {
  document.querySelector<HTMLTextAreaElement>('.captures-page .capture-composer textarea')?.focus()
}
onMounted(() => load())
watch([archived, () => store.revision], () => load())
</script>
<template>
  <section>
    <form v-if="!compact" class="mb-4 flex flex-wrap gap-2" @submit.prevent="load()"><Input v-model="query" maxlength="200" aria-label="搜索记录" placeholder="搜索原文…" class="flex-1" /><Button variant="outline">搜索</Button><label class="flex items-center gap-2 text-sm"><input v-model="archived" type="checkbox" />只看已归档</label></form>
    <p v-if="error" class="error-box" role="alert">{{ error }} <Button variant="link" class="h-auto px-0" @click="load()">重试</Button></p>
    <p v-if="loading" class="empty-inline" role="status">加载记录中…</p>
    <p v-else-if="props.compact && !items.length && !error" class="empty-inline">{{ archived ? '没有已归档记录' : '还没有记录，写下一句话就可以开始。' }}</p>
    <div v-else-if="!items.length && !error" class="empty-state">
      <template v-if="query">
        <Search :size="26" /><h2>没有找到匹配的记录</h2>
        <p>没有与「{{ query }}」匹配的记录，当前{{ archived ? '只看已归档' : '不含已归档' }}。</p>
        <Button variant="outline" @click="resetFilters">清空搜索</Button>
      </template>
      <template v-else-if="archived">
        <Archive :size="26" /><h2>没有已归档记录</h2>
        <p>点记录下方的「归档」后，记录会移到这里单独保存。</p>
      </template>
      <template v-else>
        <NotebookPen :size="28" /><h2>写下第一条随手记</h2>
        <p>例如「周五 10 点前发周报，附上进度截图」。在上方输入框写一句话，点「保存」即可。</p>
        <Button @click="focusComposer">去写第一条</Button>
      </template>
    </div>
    <article v-for="item in (props.compact ? items.slice(0, 5) : items)" :key="item.id" class="capture-item">
      <div class="mb-2 flex justify-between text-xs text-muted-foreground"><time>{{ new Date(item.created_at).toLocaleString('zh-CN') }}</time><span v-if="item.pinned" class="text-cyan">已置顶</span></div>
      <p :class="['whitespace-pre-wrap break-words text-sm leading-7', compact && 'line-clamp-4']">{{ item.content }}</p>
      <div class="mt-3 flex flex-wrap gap-1 text-xs text-muted-foreground"><Button :disabled="!!busy" @click="update(item, { pinned: !item.pinned })" variant="ghost" size="sm">{{ item.pinned ? '取消置顶' : '置顶关注' }}</Button><Button @click="discuss(item)" variant="ghost" size="sm">交给 Pulse</Button><Button :disabled="!!busy" @click="update(item, { archived: !item.archived })" variant="ghost" size="sm">{{ item.archived ? '恢复记录' : '归档' }}</Button></div>
    </article>
    <Button v-if="!compact && more" :disabled="loading" @click="load(true)" class="mt-4" variant="outline">加载更多</Button>
  </section>
</template>
