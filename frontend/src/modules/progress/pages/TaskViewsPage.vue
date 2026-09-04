<script setup lang="ts">
import { ref } from 'vue'
import { CalendarDays, CheckSquare2, Columns3, GanttChart, List, Plus, Search } from '@lucide/vue'
import { useProgressStore } from '../store'
import TaskList from '../components/TaskList.vue'
import TaskBoard from '../components/TaskBoard.vue'
import TaskCalendar from '../components/TaskCalendar.vue'
import TaskGantt from '../components/TaskGantt.vue'

type View = 'list' | 'board' | 'calendar' | 'gantt'
const view = ref<View>('list')
const query = ref('')
const store = useProgressStore()
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
      <div><p class="eyebrow">Work registry</p><h1>任务视图</h1><p>{{ store.tasks.length }} 个任务 · 数据来自工作台 API</p></div>
      <button class="btn-primary" @click="store.openTask()"><Plus :size="16" />新建任务</button>
    </header>
    <div class="mb-4 flex flex-col gap-3 rounded-xl border border-line bg-panel p-2 md:flex-row md:items-center md:justify-between">
      <div class="flex overflow-x-auto" role="tablist" aria-label="任务视图">
        <button v-for="item in views" :key="item.id" :class="['view-tab', view === item.id && 'view-tab--active']" role="tab" :aria-selected="view === item.id" @click="view = item.id">
          <component :is="item.icon" :size="15" />{{ item.label }}
        </button>
      </div>
      <label class="search-box"><Search :size="15" /><span class="sr-only">搜索任务</span><input v-model="query" placeholder="搜索任务..." /></label>
    </div>
    <div v-if="!store.loading && !store.tasks.length" class="empty-state"><CheckSquare2 :size="28" /><h2>尚无任务</h2><p>创建第一个任务后，可在列表、看板、日历和甘特图中查看。</p><button class="btn-primary" @click="store.openTask()">新建任务</button></div>
    <template v-else><TaskList v-if="view === 'list'" :query="query" /><TaskBoard v-else-if="view === 'board'" /><TaskCalendar v-else-if="view === 'calendar'" /><TaskGantt v-else /></template>
  </div>
</template>
