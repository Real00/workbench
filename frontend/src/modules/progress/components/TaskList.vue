<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ArrowUpDown, ChevronRight, CircleAlert, ListFilter, Paperclip, X } from '@lucide/vue'
import ChipSelect from '../../../shared/ChipSelect.vue'
import type { AppSelectOption } from '../../../shared/AppSelect.vue'
import { useProgressStore } from '../store'
import type { TaskListPrefs, TaskSortId } from '../store'
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

const props = defineProps<{ tasks: Task[] }>()
const store = useProgressStore()

const statusFilter = defineModel<'' | TaskStatus>('statusFilter', { default: '' })
const priorityFilter = defineModel<'' | Priority>('priorityFilter', { default: '' })
const assigneeFilter = defineModel<string>('assigneeFilter', { default: '' })
const projectFilter = defineModel<string>('projectFilter', { default: '' })

/** 排序与「仅看逾期」为列表内部状态，与筛选一起持久化（审计 A15） */
const sort = ref<TaskSortId>(store.taskListPrefs.sort)
const overdueOnly = ref(store.taskListPrefs.overdueOnly)

const statusOptions: AppSelectOption<TaskStatus>[] = Object.entries(statusMap).map(([value, label]) => ({
  value: value as TaskStatus,
  label,
}))
const priorityOptions: AppSelectOption<Priority>[] = Object.entries(priorityMap).map(([value, label]) => ({
  value: value as Priority,
  label,
}))
const sortOptions: AppSelectOption<TaskSortId>[] = [
  { value: '', label: '默认顺序' },
  { value: 'due', label: '截止时间 早→晚' },
  { value: 'priority', label: '优先级 高→低' },
  { value: 'progress', label: '进度 高→低' },
  { value: 'updated', label: '最近更新 新→旧' },
]
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

/** 表头筛选与行内编辑做视觉区分（审计 A12）：筛选一律虚线描边，命中条件时填充高亮 */
function filterTriggerClass(active: boolean) {
  return active
    ? 'border-dashed border-[#93b4f5] bg-[#eff6ff] font-normal text-[#1d4ed8]'
    : 'border-dashed bg-transparent font-normal text-muted-foreground hover:text-foreground'
}

/** 状态用色与文字双编码（审计 A12）：色彩只做加强，文字标签始终保留，色弱用户仍可识别 */
const statusChipClass: Record<TaskStatus, string> = {
  todo: 'text-text-secondary',
  in_progress: 'border-[#b2ccf7] bg-[#eff6ff] text-[#1d4ed8]',
  done: 'border-[#b4dfc9] bg-[#edf9f1] text-[#16794b]',
  cancelled: 'bg-[#f2f4f7] text-muted-foreground',
}

