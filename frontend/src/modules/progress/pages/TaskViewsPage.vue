<script setup lang="ts">
import { computed, defineAsyncComponent, ref } from 'vue'
import { CalendarDays, CheckSquare2, Columns3, GanttChart, List, Plus, Search } from '@lucide/vue'
import { useProgressStore } from '../store'
import TaskList from '../components/TaskList.vue'
import TaskBoard from '../components/TaskBoard.vue'
const TaskCalendar = defineAsyncComponent(() => import('../components/TaskCalendar.vue'))
const TaskGantt = defineAsyncComponent(() => import('../components/TaskGantt.vue'))

type View = 'list' | 'board' | 'calendar' | 'gantt'
const view = ref<View>('list')
const query = ref('')
const store = useProgressStore()
const filteredTasks = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase()
  return store.tasks.filter(task => !needle || [task.title, ...task.tags, store.memberMap.get(task.assignee_id ?? '')?.name, store.projects.find(project => project.id === task.project_id)?.name].filter(Boolean).join(' ').toLocaleLowerCase().includes(needle))
})
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
      <div><p class="eyebrow">Work registry</p><h1>任务视图</h1><p>{{ store.tasks.length }} 个任务 · 按你的工作方式查看</p></div>
      <button class="btn-primary" @click="store.openTask()"><Plus :size="16" />新建任务</button>
    </header>
    <div class="task-toolbar mb-4 flex flex-col gap-3 rounded-xl border border-line bg-panel p-2 md:flex-row md:items-center md:justify-between">
      <div class="segmented-tabs" role="group" aria-label="任务视图">
        <button v-for="item in views" :key="item.id" :class="['view-tab', view === item.id && 'view-tab--active']" :aria-pressed="view === item.id" @click="view = item.id">
          <component :is="item.icon" :size="15" />{{ item.label }}
        </button>
      </div>
      <label class="search-box"><Search :size="15" /><span class="sr-only">搜索任务</span><input v-model="query" autocomplete="off" placeholder="搜索任务、负责人或项目" /></label>
    </div>
    <div v-if="store.loading" class="card p-2">
      <div v-for="i in 6" :key="i" class="flex items-center gap-4 px-3 py-3">
        <div class="skeleton h-6 w-1.5 rounded" /><div class="flex-1"><div class="skeleton h-3.5 w-2/5" /><div class="skeleton mt-2 h-2.5 w-1/4" /></div>
        <div class="skeleton h-5 w-14 rounded-full" /><div class="skeleton h-5 w-20 rounded-full" /><div class="skeleton h-2.5 w-28" /><div class="skeleton h-2.5 w-24" />
      </div>
    </div>
    <div v-else-if="!store.tasks.length" class="empty-state"><CheckSquare2 :size="28" /><h2>尚无任务</h2><p>创建第一个任务后，可在列表、看板、日历和甘特图中查看。</p><button class="btn-primary" @click="store.openTask()">新建任务</button></div>
    <div v-else-if="!filteredTasks.length" class="empty-state"><Search :size="26" /><h2>没有匹配的任务</h2><p>尝试其他关键词，或清除搜索查看全部任务。</p><button class="btn-secondary" @click="query = ''">清除搜索</button></div>
    <template v-else><TaskList v-if="view === 'list'" :tasks="filteredTasks" /><TaskBoard v-else-if="view === 'board'" :tasks="filteredTasks" /><TaskCalendar v-else-if="view === 'calendar'" :tasks="filteredTasks" /><TaskGantt v-else :tasks="filteredTasks" /></template>
  </div>
</template>
