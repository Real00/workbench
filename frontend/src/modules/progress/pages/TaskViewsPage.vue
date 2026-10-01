<script setup lang="ts">
import { computed, defineAsyncComponent, reactive, ref } from 'vue'
import { CalendarDays, CheckSquare2, Columns3, GanttChart, List, ListFilter, Plus, Search, X } from '@lucide/vue'
import { useProgressStore } from '../store'
import TaskList from '../components/TaskList.vue'
import TaskBoard from '../components/TaskBoard.vue'
import {
  TASK_FILTER_NONE,
  emptyTaskViewFilters,
  hasActiveTaskFilters,
  taskMatchesFilters,
  type TaskViewFilters,
} from '../task-filters'
import { priorityMap, statusMap, type TaskStatus } from '../types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
const TaskCalendar = defineAsyncComponent(() => import('../components/TaskCalendar.vue'))
const TaskGantt = defineAsyncComponent(() => import('../components/TaskGantt.vue'))

type View = 'list' | 'board' | 'calendar' | 'gantt'
const view = ref<View>('list')
const filters = reactive<TaskViewFilters>(emptyTaskViewFilters())
const store = useProgressStore()

const filteredTasks = computed(() => store.tasks.filter(task => taskMatchesFilters(task, filters, {
  assigneeName: store.memberMap.get(task.assignee_id ?? '')?.name,
  projectName: store.projects.find(project => project.id === task.project_id)?.name,
})))

const filtering = computed(() => hasActiveTaskFilters(filters))

/**
 * 筛选偏好由 TaskList 的 v-model 同步持久化；TaskList 未挂载（看板/日历/甘特）时
 * v-model 断开，页面级清除必须直接写偏好，否则切回列表时筛选会从 localStorage「复活」
 */
function clearFilters() {
  Object.assign(filters, emptyTaskViewFilters())
  store.setTaskListPrefs({ status: '', priority: '', assignee: '', project: '', overdueOnly: false })
}

/* 非列表视图没有 TaskList 的筛选行，激活的筛选必须显形为可单独移除的 chip */
const activeFilterChips = computed(() => {
  const chips: { label: string; clear: () => void }[] = []
  if (filters.status) chips.push({ label: `状态：${statusMap[filters.status]}`, clear: () => clearFilter('status') })
  if (filters.priority) chips.push({ label: `优先级：${priorityMap[filters.priority]}`, clear: () => clearFilter('priority') })
  if (filters.assignee) {
    const label = filters.assignee === TASK_FILTER_NONE ? '未分配' : store.memberMap.get(filters.assignee)?.name ?? '未知成员'
    chips.push({ label: `负责人：${label}`, clear: () => clearFilter('assignee') })
  }
  if (filters.project) {
    const label = filters.project === TASK_FILTER_NONE ? '无项目' : store.projects.find(project => project.id === filters.project)?.name ?? '未知项目'
    chips.push({ label: `项目：${label}`, clear: () => clearFilter('project') })
  }
  if (filters.query.trim()) chips.push({ label: `搜索：${filters.query.trim()}`, clear: () => { filters.query = '' } })
  return chips
})

function clearFilter(key: 'status' | 'priority' | 'assignee' | 'project') {
  filters[key] = ''
  store.setTaskListPrefs({ [key]: '' })
}

/* 看板里改动任务状态后，与新状态冲突的状态筛选自动解除，避免卡片拖过去即被隐藏 */
function onBoardStatusChanged(status: TaskStatus) {
  if (filters.status && filters.status !== status) clearFilter('status')
}

const views = [
  { id: 'list', label: '列表', icon: List },
  { id: 'board', label: '看板', icon: Columns3 },
  { id: 'calendar', label: '日历', icon: CalendarDays },
  { id: 'gantt', label: '甘特图', icon: GanttChart },
] as const
</script>

