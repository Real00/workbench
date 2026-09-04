<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import Gantt from 'frappe-gantt'
import { useProgressStore } from '../store'

const store = useProgressStore()
const chart = ref<HTMLElement>()

watch(() => store.tasks, async () => {
  await nextTick()
  if (!chart.value) return
  const dated = store.tasks.filter(task => task.start_date && task.due_date)
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
    on_click: (item: { id: string }) => store.openTask(store.tasks.find((task) => task.id === item.id)),
  })
}, { immediate: true, deep: true })
</script>

<template>
  <div class="gantt-shell overflow-x-auto rounded-xl border border-line bg-panel p-4">
    <div ref="chart" class="min-w-[900px]" aria-label="任务甘特图" />
    <p v-if="!store.tasks.some(task => task.start_date && task.due_date)" class="empty-inline">暂无同时设置开始与截止日期的任务</p>
  </div>
</template>
