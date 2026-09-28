<script setup lang="ts">
import { computed } from 'vue'
import ChipSelect from '../../../shared/ChipSelect.vue'
import type { AppSelectOption } from '../../../shared/AppSelect.vue'
import { Badge } from '@/components/ui/badge'
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
const assigneeOptions = computed<AppSelectOption[]>(() => [
  { value: '', label: '未分配' },
  ...store.assignableMembers.map(member => ({
    value: member.id,
    label: member.operator ? `${member.name}（我）` : member.name,
  })),
])

function assigneeOptionsFor(task: Task): AppSelectOption[] {
  const options = assigneeOptions.value
  if (!task.assignee_id || options.some(option => option.value === task.assignee_id)) return options
  const member = store.memberMap.get(task.assignee_id)
  if (!member) return options
  return [
    options[0]!,
    { value: member.id, label: `${member.name}（不可分配）` },
    ...options.slice(1),
  ]
}

async function onStatusChange(task: Task, status: TaskStatus | null | undefined) {
  if (!status || status === task.status) return
  await store.patchTask(task.id, { status })
}

async function onPriorityChange(task: Task, priority: Priority | null | undefined) {
  if (!priority || priority === task.priority) return
  await store.patchTask(task.id, { priority })
}

async function onAssigneeChange(task: Task, assigneeId: string | null | undefined) {
  const next = assigneeId || null
  if (next === task.assignee_id) return
  await store.patchTask(task.id, { assignee_id: next })
}
</script>

<template>
  <div class="task-board">
    <section v-for="column in columns" :key="column" :class="['board-column', `board-column--${column}`]">
      <header class="flex items-center justify-between"><h2>{{ statusMap[column] }}</h2><Badge variant="secondary">{{ tasks.filter(t => t.status === column).length }}</Badge></header>
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
          <div class="board-card__chips">
            <div class="board-card__chip" @click.stop>
              <ChipSelect
                :model-value="task.priority"
                :options="priorityOptions"
                :disabled="store.saving"
                :aria-label="`修改优先级：${priorityMap[task.priority]}`"
                @update:model-value="priority => onPriorityChange(task, priority)"
              />
            </div>
            <div class="board-card__chip" @click.stop>
              <ChipSelect
                :model-value="task.status"
                :options="statusOptions"
                :disabled="task.status === 'cancelled' || store.saving"
                :aria-label="`修改状态：${isBlocked(task) ? '阻塞' : statusMap[task.status]}`"
                @update:model-value="status => onStatusChange(task, status)"
              />
            </div>
          </div>
          <h3>{{ task.title }}</h3>
          <p>{{ isBlocked(task) ? `阻塞 · ${latestEntry(task)?.content}` : (latestEntry(task)?.content || task.tags.join(' / ') || '无标签') }}</p>
          <div class="board-card__foot">
            <div class="board-card__assignee" @click.stop>
              <ChipSelect
                :model-value="task.assignee_id ?? ''"
                :options="assigneeOptionsFor(task)"
                :disabled="store.saving"
                trigger-class="max-w-full"
                :aria-label="`修改负责人：${store.memberMap.get(task.assignee_id ?? '')?.name ?? '未分配'}`"
                @update:model-value="assigneeId => onAssigneeChange(task, assigneeId)"
              />
            </div>
            <div class="progress-line min-w-0 flex-1"><i :style="{ width: `${task.progress}%` }" /></div>
            <span class="shrink-0 font-mono text-[12px] text-muted-foreground">{{ task.progress }}%</span>
            <span v-if="task.resources.length" class="shrink-0 font-mono text-[12px] text-muted-foreground">{{ task.resources.length }}</span>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>
