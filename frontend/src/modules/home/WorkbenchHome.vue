<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ArrowUpRight, RefreshCw } from '@lucide/vue'
import { homeModules, modules } from '../../app/modules'
import type { WorkbenchItem } from '../../app/module-types'
import CaptureComposer from '../capture/CaptureComposer.vue'
import CaptureList from '../capture/CaptureList.vue'
import { apiError } from '../../shared/api/client'

const sources = modules.filter(module => module.workbench)
const selected = ref(sources.map(module => module.id))
const items = ref<(WorkbenchItem & { moduleId: string; moduleTitle: string })[]>([])
const errors = ref<string[]>([])
const loading = ref(false)
const visible = computed(() => items.value.filter(item => selected.value.includes(item.moduleId)))
const attention = computed(() => visible.value.filter(item => item.kind === 'attention'))
const activity = computed(() => visible.value.filter(item => item.kind === 'activity').sort((a, b) => b.occurredAt.localeCompare(a.occurredAt)).slice(0, 12))
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
}
onMounted(() => { void refresh(); window.addEventListener('workbench-changed', refresh) })
onUnmounted(() => window.removeEventListener('workbench-changed', refresh))
</script>

<template>
  <div class="page-wrap workbench-home">
    <header class="page-header"><div><p class="eyebrow">Your workspace</p><h1>我的工作台</h1><p>记下想法，关注变化，从这里继续推进。</p></div><button class="btn-secondary" :disabled="loading" @click="refresh"><RefreshCw :size="15" />{{ loading ? '刷新中…' : '刷新动态' }}</button></header>
    <section class="card capture-hero"><CaptureComposer /></section>
    <div class="workbench-columns mt-5">
      <div class="min-w-0 space-y-5">
        <section class="card"><div class="card-head"><div><p class="eyebrow">Attention</p><h2>待处理 <span class="text-muted">{{ attention.length }}</span></h2></div></div><p class="mt-2 text-xs text-muted">来自已选模块的待处理事项，点击回到来源继续操作。</p>
          <p v-for="error in errors" :key="error" class="error-box mt-3" role="alert">{{ error }}</p>
          <p v-if="loading" class="empty-inline">正在读取各模块…</p>
          <p v-else-if="!attention.length" class="empty-inline">{{ errors.length ? '部分模块暂不可用，请刷新重试。' : '已选模块中暂无待处理事项。' }}</p>
          <RouterLink v-for="item in attention" :key="`${item.moduleId}:${item.id}`" :to="item.to" class="workbench-feed"><span class="feed-mark feed-mark--attention" /><div class="min-w-0 flex-1"><p class="break-words text-sm">{{ item.title }}</p><p class="mt-1 text-xs text-muted">{{ item.moduleTitle }} · {{ item.summary }}</p></div><ArrowUpRight :size="14" /></RouterLink>
        </section>
        <section class="card"><div class="card-head"><div><p class="eyebrow">Activity</p><h2>最近动态</h2></div></div>
          <div class="my-4 flex flex-wrap gap-4"><label v-for="source in sources" :key="source.id" class="flex items-center gap-2 text-xs text-muted"><input v-model="selected" type="checkbox" :value="source.id" />{{ source.title }}</label></div>
          <p v-if="!loading && !activity.length" class="empty-inline">{{ selected.length ? '暂无可展示的动态。' : '选择一个模块查看动态与待处理事项。' }}</p>
          <RouterLink v-for="item in activity" :key="`${item.moduleId}:${item.id}`" :to="item.to" class="workbench-feed"><span class="feed-mark" /><div class="min-w-0 flex-1"><p class="break-words text-sm">{{ item.title }}</p><p class="mt-1 text-xs text-muted">{{ item.moduleTitle }} · {{ item.summary }}</p></div><time class="shrink-0 text-xs text-muted">{{ item.occurredAt ? new Date(item.occurredAt).toLocaleDateString('zh-CN') : '' }}</time></RouterLink>
        </section>
      </div>
      <div class="min-w-0 space-y-5">
        <section class="card"><div class="card-head"><div><p class="eyebrow">Capture</p><h2>关注与最近记录</h2></div><RouterLink to="/captures" class="text-xs text-cyan">全部记录 →</RouterLink></div><CaptureList compact /></section>
        <section class="card"><div class="card-head"><h2>工作模块</h2></div><RouterLink v-for="module in homeModules" :key="module.id" :to="module.homeCard ? module.homeCard.to : '/'" class="workbench-feed"><component :is="module.icon" :size="20" class="shrink-0 text-cyan" /><div><p class="text-sm">{{ module.title }}</p><p class="mt-1 text-xs leading-5 text-muted">{{ module.description }}</p></div><ArrowUpRight :size="14" class="ml-auto shrink-0" /></RouterLink></section>
      </div>
    </div>
  </div>
</template>
