<script setup lang="ts">
import { useProgressStore } from '../store'
import { isBlocked, latestEntry, priorityMap, statusMap, type Task, type TaskStatus } from '../types'

defineProps<{ tasks: Task[] }>()
const store = useProgressStore()
const columns: TaskStatus[] = ['todo', 'in_progress', 'done', 'cancelled']
</script>

<template>
  <div class="task-board">
    <section v-for="column in columns" :key="column" :class="['board-column', `board-column--${column}`]">
      <header class="flex items-center justify-between"><h2>{{ statusMap[column] }}</h2><span class="count-badge">{{ tasks.filter(t => t.status === column).length }}</span></header>
      <div class="mt-3 space-y-2">
        <p v-if="!tasks.some(task => task.status === column)" class="empty-inline">暂无任务</p>
        <button v-for="task in tasks.filter(t => t.status === column)" :key="task.id" class="board-card" @click="store.openTask(task)">
          <div class="flex justify-between"><span :class="['priority', `priority--${task.priority}`]">{{ priorityMap[task.priority] }}</span><span class="font-mono text-[12px] text-muted">{{ task.id.slice(0, 8) }}</span></div>
          <h3>{{ task.title }}</h3>
          <p>{{ isBlocked(task) ? `阻塞 · ${latestEntry(task)?.content}` : (latestEntry(task)?.content || task.tags.join(' / ') || '无标签') }}</p>
          <div class="mt-4 flex items-center gap-2"><span class="avatar avatar--sm">{{ store.memberMap.get(task.assignee_id ?? '')?.name.slice(0, 2) ?? '--' }}</span><div class="progress-line flex-1"><i :style="{ width: `${task.progress}%` }" /></div><span class="font-mono text-[12px] text-muted">{{ task.progress }}%</span><span v-if="task.resources.length" class="font-mono text-[12px] text-muted">{{ task.resources.length }}</span></div>
        </button>
      </div>
    </section>
  </div>
</template>
