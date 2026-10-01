<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useMediaQuery } from '@vueuse/core'
import Gantt from 'frappe-gantt'
import type { GanttOptions, GanttTask } from 'frappe-gantt'
import { Maximize2, X } from '@lucide/vue'
import { useProgressStore } from '../store'
import { Button } from '@/components/ui/button'

import type { Task } from '../types'
import { ganttBarPalette } from '../status-palette'

const props = defineProps<{ tasks: Task[] }>()
const datedTasks = computed(() => props.tasks.filter(task => task.start_date && task.due_date))
const unscheduledTasks = computed(() => props.tasks.filter(task => !task.start_date || !task.due_date))
const store = useProgressStore()
const chart = ref<HTMLElement>()
const fullscreenChart = ref<HTMLElement>()
const isNarrow = useMediaQuery('(max-width: 768px)')
const fullscreen = ref(false)

interface GanttTaskWithClass extends GanttTask {
  custom_class?: string
}

type LowerText = string | ((date: Date, prev: Date | null, lang?: string) => string)

interface GanttViewModeOption {
  name: 'Day' | 'Week' | 'Month'
  padding: string
  step: string
  column_width?: number
  date_format?: string
  lower_text: LowerText
  upper_text: (date: Date, prev: Date | null, lang?: string) => string
  thick_line?: (date: Date) => boolean
  upper_text_frequency?: number
  snap_at?: string
}

interface GanttOptionsExtended extends GanttOptions {
  view_modes?: GanttViewModeOption[]
  infinite_padding?: boolean
}

/* 压缩图表两侧留白：范围贴合任务日期，只保留少量前后缓冲 */
const viewModes: GanttViewModeOption[] = [
  {
    name: 'Week',
    padding: '10d',
    step: '7d',
    column_width: 140,
    date_format: 'YYYY-MM-DD',
    lower_text: (date) => {
      const end = new Date(date)
      end.setDate(end.getDate() + 6)
      return `${date.getMonth() + 1}/${date.getDate()} - ${end.getMonth() + 1}/${end.getDate()}`
    },
    upper_text: (date, prev) => (!prev || date.getMonth() !== prev.getMonth() ? `${date.getFullYear()}年${date.getMonth() + 1}月` : ''),
    thick_line: (date) => date.getDate() >= 1 && date.getDate() <= 7,
    upper_text_frequency: 4,
  },
  {
    name: 'Day',
    padding: '6d',
    step: '1d',
    column_width: 45,
    date_format: 'YYYY-MM-DD',
    lower_text: (date, prev) => (!prev || date.getDate() !== prev.getDate() ? String(date.getDate()) : ''),
    upper_text: (date, prev) => (!prev || date.getMonth() !== prev.getMonth() ? `${date.getFullYear()}年${date.getMonth() + 1}月` : ''),
    thick_line: (date) => date.getDay() === 1,
  },
  {
    name: 'Month',
    padding: '1m',
    step: '1m',
    column_width: 120,
    date_format: 'YYYY-MM',
    lower_text: (date) => `${date.getFullYear()}年${date.getMonth() + 1}月`,
    upper_text: (date, prev) => (!prev || date.getFullYear() !== prev.getFullYear() ? String(date.getFullYear()) : ''),
    thick_line: (date) => date.getMonth() % 3 === 0,
    snap_at: '7d',
  },
]

/* view_modes 传入后首个元素即初始视图，因此 Week 排在最前 */
const viewMode = ref<'Day' | 'Week' | 'Month'>('Week')
const viewModeOptions = [
  { value: 'Day', label: '日' },
  { value: 'Week', label: '周' },
  { value: 'Month', label: '月' },
] as const

type GanttInstance = InstanceType<typeof Gantt> & { scroll_current?: () => void }
const chartInstances = new Map<'chart' | 'fullscreen', GanttInstance>()

const statusBarClass: Record<Task['status'], string | undefined> = {
  todo: undefined,
  in_progress: undefined,
  done: 'task-bar--done',
  cancelled: 'task-bar--cancelled',
}

