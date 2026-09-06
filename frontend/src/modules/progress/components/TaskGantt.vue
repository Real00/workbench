<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import Gantt from 'frappe-gantt'
import { useProgressStore } from '../store'

import type { Task } from '../types'

const props = defineProps<{ tasks: Task[] }>()
const datedTasks = computed(() => props.tasks.filter(task => task.start_date && task.due_date))
const store = useProgressStore()
const chart = ref<HTMLElement>()

watch(datedTasks, async () => {
  await nextTick()
  if (!chart.value) return
  const dated = datedTasks.value
  chart.value.innerHTML = ''
  if (!dated.length) return
  new Gantt(chart.value, dated.map((task) => ({
    id: task.id,
    name: `${task.title} · ${store.memberMap.get(task.assignee_id ?? '')?.name ?? '未分配'}`,
    start: task.start_date!.slice(0, 10),
    end: task.due_date!.slice(0, 10),
    progress: task.progress,
    dependencies: '',
  })), {
    view_mode: 'Day',
    language: 'zh',
    readonly: true,
    scroll_to: 'start',
    today_button: false,
    popup: false,
    bar_height: 36,
    on_click: (item: { id: string }) => store.openTask(store.tasks.find((task) => task.id === item.id)),
  })
}, { immediate: true, deep: true })
</script>

<template>
  <div class="gantt-shell overflow-x-auto rounded-xl border border-line bg-panel p-4">
    <p v-if="datedTasks.length" class="mb-4 text-xs text-muted">{{ datedTasks.length }} 个已排期任务<span v-if="tasks.length > datedTasks.length"> · {{ tasks.length - datedTasks.length }} 个任务尚未设置完整日期</span></p>
    <div ref="chart" class="min-w-0" aria-label="任务甘特图" />
    <p v-if="!datedTasks.length" class="empty-inline">暂无同时设置开始与截止日期的任务</p>
  </div>
</template>
