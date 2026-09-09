<script setup lang="ts">
import { computed } from 'vue'
import FullCalendar from '@fullcalendar/vue3'
import dayGridPlugin from '@fullcalendar/vue3/daygrid'
import interactionPlugin from '@fullcalendar/vue3/interaction'
import classicThemePlugin from '@fullcalendar/vue3/themes/classic'
import zhCn from '@fullcalendar/vue3/locales/zh-cn'
import '@fullcalendar/vue3/skeleton.css'
import '@fullcalendar/vue3/themes/classic/theme.css'
import '@fullcalendar/vue3/themes/classic/palette.css'
import { useProgressStore } from '../store'

import type { Task } from '../types'

const props = defineProps<{ tasks: Task[] }>()
const store = useProgressStore()
const options = computed(() => ({
  plugins: [classicThemePlugin, dayGridPlugin, interactionPlugin],
  initialView: 'dayGridMonth',
  locale: zhCn,
  colorScheme: 'light',
  height: 'auto',
  firstDay: 1,
  headerToolbar: { left: 'prev,next today', center: 'title', right: '' },
  buttonText: { today: '今天' },
  events: props.tasks.filter(task => task.start_date || task.due_date).map((task) => ({
    id: task.id, title: `${task.title} · ${store.memberMap.get(task.assignee_id ?? '')?.name ?? '未分配'}`,
    start: (task.start_date ?? task.due_date)?.slice(0, 10),
    end: task.due_date?.slice(0, 10),
  })),
  eventClick: ({ event }: { event: { id: string } }) => store.openTask(store.tasks.find((task) => task.id === event.id)),
}))
</script>

<template>
  <div class="calendar-shell rounded-xl border border-line bg-panel p-4">
    <FullCalendar :options="options" />
  </div>
</template>