/* 图例与条形配色同源（status-palette），桌面与全屏共用 */
const legendEntries: { status: Task['status']; label: string }[] = [
  { status: 'todo', label: '待处理 / 进行中' },
  { status: 'done', label: '已完成' },
  { status: 'cancelled', label: '已取消' },
]

/* 条形填充色经 CSS 变量下发，:deep 规则只引用变量，不再硬编码 */
const barCssVars = {
  '--gantt-done-fill': ganttBarPalette.done.fill,
  '--gantt-done-stroke': ganttBarPalette.done.stroke,
  '--gantt-done-progress': ganttBarPalette.done.progress,
  '--gantt-cancelled-fill': ganttBarPalette.cancelled.fill,
  '--gantt-cancelled-stroke': ganttBarPalette.cancelled.stroke,
  '--gantt-cancelled-progress': ganttBarPalette.cancelled.progress,
} as Record<string, string>

const timelineGroups = computed(() => {
  const groups = new Map<string, Task[]>()
  for (const task of datedTasks.value) {
    const key = task.start_date!.slice(0, 10)
    const list = groups.get(key) ?? []
    list.push(task)
    groups.set(key, list)
  }
  return [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, items]) => ({ date, items }))
})

function missingDateLabel(task: Task): string {
  if (!task.start_date && !task.due_date) return '缺开始与截止日期'
  return task.start_date ? '缺截止日期' : '缺开始日期'
}

/* 统一标签规则：任务名固定展示在条形右侧，深色文字保证可读 */
function moveLabelsOutside(el: HTMLElement) {
  for (const bar of Array.from(el.querySelectorAll<SVGRectElement>('.bar'))) {
    const label = bar.closest('.bar-wrapper')?.querySelector<SVGTextElement>('.bar-label')
    if (!label) continue
    const x = (Number(bar.getAttribute('x')) || 0) + (Number(bar.getAttribute('width')) || 0) + 10
    label.setAttribute('x', String(x))
    label.classList.add('big')
  }
}

function renderGantt(el: HTMLElement | undefined, slot: 'chart' | 'fullscreen') {
  if (!el) return
  const dated = datedTasks.value
  el.innerHTML = ''
  chartInstances.delete(slot)
  if (!dated.length) return
  const items: GanttTaskWithClass[] = dated.map((task) => ({
    id: task.id,
    name: `${task.title} · ${store.memberMap.get(task.assignee_id ?? '')?.name ?? '未分配'}`,
    start: task.start_date!.slice(0, 10),
    end: task.due_date!.slice(0, 10),
    progress: task.progress,
    dependencies: '',
    custom_class: statusBarClass[task.status],
  }))
  const options: GanttOptionsExtended = {
    view_mode: viewMode.value,
    // 库在传入自定义 view_modes 时强制以 view_modes[0] 为初始视图（setup_options 覆盖 view_mode），
    // 因此把当前所选尺度排到首位，重建实例后仍保持用户选择
    view_modes: viewMode.value === 'Week'
      ? viewModes
      : [viewModes.find(mode => mode.name === viewMode.value)!, ...viewModes.filter(mode => mode.name !== viewMode.value)],
    language: 'zh',
    readonly: true,
    scroll_to: 'start',
    infinite_padding: false,
    today_button: false,
    popup: false,
    bar_height: 36,
    on_click: (item: { id: string }) => store.openTask(store.tasks.find((task) => task.id === item.id)),
  }
  chartInstances.set(slot, new Gantt(el, items, options))
  requestAnimationFrame(() => moveLabelsOutside(el))
}

function rerenderCharts() {
  if (!isNarrow.value) renderGantt(chart.value, 'chart')
  if (fullscreen.value) renderGantt(fullscreenChart.value, 'fullscreen')
}

async function setViewMode(mode: 'Day' | 'Week' | 'Month') {
  if (viewMode.value === mode) return
  viewMode.value = mode
  await nextTick()
  rerenderCharts()
}