function todayISO() {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

/** 与后端 dashboard.overdue 同口径：有截止且早于今天、未完成 */
function isOverdue(task: Task) {
  return Boolean(task.due_date && task.due_date < todayISO() && task.status !== 'done' && task.status !== 'cancelled')
}

const PRIORITY_WEIGHT: Record<Priority, number> = { urgent: 4, high: 3, medium: 2, low: 1 }

/** 排序（审计 A15）：只调整展示顺序，不改变筛选集合；并列时保持原有稳定顺序 */
const displayTasks = computed(() => {
  const base = overdueOnly.value ? props.tasks.filter(task => isOverdue(task)) : props.tasks
  if (!sort.value) return base
  const sorted = [...base]
  if (sort.value === 'due') sorted.sort((left, right) => (left.due_date ?? '9999-12-31').localeCompare(right.due_date ?? '9999-12-31'))
  else if (sort.value === 'priority') sorted.sort((left, right) => PRIORITY_WEIGHT[right.priority] - PRIORITY_WEIGHT[left.priority])
  else if (sort.value === 'progress') sorted.sort((left, right) => right.progress - left.progress)
  else sorted.sort((left, right) => right.updated_at.localeCompare(left.updated_at))
  return sorted
})

const filtering = computed(() =>
  Boolean(statusFilter.value || priorityFilter.value || assigneeFilter.value || projectFilter.value || overdueOnly.value))

function clearFilters() {
  statusFilter.value = ''
  priorityFilter.value = ''
  assigneeFilter.value = ''
  projectFilter.value = ''
  overdueOnly.value = false
}

/** 恢复上次会话（或进度总览下钻）约定的筛选 / 排序；TaskViewsPage 的筛选经 v-model 同步 */
onMounted(() => {
  const prefs = store.taskListPrefs
  if (statusFilter.value !== prefs.status) statusFilter.value = prefs.status
  if (priorityFilter.value !== prefs.priority) priorityFilter.value = prefs.priority
  if (assigneeFilter.value !== prefs.assignee) assigneeFilter.value = prefs.assignee
  if (projectFilter.value !== prefs.project) projectFilter.value = prefs.project
  sort.value = prefs.sort
  overdueOnly.value = prefs.overdueOnly
})

watch([statusFilter, priorityFilter, assigneeFilter, projectFilter, sort, overdueOnly], () => {
  const prefs: TaskListPrefs = {
    status: statusFilter.value,
    priority: priorityFilter.value,
    assignee: assigneeFilter.value,
    project: projectFilter.value,
    sort: sort.value,
    overdueOnly: overdueOnly.value,
  }
  store.setTaskListPrefs(prefs)
})

/** 行内次要信息分层（审计 A13）：最新说明单独一行并限高，标签与资源数量归入元信息，短 ID 移到行提示 */
function taskMeta(task: Task) {
  const entry = latestEntry(task)
  return {
    entryLine: entry ? `${isBlocked(task) ? '阻塞' : entryKindMap[entry.kind]} · ${entry.content}` : '',
    tags: task.tags.join(' / ') || '无标签',
    resourceCount: task.resources.length,
  }
}

/** 行级键盘激活只响应行自身获得焦点的情况，避免行内下拉触发器的按键冒泡误开详情 */
function onRowKeydown(event: KeyboardEvent, task: Task) {
  if (event.target !== event.currentTarget) return
  event.preventDefault()
  store.openTask(task)
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
  <div class="task-list">
    <!-- 独立筛选工具栏 + 命中数（审计 A12 / A15）：与行内编辑胶囊区分 -->
    <div class="task-filterbar mb-3 flex flex-wrap items-center gap-x-2 gap-y-1.5 rounded-xl border border-line bg-panel px-3 py-2">
      <span class="task-filter flex items-center gap-1 text-[11px] font-medium text-muted-foreground"><ListFilter :size="13" aria-hidden="true" />筛选</span>
      <ChipSelect v-model="projectFilter" :options="projectFilterOptions" :trigger-class="filterTriggerClass(projectFilter !== '')" aria-label="按项目筛选" />
      <ChipSelect v-model="priorityFilter" :options="priorityFilterOptions" :trigger-class="filterTriggerClass(priorityFilter !== '')" aria-label="按优先级筛选" />
      <ChipSelect v-model="statusFilter" :options="statusFilterOptions" :trigger-class="filterTriggerClass(statusFilter !== '')" aria-label="按状态筛选" />
      <ChipSelect v-model="assigneeFilter" :options="assigneeFilterOptions" :trigger-class="filterTriggerClass(assigneeFilter !== '')" aria-label="按负责人筛选" />
      <button
        type="button"
        :class="['inline-flex h-7 items-center gap-1 whitespace-nowrap rounded-lg border px-2 text-xs transition-colors',
                 overdueOnly ? 'border-[#f0b6b0] bg-[#fff5f4] font-normal text-[#b42318]' : 'border-dashed bg-transparent font-normal text-muted-foreground hover:text-foreground']"
        :aria-pressed="overdueOnly"
        aria-label="仅看逾期任务"
        @click="overdueOnly = !overdueOnly"
      >
        <CircleAlert :size="13" aria-hidden="true" />仅看逾期
      </button>
      <span class="task-filter flex items-center gap-1 text-muted-foreground">
        <ArrowUpDown :size="13" aria-hidden="true" />
        <ChipSelect v-model="sort" :options="sortOptions" trigger-class="border-dashed bg-transparent font-normal text-muted-foreground hover:text-foreground" aria-label="排序方式" />
      </span>
      <button v-if="filtering" type="button" class="btn-ghost btn-ghost--sm" @click="clearFilters"><X :size="13" />清除筛选</button>
      <span class="ml-auto flex-none font-mono text-[11px] text-muted-foreground">命中 {{ displayTasks.length }} / 共 {{ store.tasks.length }} 个任务</span>
    </div>
    <!-- 桌面：完整表格（审计 A12 / A13 / A15） -->
    <div v-if="displayTasks.length" class="task-table hidden overflow-x-auto rounded-xl border border-line bg-panel lg:block">
      <table class="data-table">
        <thead>
          <tr>
            <th>任务</th>
            <th>状态</th>
            <th>负责人</th>
            <th>时间窗口</th>
            <th>进度</th>
            <th><span class="sr-only">操作</span></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="task in displayTasks"
            :key="task.id"
            tabindex="0"
            :aria-label="`打开任务详情：${task.title}`"
            :title="`${task.title} · ID ${task.id.slice(0, 8)}`"
            @click="store.openTask(task)"
            @keydown.enter="onRowKeydown($event, task)"
            @keydown.space="onRowKeydown($event, task)"
          >
            <td>
              <div class="flex items-center gap-3">
                <span class="task-edit inline-flex flex-none" :title="`修改优先级（当前：${priorityMap[task.priority]}）`" @click.stop>
                  <ChipSelect
                    :model-value="task.priority"
                    :options="priorityOptions"
                    :disabled="store.saving"
                    :aria-label="`修改优先级：${priorityMap[task.priority]}`"
                    @update:model-value="priority => onPriorityChange(task, priority)"
                  />
                </span>
                <div class="min-w-0">
                  <b>{{ task.title }}<span v-if="task.project_id" class="ml-2 font-mono text-[12px] font-normal text-cyan">{{ store.projects.find(project => project.id === task.project_id)?.name ?? '' }}</span></b>
                  <small class="task-hint">
                    <span v-if="taskMeta(task).entryLine" class="task-hint__entry">{{ taskMeta(task).entryLine }}</span>
                    <span class="task-hint__meta">
                      <span>{{ taskMeta(task).tags }}</span>
                      <span v-if="taskMeta(task).resourceCount" class="inline-flex items-center gap-1"><Paperclip :size="11" aria-hidden="true" />{{ taskMeta(task).resourceCount }} 个资源</span>
                    </span>
                  </small>
                </div>
              </div>
            </td>
            <td @click.stop>
              <span class="task-edit inline-flex" :title="`修改状态（当前：${isBlocked(task) ? '阻塞' : statusMap[task.status]}）`">
                <ChipSelect
                  :model-value="task.status"
                  :options="statusOptions"
                  :trigger-class="statusChipClass[task.status]"
                  :disabled="task.status === 'cancelled' || store.saving"
                  :aria-label="`修改状态：${isBlocked(task) ? '阻塞' : statusMap[task.status]}`"
                  @update:model-value="status => onStatusChange(task, status)"
                />
              </span>
            </td>
            <td @click.stop>
              <span class="task-edit inline-flex" :title="`修改负责人（当前：${store.memberMap.get(task.assignee_id ?? '')?.name ?? '未分配'}）`">
                <ChipSelect
                  :model-value="task.assignee_id ?? ''"
                  :options="assigneeOptionsFor(task)"
                  :disabled="store.saving"
                  :aria-label="`修改负责人：${store.memberMap.get(task.assignee_id ?? '')?.name ?? '未分配'}`"
                  @update:model-value="assigneeId => onAssigneeChange(task, assigneeId)"
                />
              </span>
            </td>
            <td class="font-mono text-[12px] text-muted-foreground">{{ task.start_date?.slice(0, 10) ?? '—' }} → {{ task.due_date?.slice(0, 10) ?? '—' }}</td>
            <td><div class="w-28"><div class="progress-line"><i :style="{ width: `${task.progress}%` }" /></div><small class="font-mono">{{ task.progress }}%</small></div></td>
            <td><ChevronRight :size="15" class="text-muted-foreground" aria-hidden="true" /></td>
          </tr>
        </tbody>
      </table>
    </div>
    <!-- 手机：同数据的紧凑卡片投影，无需横滚即可辨识名称 / 状态 / 截止 / 负责人（审计 A14） -->
    <ul v-if="displayTasks.length" class="grid gap-2.5 rounded-xl border border-line bg-panel p-3 lg:hidden">
      <li v-for="task in displayTasks" :key="task.id">
        <button
          type="button"
          class="flex w-full items-center gap-3 rounded-lg border border-transparent p-2 text-left transition-colors hover:border-[#c6d5ed] hover:bg-[#f8faff] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#2563eb]"
          :aria-label="`打开任务详情：${task.title}`"
          @click="store.openTask(task)"
        >
          <span class="priority-dot flex-none" aria-hidden="true" />
          <span class="min-w-0 flex-1">
            <b class="block truncate text-sm text-text">{{ task.title }}<span v-if="task.project_id" class="ml-2 font-mono text-[12px] font-normal text-cyan">{{ store.projects.find(project => project.id === task.project_id)?.name ?? '' }}</span></b>
            <span class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-muted-foreground">
              <span :class="['inline-flex h-5 items-center whitespace-nowrap rounded-full border px-2 text-[11px]', statusChipClass[task.status]]">{{ statusMap[task.status] }}</span>
              <span v-if="isBlocked(task)" class="inline-flex h-5 items-center rounded-full border border-[#f0b6b0] bg-[#fff5f4] px-2 text-[11px] text-[#b42318]">阻塞</span>
              <span>优先级 {{ priorityMap[task.priority] }}</span>
              <span :class="isOverdue(task) && 'font-medium text-[#b42318]'">截止 {{ task.due_date?.slice(0, 10) ?? '—' }}</span>
              <span>{{ store.memberMap.get(task.assignee_id ?? '')?.name ?? '未分配' }}</span>
            </span>
            <span class="mt-1.5 flex items-center gap-2">
              <span class="progress-line w-20"><i :style="{ width: `${task.progress}%` }" /></span>
              <small class="font-mono text-[11px]">{{ task.progress }}%</small>
            </span>
          </span>
          <ChevronRight :size="15" class="flex-none text-muted-foreground" aria-hidden="true" />
        </button>
      </li>
    </ul>
    <p v-if="!displayTasks.length" class="rounded-xl border border-line bg-panel p-10 text-center text-sm text-muted-foreground">没有匹配任务，尝试调整上方筛选或搜索。</p>
  </div>
</template>

<style scoped>
/* 行内可编辑单元：悬停给出“可修改”反馈，与表头筛选（虚线描边）区分（审计 A12） */
.task-list :deep(.task-edit [data-slot='select-trigger']) {
  transition: border-color .15s, background-color .15s;
}
.task-list :deep(.task-edit:hover [data-slot='select-trigger']) {
  border-color: #98a2b3;
  background: #f8fafc;
}

/* 行内说明限高：长进展不再撑高整行（审计 A13） */
.task-list .task-hint {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.task-list .task-hint__entry {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.task-list .task-hint__meta {
  display: flex;
  flex-wrap: wrap;
  column-gap: 8px;
}
.task-list .task-hint__meta > .inline-flex {
  flex: none;
}
</style>
