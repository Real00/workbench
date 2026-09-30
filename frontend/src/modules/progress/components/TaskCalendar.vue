<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useMediaQuery } from '@vueuse/core'
import FullCalendar from '@fullcalendar/vue3'
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

import type { Task } from '../types'

const props = defineProps<{ tasks: Task[] }>()
const store = useProgressStore()
const isNarrow = useMediaQuery('(max-width: 640px)')
const mode = ref<'list' | 'month'>('list')

watch(isNarrow, (narrow) => {
  mode.value = narrow ? 'list' : 'month'
}, { immediate: true })

const options = computed(() => ({
  plugins: [classicThemePlugin, dayGridPlugin, listPlugin, interactionPlugin],
  initialView: mode.value === 'list' ? 'listWeek' : 'dayGridMonth',
  locale: zhCn,
  colorScheme: 'light',
  height: 'auto',
  firstDay: 1,
  headerToolbar: {
    left: 'prev,next today',
    center: 'title',
    right: '',
  },
  buttonText: { today: '今天', listWeek: '本周', dayGridMonth: '月' },
  events: props.tasks.filter(task => task.start_date || task.due_date).map((task) => ({
    id: task.id,
    title: `${task.title} · ${store.memberMap.get(task.assignee_id ?? '')?.name ?? '未分配'}`,
    start: (task.start_date ?? task.due_date)?.slice(0, 10),
    end: task.due_date?.slice(0, 10),
  })),
  eventClick: ({ event }: { event: { id: string } }) => store.openTask(store.tasks.find((task) => task.id === event.id)),
}))
</script>

<template>
  <div class="calendar-shell overflow-x-auto rounded-xl border border-line bg-panel p-4">
    <div v-if="isNarrow" class="mb-3 flex gap-2">
      <Button type="button" size="sm" :variant="mode === 'list' ? 'default' : 'outline'" @click="mode = 'list'">近期列表</Button>
      <Button type="button" size="sm" :variant="mode === 'month' ? 'default' : 'outline'" @click="mode = 'month'">月视图</Button>
    </div>
    <FullCalendar :key="mode" :options="options" />
  </div>
</template>
