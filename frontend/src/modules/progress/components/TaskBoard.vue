<script setup lang="ts">
import ChipSelect from '../../../shared/ChipSelect.vue'
import type { AppSelectOption } from '../../../shared/AppSelect.vue'
import { useProgressStore } from '../store'
import { isBlocked, latestEntry, priorityMap, statusMap, type Priority, type Task, type TaskStatus } from '../types'

defineProps<{ tasks: Task[] }>()
const store = useProgressStore()
const columns: TaskStatus[] = ['todo', 'in_progress', 'done', 'cancelled']

const statusOptions: AppSelectOption<TaskStatus>[] = Object.entries(statusMap).map(([value, label]) => ({
  value: value as TaskStatus,
  label,
}))
const priorityOptions: AppSelectOption<Priority>[] = Object.entries(priorityMap).map(([value, label]) => ({
  value: value as Priority,
  label,
}))

function statusLabel(task: Task, display: string, open = false) {
  return !open && isBlocked(task) ? '阻塞' : display
}

async function onStatusChange(task: Task, status: TaskStatus | null) {
  if (!status || status === task.status) return
  await store.patchTask(task.id, { status })
}

async function onPriorityChange(task: Task, priority: Priority | null) {
  if (!priority || priority === task.priority) return
  await store.patchTask(task.id, { priority })
}
</script>

<template>
  <div class="task-board">
    <section v-for="column in columns" :key="column" :class="['board-column', `board-column--${column}`]">
      <header class="flex items-center justify-between"><h2>{{ statusMap[column] }}</h2><span class="count-badge">{{ tasks.filter(t => t.status === column).length }}</span></header>
      <div class="mt-3 space-y-2">
        <p v-if="!tasks.some(task => task.status === column)" class="empty-inline">暂无任务</p>
        <article
          v-for="task in tasks.filter(task => task.status === column)"
          :key="task.id"
          class="board-card"
          role="button"
          tabindex="0"
          @click="store.openTask(task)"
          @keydown.enter="store.openTask(task)"
        >
          <div class="flex justify-between gap-2">
            <div @click.stop>
              <ChipSelect
                :model-value="task.priority"
                :options="priorityOptions"
                :disabled="store.saving"
                :trigger-class="['priority', 'priority--interactive', `priority--${task.priority}`]"
                :aria-label="`修改优先级：${priorityMap[task.priority]}`"
                @update:model-value="priority => onPriorityChange(task, priority)"
              />
            </div>
            <div @click.stop>
              <ChipSelect
                :model-value="task.status"
                :options="statusOptions"
                :disabled="task.status === 'cancelled' || store.saving"
                :trigger-class="[
                  'status-chip',
                  'status-chip--interactive',
                  `status-chip--${isBlocked(task) ? 'blocked' : task.status}`,
                ]"
                :aria-label="`修改状态：${statusLabel(task, statusMap[task.status])}`"
                @update:model-value="status => onStatusChange(task, status)"
              >
                <template #default="{ display, open }">{{ statusLabel(task, display, open) }}</template>
              </ChipSelect>
            </div>
          </div>
          <h3>{{ task.title }}</h3>
          <p>{{ isBlocked(task) ? `阻塞 · ${latestEntry(task)?.content}` : (latestEntry(task)?.content || task.tags.join(' / ') || '无标签') }}</p>
          <div class="mt-4 flex items-center gap-2"><span class="avatar avatar--sm">{{ store.memberMap.get(task.assignee_id ?? '')?.name.slice(0, 2) ?? '--' }}</span><div class="progress-line flex-1"><i :style="{ width: `${task.progress}%` }" /></div><span class="font-mono text-[12px] text-muted">{{ task.progress }}%</span><span v-if="task.resources.length" class="font-mono text-[12px] text-muted">{{ task.resources.length }}</span></div>
        </article>
      </div>
    </section>
  </div>
</template>