function scrollToToday() {
  for (const instance of chartInstances.values()) {
    try {
      instance.scroll_current?.()
    } catch {
      // 今天不在图表范围内时忽略
    }
  }
}

watch(datedTasks, async () => {
  await nextTick()
  rerenderCharts()
}, { immediate: true, deep: true })

watch(fullscreen, async (open) => {
  if (!open) return
  await nextTick()
  renderGantt(fullscreenChart.value, 'fullscreen')
})

watch(isNarrow, async (narrow) => {
  if (narrow) return
  fullscreen.value = false
  await nextTick()
  rerenderCharts()
})
</script>

<template>
  <div class="gantt-shell overflow-x-auto rounded-xl border border-line bg-panel p-4" :style="barCssVars">
    <div class="mb-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
      <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
        <p class="text-xs text-muted-foreground">{{ datedTasks.length }} 个已排期任务</p>
        <div v-if="!isNarrow && datedTasks.length" class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground" aria-label="甘特图状态图例">
          <span v-for="entry in legendEntries" :key="entry.status" class="inline-flex items-center gap-1.5">
            <i class="gantt-legend-swatch" :style="{ background: ganttBarPalette[entry.status].fill, borderColor: ganttBarPalette[entry.status].stroke }"><b :style="{ background: ganttBarPalette[entry.status].progress }" /></i>{{ entry.label }}
          </span>
          <span>任务名在条形右侧 · 竖线为今天</span>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <template v-if="!isNarrow && datedTasks.length">
          <div class="segmented-tabs" role="group" aria-label="甘特图时间尺度">
            <Button
              v-for="option in viewModeOptions"
              :key="option.value"
              type="button"
              variant="ghost"
              size="sm"
              :class="['view-tab', viewMode === option.value && 'view-tab--active']"
              :aria-pressed="viewMode === option.value"
              @click="setViewMode(option.value)"
            >{{ option.label }}</Button>
          </div>
          <Button type="button" size="sm" variant="outline" @click="scrollToToday">今天</Button>
        </template>
        <Button v-if="isNarrow && datedTasks.length" type="button" size="sm" variant="outline" @click="fullscreen = true">
          <Maximize2 :size="14" />全屏甘特
        </Button>
        <details v-if="unscheduledTasks.length" class="unscheduled-details relative">
          <summary>有 {{ unscheduledTasks.length }} 个任务未设置完整日期，点击补全</summary>
          <div class="absolute right-0 z-20 mt-2 w-72 rounded-lg border border-line bg-panel p-2 shadow-lg">
            <div v-for="task in unscheduledTasks" :key="task.id" class="flex items-center justify-between gap-2 rounded-md px-2 py-1.5 hover:bg-panel-2">
              <span class="min-w-0">
                <b class="block truncate text-[13px] text-text">{{ task.title }}</b>
                <small class="block text-xs text-muted-foreground">{{ missingDateLabel(task) }}</small>
              </span>
              <Button type="button" size="sm" variant="outline" class="shrink-0" @click="store.openTask(task)">补全日期</Button>
            </div>
          </div>
        </details>
      </div>
    </div>

    <template v-if="isNarrow">
      <div v-if="timelineGroups.length" class="space-y-4">
        <section v-for="group in timelineGroups" :key="group.date">
          <p class="mb-2 font-mono text-xs text-muted-foreground">{{ group.date }}</p>
          <ul class="space-y-2">
            <li v-for="task in group.items" :key="task.id">
              <button
                type="button"
                class="w-full rounded-lg border border-line bg-panel-2 px-3 py-2.5 text-left"
                @click="store.openTask(task)"
              >
                <b class="block text-sm text-text">{{ task.title }}</b>
                <span class="mt-1 block text-[12px] text-muted-foreground">
                  {{ store.memberMap.get(task.assignee_id ?? '')?.name ?? '未分配' }}
                  · {{ task.start_date?.slice(0, 10) }} → {{ task.due_date?.slice(0, 10) }}
                  · {{ task.progress }}%
                </span>
              </button>
            </li>
          </ul>
        </section>
      </div>
      <p v-else class="empty-inline">暂无同时设置开始与截止日期的任务</p>
    </template>
    <template v-else>
      <div ref="chart" class="min-w-0" aria-label="任务甘特图" />
      <p v-if="!datedTasks.length" class="empty-inline">暂无同时设置开始与截止日期的任务，可点击右上角列表补全日期</p>
    </template>

    <Teleport to="body">
      <div v-if="fullscreen" class="fixed inset-0 z-50 flex flex-col bg-panel" :style="[barCssVars, { paddingTop: 'var(--safe-top)', paddingBottom: 'var(--safe-bottom)' }]">
        <header class="flex shrink-0 items-center justify-between border-b border-line px-4 py-3">
          <h2 class="font-display text-lg text-text">甘特图</h2>
          <Button aria-label="关闭全屏甘特" variant="ghost" size="icon" @click="fullscreen = false"><X :size="16" /></Button>
        </header>
        <div class="min-h-0 flex-1 overflow-auto p-3">
          <div class="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <div class="segmented-tabs" role="group" aria-label="全屏甘特时间尺度">
              <Button
                v-for="option in viewModeOptions"
                :key="option.value"
                type="button"
                variant="ghost"
                size="sm"
                :class="['view-tab', viewMode === option.value && 'view-tab--active']"
                :aria-pressed="viewMode === option.value"
                @click="setViewMode(option.value)"
              >{{ option.label }}</Button>
            </div>
            <Button type="button" size="sm" variant="outline" @click="scrollToToday">今天</Button>
            <span v-for="entry in legendEntries" :key="entry.status" class="inline-flex items-center gap-1.5">
              <i class="gantt-legend-swatch" :style="{ background: ganttBarPalette[entry.status].fill, borderColor: ganttBarPalette[entry.status].stroke }"><b :style="{ background: ganttBarPalette[entry.status].progress }" /></i>{{ entry.label }}
            </span>
          </div>
          <div ref="fullscreenChart" class="gantt-shell min-w-0" aria-label="全屏任务甘特图" />
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
/* 状态配色与图例同源（status-palette 经 barCssVars 下发）：完成绿、取消灰，其余保持默认蓝 */
:deep(.bar-wrapper.task-bar--done .bar) {
  fill: var(--gantt-done-fill, #d9f0e3);
  stroke: var(--gantt-done-stroke, #8fd0af);
}
:deep(.bar-wrapper.task-bar--done .bar-progress) {
  fill: var(--gantt-done-progress, #2e9c6b);
}
:deep(.bar-wrapper.task-bar--cancelled .bar) {
  fill: var(--gantt-cancelled-fill, #eef1f5);
  stroke: var(--gantt-cancelled-stroke, #cbd5e1);
}
:deep(.bar-wrapper.task-bar--cancelled .bar-progress) {
  fill: var(--gantt-cancelled-progress, #b7c3d3);
}
:deep(.bar-wrapper.task-bar--cancelled .bar-label) {
  fill: var(--muted-foreground);
  text-decoration: line-through;
}
/* 条形右侧标签：与代码注释「深色文字保证可读」对齐——主文字色，不再用次要灰 */
:deep(.bar-label.big) {
  font-size: 13px;
  font-weight: 500;
  fill: var(--color-text);
}
/* 图例按「底色 + 进度段」表达条形语言：进度色会覆盖条身（100% 完成的条整根是进度色） */
.gantt-legend-swatch {
  display: inline-flex;
  width: 16px;
  height: 9px;
  flex-shrink: 0;
  overflow: hidden;
  border: 1px solid;
  border-radius: 3px;
}
.gantt-legend-swatch b {
  width: 55%;
  height: 100%;
}
.unscheduled-details summary {
  list-style: none;
  cursor: pointer;
  font-size: 12px;
  color: var(--muted-foreground);
}
.unscheduled-details summary::-webkit-details-marker {
  display: none;
}
.unscheduled-details summary:hover {
  color: var(--color-cyan);
}
</style>
