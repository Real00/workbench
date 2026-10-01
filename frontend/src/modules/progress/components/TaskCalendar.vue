<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useMediaQuery } from '@vueuse/core'
import FullCalendar, { type CalendarOptions } from '@fullcalendar/vue3'
import dayGridPlugin from '@fullcalendar/vue3/daygrid'
import listPlugin from '@fullcalendar/vue3/list'
import interactionPlugin from '@fullcalendar/vue3/interaction'
import classicThemePlugin from '@fullcalendar/vue3/themes/classic'
import zhCn from '@fullcalendar/vue3/locales/zh-cn'
import '@fullcalendar/vue3/skeleton.css'
import '@fullcalendar/vue3/themes/classic/theme.css'
import '@fullcalendar/vue3/themes/classic/palette.css'
import { useProgressStore } from '../store'
import { Button } from '@/components/ui/button'

import { statusMap, type Task, type TaskStatus } from '../types'
import { statusPalette } from '../status-palette'

const props = defineProps<{ tasks: Task[] }>()
const store = useProgressStore()
const isNarrow = useMediaQuery('(max-width: 640px)')
const mode = ref<'list' | 'month'>('list')

const modeOptions = [
  { value: 'list', label: '议程' },
  { value: 'month', label: '月历' },
] as const

watch(isNarrow, (narrow) => {
  mode.value = narrow ? 'list' : 'month'
}, { immediate: true })

/* 状态图例与事件配色保持同一份来源（status-palette，与列表 / 甘特统一） */
const statusStyles = statusPalette

interface CalendarEventProps {
  title: string
  assignee: string
  status: TaskStatus
  range: string
}

/* FullCalendar 的 end 为独占语义，截止日期需 +1 天才包含当天，与甘特图口径一致 */
function inclusiveEndDate(date: string | null | undefined): string | undefined {
  if (!date) return undefined
  const [year, month, day] = date.slice(0, 10).split('-').map(Number)
  const next = new Date(year!, (month ?? 1) - 1, (day ?? 1) + 1)
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${next.getFullYear()}-${pad(next.getMonth() + 1)}-${pad(next.getDate())}`
}

function rangeLabel(task: Task): string {
  if (task.start_date && task.due_date) return `开始 ${task.start_date.slice(0, 10)} · 截止 ${task.due_date.slice(0, 10)}`
  if (task.due_date) return `截止 ${task.due_date.slice(0, 10)} · 未设开始`
  return `开始 ${task.start_date!.slice(0, 10)} · 未设截止`
}

const options = computed<CalendarOptions>(() => ({
  plugins: [classicThemePlugin, dayGridPlugin, listPlugin, interactionPlugin],
  initialView: mode.value === 'list' ? 'listMonth' : 'dayGridMonth',
  locale: zhCn,
  colorScheme: 'light',
  height: 'auto',
  /* 议程（listMonth）高度全靠事件行撑起：无事件时若无此文案会塌成一条无文字的空表 */
  noEventsText: '本月暂无日程——可翻月查找，或调整筛选条件',
  firstDay: 1,
  headerToolbar: {
    left: 'prev,next today',
    center: 'title',
    right: '',
  },
  buttonText: { today: '今天', listMonth: '议程', dayGridMonth: '月历' },
  events: props.tasks.filter(task => task.start_date || task.due_date).map((task) => {
    const style = statusStyles[task.status]
    const assignee = store.memberMap.get(task.assignee_id ?? '')?.name ?? '未分配'
    return {
      id: task.id,
      title: `${task.title} · ${assignee}`,
      start: (task.start_date ?? task.due_date)?.slice(0, 10),
      end: inclusiveEndDate(task.due_date),
      backgroundColor: style.background,
      borderColor: style.border,
      textColor: style.text,
      classNames: [`task-event--${task.status}`],
      extendedProps: {
        title: task.title,
        assignee,
        status: task.status,
        range: rangeLabel(task),
      } satisfies CalendarEventProps,
    }
  }),
  eventDidMount: ({ el, event, view }) => {
    const summary = event.extendedProps as CalendarEventProps
    el.title = `${summary.title}\n负责人：${summary.assignee}\n${summary.range}\n状态：${statusMap[summary.status]}`
    /* 议程（list）行的标题不着事件底色：改用状态文字色，终态加删除线。
       注意不能用 eventContent 实现：v7 里其回调返回 undefined 会吞掉默认内容，
       月历事件会塌成无文字的空条 */
    if (view.type.startsWith('list')) {
      const style = statusStyles[summary.status]
      el.style.color = style.text
      if (summary.status === 'done' || summary.status === 'cancelled') el.style.textDecoration = 'line-through'
    }
  },
  eventClick: ({ event }: { event: { id: string } }) => store.openTask(store.tasks.find((task) => task.id === event.id)),
}))
</script>

<template>
  <div class="calendar-shell overflow-x-auto rounded-xl border border-line bg-panel p-4">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
      <div class="segmented-tabs" role="group" aria-label="日历视图切换">
        <Button
          v-for="option in modeOptions"
          :key="option.value"
          type="button"
          variant="ghost"
          size="sm"
          :class="['view-tab', mode === option.value && 'view-tab--active']"
          :aria-pressed="mode === option.value"
          @click="mode = option.value"
        >{{ option.label }}</Button>
      </div>
      <p class="text-xs text-muted-foreground">按「开始 → 截止」绘制，截止当天含在内；仅设单日期的任务显示在当天</p>
    </div>
    <div class="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground" aria-label="日历状态图例">
      <span v-for="(style, status) in statusStyles" :key="status" class="inline-flex items-center gap-1.5">
        <i
          class="inline-block size-3 rounded-[3px] border"
          :style="{ background: style.background, borderColor: style.border, borderStyle: style.dashed ? 'dashed' : 'solid' }"
        />{{ statusMap[status] }}
      </span>
    </div>
    <FullCalendar :key="mode" :options="options" />
  </div>
</template>

<style scoped>
/* 已取消：虚线边框区分待处理（月历块事件）；议程标题样式由 eventContent 控制 */
:deep(.task-event--cancelled) {
  border-style: dashed;
}
</style>
