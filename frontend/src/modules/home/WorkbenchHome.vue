<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ArrowUpRight, CircleAlert, Clock3, Layers, NotebookPen, RefreshCw } from '@lucide/vue'
import { homeModules, modules } from '../../app/modules'
import type { WorkbenchItem } from '../../app/module-types'
import CaptureComposer from '../capture/CaptureComposer.vue'
import CaptureList from '../capture/CaptureList.vue'
import { apiError } from '../../shared/api/client'
import { Button } from '@/components/ui/button'

const sources = modules.filter(module => module.workbench)
const selected = ref(sources.map(module => module.id))
const items = ref<(WorkbenchItem & { moduleId: string; moduleTitle: string })[]>([])
const errors = ref<string[]>([])
const loading = ref(false)
const visible = computed(() => items.value.filter(item => selected.value.includes(item.moduleId)))
const attention = computed(() => visible.value.filter(item => item.kind === 'attention'))
// 动态按时间排序，但每个来源最多占 ACTIVITY_PER_SOURCE 条，避免订阅刷新淹没任务与知识变动
const ACTIVITY_PER_SOURCE = 3
const refreshedAt = ref('')
const activity = computed(() => {
  const counts = new Map<string, number>()
  const picked: typeof items.value = []
  for (const item of visible.value.filter(item => item.kind === 'activity').sort((a, b) => b.occurredAt.localeCompare(a.occurredAt))) {
    const count = counts.get(item.moduleId) ?? 0
    if (count >= ACTIVITY_PER_SOURCE) continue
    counts.set(item.moduleId, count + 1)
    picked.push(item)
    if (picked.length >= 12) break
  }
  return picked
})
function formatDay(value: string) { return value ? new Date(value).toLocaleDateString('zh-CN') : '' }
async function refresh() {
  if (loading.value) return
  loading.value = true
  const results = await Promise.allSettled(sources.map(async module => (await module.workbench!.load()).map(item => ({ ...item, moduleId: module.id, moduleTitle: module.title }))))
  items.value = []; errors.value = []
  results.forEach((result, index) => {
    if (result.status === 'fulfilled') items.value.push(...result.value)
    else errors.value.push(`${sources[index]!.title}：${apiError(result.reason)}`)
  })
  loading.value = false
  refreshedAt.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}
onMounted(() => { void refresh(); window.addEventListener('workbench-changed', refresh) })
onUnmounted(() => window.removeEventListener('workbench-changed', refresh))
</script>

<template>
  <div class="page-wrap workbench-home">
    <header class="page-header"><div><p class="eyebrow">Your workspace</p><h1>工作台首页</h1><p>记下想法，关注变化，从这里继续推进。</p></div><Button :disabled="loading" @click="refresh" variant="outline"><RefreshCw :size="15" />{{ loading ? '刷新中…' : '刷新动态' }}</Button></header>
    <section class="card capture-hero"><CaptureComposer /></section>
    <div class="workbench-filter" role="group" aria-label="待处理与动态来源"><span>关注来源</span><label v-for="source in sources" :key="source.id"><input v-model="selected" type="checkbox" :value="source.id" />{{ source.title }}</label></div>
    <div class="workbench-columns">
      <div class="min-w-0 space-y-5">
        <section class="card home-attention"><div class="card-head"><div><h2><span class="section-icon section-icon--amber"><CircleAlert :size="17" /></span>待处理 <span class="text-muted-foreground">{{ attention.length }}</span></h2></div></div>
          <p v-for="error in errors" :key="error" class="error-box mt-3" role="alert">{{ error }}</p>
          <p v-if="loading" class="empty-inline">正在读取各模块…</p>
          <p v-else-if="!attention.length && errors.length" class="py-1 text-xs text-muted-foreground">部分模块暂不可用，请刷新重试。</p>
          <p v-else-if="!attention.length" class="py-1 text-xs text-muted-foreground">已选模块中暂无待处理事项，<RouterLink to="/progress/tasks" class="text-cyan">去进度管理查看任务 →</RouterLink></p>
          <p v-else class="mt-2 text-xs text-muted-foreground">来自已选模块的待处理事项，点击回到来源继续操作。</p>
          <RouterLink v-for="item in attention" :key="`${item.moduleId}:${item.id}`" :to="item.to" class="workbench-feed"><span class="feed-mark feed-mark--attention" /><div class="min-w-0 flex-1"><p class="break-words text-sm">{{ item.title }}</p><p class="mt-1 text-xs text-muted-foreground">{{ item.moduleTitle }} · {{ item.summary }}</p></div><ArrowUpRight :size="14" /></RouterLink>
        </section>
        <section class="card"><div class="card-head"><div><h2><span class="section-icon"><Clock3 :size="17" /></span>最近动态</h2></div><span class="shrink-0 text-xs text-muted-foreground">每来源最多 {{ ACTIVITY_PER_SOURCE }} 条<template v-if="refreshedAt"> · 更新于 {{ refreshedAt }}</template></span></div>
          <p v-if="!loading && !activity.length" class="empty-inline">{{ selected.length ? '暂无可展示的动态。' : '选择一个模块查看动态与待处理事项。' }}</p>
          <RouterLink v-for="item in activity" :key="`${item.moduleId}:${item.id}`" :to="item.to" class="workbench-feed"><span class="feed-mark" /><div class="min-w-0 flex-1"><p class="line-clamp-2 break-words text-sm">{{ item.title }}</p><p class="mt-1 truncate text-xs text-muted-foreground"><time v-if="item.occurredAt" :datetime="item.occurredAt">{{ formatDay(item.occurredAt) }}</time>{{ item.occurredAt ? ' · ' : '' }}{{ item.moduleTitle }} · {{ item.summary }}</p></div></RouterLink>
        </section>
      </div>
      <div class="min-w-0 space-y-5">
        <section class="card"><div class="card-head"><div><h2><span class="section-icon"><NotebookPen :size="17" /></span>关注与最近记录</h2></div><RouterLink to="/captures" class="text-xs text-cyan">全部记录 →</RouterLink></div><CaptureList compact /></section>
        <section class="card"><div class="card-head"><h2><span class="section-icon"><Layers :size="17" /></span>工作模块</h2></div><RouterLink v-for="module in homeModules" :key="module.id" :to="module.homeCard ? module.homeCard.to : '/'" class="workbench-feed"><component :is="module.icon" :size="20" class="shrink-0 text-cyan" /><div><p class="text-sm">{{ module.title }}</p><p class="mt-1 text-xs leading-5 text-muted-foreground">{{ module.description }}</p></div><ArrowUpRight :size="14" class="ml-auto shrink-0" /></RouterLink></section>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* A07：快记保留输入与快捷键，但压缩为轻量入口，让最近动态在手机首屏可见 */
.workbench-home .capture-hero { padding: 12px 16px; }
.capture-hero :deep([data-slot='textarea']) { min-height: 4rem; margin-top: .5rem; }
</style>