<template>
  <div class="page-wrap">
    <header class="page-header">
      <div>
        <p class="eyebrow">Work registry</p>
        <h1>任务视图</h1>
        <p>
          {{ store.tasks.length }} 个任务
          <template v-if="filtering"> · 当前显示 {{ filteredTasks.length }} 个</template>
          · 按你的工作方式查看
        </p>
      </div>
      <Button @click="store.openTask()"><Plus :size="16" />新建任务</Button>
    </header>
    <div class="task-toolbar mb-4 flex flex-col gap-3 rounded-xl border border-line bg-panel p-2 md:flex-row md:items-center md:justify-between">
      <div class="segmented-tabs" role="group" aria-label="任务视图">
        <Button v-for="item in views" :key="item.id" type="button" variant="ghost" :class="['view-tab', view === item.id && 'view-tab--active']" :aria-pressed="view === item.id" :aria-label="item.label" :title="item.label" @click="view = item.id">
          <component :is="item.icon" :size="15" /><span class="hidden sm:inline">{{ item.label }}</span>
        </Button>
      </div>
      <div class="flex min-w-0 flex-1 items-center justify-end gap-2 md:max-w-md">
        <label class="search-box search-box--sm min-w-0 flex-1"><Search :size="15" /><span class="sr-only">搜索任务</span><Input v-model="filters.query" autocomplete="off" placeholder="搜索任务、负责人或项目" class="h-auto min-h-0 border-0 bg-transparent p-0 shadow-none focus-visible:ring-0" /></label>
        <Button v-if="filtering" type="button" variant="outline" size="sm" class="shrink-0" @click="clearFilters">清除筛选</Button>
      </div>
    </div>
    <div v-if="view !== 'list' && activeFilterChips.length" class="mb-3 flex flex-wrap items-center gap-x-2 gap-y-1.5 rounded-xl border border-line bg-panel px-3 py-2" role="group" aria-label="生效中的筛选">
      <span class="flex items-center gap-1 text-[11px] font-medium text-muted-foreground"><ListFilter :size="13" aria-hidden="true" />生效筛选</span>
      <button
        v-for="chip in activeFilterChips"
        :key="chip.label"
        type="button"
        class="filter-chip filter-chip--active inline-flex h-7 items-center gap-1 whitespace-nowrap rounded-lg px-2 text-xs transition-colors"
        :aria-label="`移除筛选：${chip.label}`"
        @click="chip.clear()"
      >
        {{ chip.label }}<X :size="13" aria-hidden="true" />
      </button>
      <span class="ml-auto hidden text-[11px] text-muted-foreground sm:inline">来自列表的筛选，点击移除</span>
    </div>
    <div v-if="store.loading" class="card p-2">
      <div v-for="i in 6" :key="i" class="flex items-center gap-4 px-3 py-3">
        <div class="skeleton h-6 w-1.5 rounded" /><div class="flex-1"><div class="skeleton h-3.5 w-2/5" /><div class="skeleton mt-2 h-2.5 w-1/4" /></div>
        <div class="skeleton h-5 w-14 rounded-full" /><div class="skeleton h-5 w-20 rounded-full" /><div class="skeleton h-2.5 w-28" /><div class="skeleton h-2.5 w-24" />
      </div>
    </div>
    <div v-else-if="!store.tasks.length" class="empty-state"><CheckSquare2 :size="28" /><h2>尚无任务</h2><p>创建第一个任务后，可在列表、看板、日历和甘特图中查看。</p><Button @click="store.openTask()">新建任务</Button></div>
    <div v-else-if="!filteredTasks.length" class="empty-state"><Search :size="26" /><h2>没有匹配的任务</h2><p>尝试调整表头筛选或搜索关键词。</p><Button @click="clearFilters" variant="outline">清除筛选</Button></div>
    <template v-else>
      <TaskList
        v-if="view === 'list'"
        :tasks="filteredTasks"
        v-model:status-filter="filters.status"
        v-model:priority-filter="filters.priority"
        v-model:assignee-filter="filters.assignee"
        v-model:project-filter="filters.project"
      />
      <TaskBoard v-else-if="view === 'board'" :tasks="filteredTasks" @status-changed="onBoardStatusChanged" />
      <TaskCalendar v-else-if="view === 'calendar'" :tasks="filteredTasks" />
      <TaskGantt v-else :tasks="filteredTasks" />
    </template>
  </div>
</template>
