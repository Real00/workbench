<script setup lang="ts">
import { computed, defineAsyncComponent, reactive, ref } from 'vue'
import { CalendarDays, CheckSquare2, Columns3, GanttChart, List, Plus, Search } from '@lucide/vue'
import { useProgressStore } from '../store'
import TaskList from '../components/TaskList.vue'
import TaskBoard from '../components/TaskBoard.vue'
import {
  emptyTaskViewFilters,
  hasActiveTaskFilters,
  taskMatchesFilters,
  type TaskViewFilters,
} from '../task-filters'
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

function clearFilters() {
  Object.assign(filters, emptyTaskViewFilters())
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
        <Button v-for="item in views" :key="item.id" type="button" variant="ghost" :class="['view-tab', view === item.id && 'view-tab--active']" :aria-pressed="view === item.id" @click="view = item.id">
          <component :is="item.icon" :size="15" />{{ item.label }}
        </Button>
      </div>
      <div class="flex min-w-0 flex-1 items-center justify-end gap-2 md:max-w-md">
        <label class="search-box min-w-0 flex-1"><Search :size="15" /><span class="sr-only">搜索任务</span><Input v-model="filters.query" autocomplete="off" placeholder="搜索任务、负责人或项目" class="h-auto min-h-0 border-0 bg-transparent p-0 shadow-none focus-visible:ring-0" /></label>
        <Button v-if="filtering" type="button" variant="outline" size="sm" class="shrink-0" @click="clearFilters">清除筛选</Button>
      </div>
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
      <TaskBoard v-else-if="view === 'board'" :tasks="filteredTasks" />
      <TaskCalendar v-else-if="view === 'calendar'" :tasks="filteredTasks" />
      <TaskGantt v-else :tasks="filteredTasks" />
    </template>
  </div>
</template>
