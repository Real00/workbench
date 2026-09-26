<script setup lang="ts">
import { computed } from 'vue'
import { ChevronRight } from '@lucide/vue'
import ChipSelect from '../../../shared/ChipSelect.vue'
import type { AppSelectOption } from '../../../shared/AppSelect.vue'
import { useProgressStore } from '../store'
import {
  entryKindMap,
  isBlocked,
  latestEntry,
  priorityMap,
  statusMap,
  type Priority,
  type Task,
  type TaskStatus,
} from '../types'

defineProps<{ tasks: Task[] }>()
const store = useProgressStore()

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

function taskHint(task: Task) {
  const entry = latestEntry(task)
  const extra = task.resources.length ? ` · ${task.resources.length} 个资源` : ''
  if (isBlocked(task) && entry) return `阻塞 · ${entry.content}${extra}`
  if (entry) return `${entryKindMap[entry.kind]} · ${entry.content}${extra}`
  return `${task.id.slice(0, 8)} · ${task.tags.join(' / ') || '无标签'}${extra}`
}

function statusLabel(task: Task, display: string, open = false) {
  return !open && isBlocked(task) ? '阻塞' : display
}

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
  <div class="task-table overflow-x-auto rounded-xl border border-line bg-panel">
    <table class="data-table">
      <thead><tr><th>任务</th><th>状态</th><th>负责人</th><th>时间窗口</th><th>进度</th><th><span class="sr-only">操作</span></th></tr></thead>
      <tbody>
        <tr v-for="task in tasks" :key="task.id" tabindex="0" @click="store.openTask(task)" @keydown.enter="store.openTask(task)">
          <td>
            <div class="flex items-center gap-3">
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
              <div>
                <b>{{ task.title }}<span v-if="task.project_id" class="ml-2 font-mono text-[12px] font-normal text-cyan">{{ store.projects.find(project => project.id === task.project_id)?.name ?? '' }}</span></b>
                <small>{{ taskHint(task) }}</small>
              </div>
            </div>
          </td>
          <td @click.stop>
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
          </td>
          <td @click.stop>
            <ChipSelect
              :model-value="task.assignee_id ?? ''"
              :options="assigneeOptionsFor(task)"
              :disabled="store.saving"
              trigger-class="assignee-chip"
              :aria-label="`修改负责人：${store.memberMap.get(task.assignee_id ?? '')?.name ?? '未分配'}`"
              @update:model-value="assigneeId => onAssigneeChange(task, assigneeId)"
            >
              <template #default="{ display }">
                <span class="avatar avatar--sm">{{ store.memberMap.get(task.assignee_id ?? '')?.name.slice(0, 2) ?? '--' }}</span>
                <span class="assignee-chip__name">{{ display }}</span>
              </template>
            </ChipSelect>
          </td>
          <td class="font-mono text-[12px] text-muted-foreground">{{ task.start_date?.slice(0, 10) ?? '—' }} → {{ task.due_date?.slice(0, 10) ?? '—' }}</td>
          <td><div class="w-28"><div class="progress-line"><i :style="{ width: `${task.progress}%` }" /></div><small class="font-mono">{{ task.progress }}%</small></div></td>
          <td><ChevronRight :size="15" class="text-muted-foreground" /></td>
        </tr>
      </tbody>
    </table>
    <p v-if="!tasks.length" class="p-10 text-center text-sm text-muted-foreground">没有匹配任务，尝试其他关键词。</p>
  </div>
</template>
