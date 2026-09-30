<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useMediaQuery } from '@vueuse/core'
import Gantt from 'frappe-gantt'
import { Maximize2, X } from '@lucide/vue'
import { useProgressStore } from '../store'
import { Button } from '@/components/ui/button'

import type { Task } from '../types'

const props = defineProps<{ tasks: Task[] }>()
const datedTasks = computed(() => props.tasks.filter(task => task.start_date && task.due_date))
const store = useProgressStore()
const chart = ref<HTMLElement>()
const fullscreenChart = ref<HTMLElement>()
const isNarrow = useMediaQuery('(max-width: 768px)')
const fullscreen = ref(false)

const timelineGroups = computed(() => {
  const groups = new Map<string, Task[]>()
  for (const task of datedTasks.value) {
    const key = task.start_date!.slice(0, 10)
    const list = groups.get(key) ?? []
    list.push(task)
    groups.set(key, list)
  }
  return [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, items]) => ({ date, items }))
})

function renderGantt(el: HTMLElement | undefined) {
  if (!el) return
  const dated = datedTasks.value
  el.innerHTML = ''
  if (!dated.length) return
  new Gantt(el, dated.map((task) => ({
    id: task.id,
    name: `${task.title} · ${store.memberMap.get(task.assignee_id ?? '')?.name ?? '未分配'}`,
    start: task.start_date!.slice(0, 10),
    end: task.due_date!.slice(0, 10),
    progress: task.progress,
    dependencies: '',
  })), {
    view_mode: 'Week',
    language: 'zh',
    readonly: true,
    scroll_to: 'start',
    today_button: false,
    popup: false,
    bar_height: 36,
    on_click: (item: { id: string }) => store.openTask(store.tasks.find((task) => task.id === item.id)),
  })
}

watch(datedTasks, async () => {
  await nextTick()
  if (!isNarrow.value) renderGantt(chart.value)
  if (fullscreen.value) renderGantt(fullscreenChart.value)
}, { immediate: true, deep: true })

watch(fullscreen, async (open) => {
  if (!open) return
  await nextTick()
  renderGantt(fullscreenChart.value)
})

watch(isNarrow, async (narrow) => {
  if (narrow) return
  fullscreen.value = false
  await nextTick()
  renderGantt(chart.value)
})
</script>

<template>
  <div class="gantt-shell overflow-x-auto rounded-xl border border-line bg-panel p-4">
    <div class="mb-4 flex flex-wrap items-center justify-between gap-2">
      <p v-if="datedTasks.length" class="text-xs text-muted-foreground">
        {{ datedTasks.length }} 个已排期任务
        <span v-if="tasks.length > datedTasks.length"> · {{ tasks.length - datedTasks.length }} 个任务尚未设置完整日期</span>
      </p>
      <Button v-if="isNarrow && datedTasks.length" type="button" size="sm" variant="outline" @click="fullscreen = true">
        <Maximize2 :size="14" />全屏甘特
      </Button>
    </div>

    <template v-if="isNarrow">
      <div v-if="timelineGroups.length" class="space-y-4">
        <section v-for="group in timelineGroups" :key="group.date">
          <p class="mb-2 font-mono text-xs text-muted-foreground">{{ group.date }}</p>
          <ul class="space-y-2">
            <li v-for="task in group.items" :key="task.id">
              <button
                type="button"
                class="w-full rounded-lg border border-line bg-panel-2 px-3 py-2.5 text-left"
                @click="store.openTask(task)"
              >
                <b class="block text-sm text-text">{{ task.title }}</b>
                <span class="mt-1 block text-[12px] text-muted-foreground">
                  {{ store.memberMap.get(task.assignee_id ?? '')?.name ?? '未分配' }}
                  · {{ task.start_date?.slice(0, 10) }} → {{ task.due_date?.slice(0, 10) }}
                  · {{ task.progress }}%
                </span>
              </button>
            </li>
          </ul>
        </section>
      </div>
      <p v-else class="empty-inline">暂无同时设置开始与截止日期的任务</p>
    </template>
    <template v-else>
      <div ref="chart" class="min-w-0" aria-label="任务甘特图" />
      <p v-if="!datedTasks.length" class="empty-inline">暂无同时设置开始与截止日期的任务</p>
    </template>

    <Teleport to="body">
      <div v-if="fullscreen" class="fixed inset-0 z-50 flex flex-col bg-panel">
        <header class="flex shrink-0 items-center justify-between border-b border-line px-4 py-3">
          <h2 class="font-display text-lg text-text">甘特图</h2>
          <Button aria-label="关闭全屏甘特" variant="ghost" size="icon" @click="fullscreen = false"><X :size="18" /></Button>
        </header>
        <div class="min-h-0 flex-1 overflow-auto p-3">
          <div ref="fullscreenChart" class="min-w-0" aria-label="全屏任务甘特图" />
        </div>
      </div>
    </Teleport>
  </div>
</template>
