<script setup lang="ts">
import { computed } from 'vue'
import { ChevronRight } from '@lucide/vue'
import ChipSelect from '../../../shared/ChipSelect.vue'
import type { AppSelectOption } from '../../../shared/AppSelect.vue'
import { useProgressStore } from '../store'
import { TASK_FILTER_NONE } from '../task-filters'
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

const statusFilter = defineModel<'' | TaskStatus>('statusFilter', { default: '' })
const priorityFilter = defineModel<'' | Priority>('priorityFilter', { default: '' })
const assigneeFilter = defineModel<string>('assigneeFilter', { default: '' })
const projectFilter = defineModel<string>('projectFilter', { default: '' })

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

const statusFilterOptions = computed<AppSelectOption[]>(() => [
  { value: '', label: '全部状态' },
  ...statusOptions,
])
const priorityFilterOptions = computed<AppSelectOption[]>(() => [
  { value: '', label: '全部优先级' },
  ...priorityOptions,
])
const assigneeFilterOptions = computed<AppSelectOption[]>(() => [
  { value: '', label: '全部负责人' },
  { value: TASK_FILTER_NONE, label: '未分配' },
  ...store.assignableMembers.map(member => ({
    value: member.id,
    label: member.operator ? `${member.name}（我）` : member.name,
  })),
])
const projectFilterOptions = computed<AppSelectOption[]>(() => [
  { value: '', label: '全部项目' },
  { value: TASK_FILTER_NONE, label: '无项目' },
  ...store.projects.map(project => ({ value: project.id, label: project.name })),
])

const filterTriggerClass = 'border-dashed bg-transparent font-normal text-muted-foreground hover:text-foreground'

function taskHint(task: Task) {
  const entry = latestEntry(task)
  const extra = task.resources.length ? ` · ${task.resources.length} 个资源` : ''
  if (isBlocked(task) && entry) return `阻塞 · ${entry.content}${extra}`
  if (entry) return `${entryKindMap[entry.kind]} · ${entry.content}${extra}`
  return `${task.id.slice(0, 8)} · ${task.tags.join(' / ') || '无标签'}${extra}`
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
      <thead>
        <tr>
          <th>
            <div class="task-th">
              <span>任务</span>
              <div class="task-th__filters" @click.stop>
                <ChipSelect
                  v-model="projectFilter"
                  :options="projectFilterOptions"
                  :trigger-class="filterTriggerClass"
                  aria-label="按项目筛选"
                />
                <ChipSelect
                  v-model="priorityFilter"
                  :options="priorityFilterOptions"
                  :trigger-class="filterTriggerClass"
                  aria-label="按优先级筛选"
                />
              </div>
            </div>
          </th>
          <th>
            <div class="task-th">
              <span>状态</span>
              <div class="task-th__filters" @click.stop>
                <ChipSelect
                  v-model="statusFilter"
                  :options="statusFilterOptions"
                  :trigger-class="filterTriggerClass"
                  aria-label="按状态筛选"
                />
              </div>
            </div>
          </th>
          <th>
            <div class="task-th">
              <span>负责人</span>
              <div class="task-th__filters" @click.stop>
                <ChipSelect
                  v-model="assigneeFilter"
                  :options="assigneeFilterOptions"
                  :trigger-class="filterTriggerClass"
                  aria-label="按负责人筛选"
                />
              </div>
            </div>
          </th>
          <th>时间窗口</th>
          <th>进度</th>
          <th><span class="sr-only">操作</span></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="task in tasks" :key="task.id" tabindex="0" @click="store.openTask(task)" @keydown.enter="store.openTask(task)">
          <td>
            <div class="flex items-center gap-3">
              <div @click.stop>
                <ChipSelect
                  :model-value="task.priority"
                  :options="priorityOptions"
                  :disabled="store.saving"
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
              :aria-label="`修改状态：${isBlocked(task) ? '阻塞' : statusMap[task.status]}`"
              @update:model-value="status => onStatusChange(task, status)"
            />
          </td>
          <td @click.stop>
            <ChipSelect
              :model-value="task.assignee_id ?? ''"
              :options="assigneeOptionsFor(task)"
              :disabled="store.saving"
              :aria-label="`修改负责人：${store.memberMap.get(task.assignee_id ?? '')?.name ?? '未分配'}`"
              @update:model-value="assigneeId => onAssigneeChange(task, assigneeId)"
            />
          </td>
          <td class="font-mono text-[12px] text-muted-foreground">{{ task.start_date?.slice(0, 10) ?? '—' }} → {{ task.due_date?.slice(0, 10) ?? '—' }}</td>
          <td><div class="w-28"><div class="progress-line"><i :style="{ width: `${task.progress}%` }" /></div><small class="font-mono">{{ task.progress }}%</small></div></td>
          <td><ChevronRight :size="15" class="text-muted-foreground" /></td>
        </tr>
      </tbody>
    </table>
    <p v-if="!tasks.length" class="p-10 text-center text-sm text-muted-foreground">没有匹配任务，尝试调整表头筛选或搜索。</p>
  </div>
</template>
