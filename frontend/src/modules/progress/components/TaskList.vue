<script setup lang="ts">
import { ChevronRight } from '@lucide/vue'
import { useProgressStore } from '../store'
import { entryKindMap, isBlocked, latestEntry, priorityMap, statusMap, type Task } from '../types'

defineProps<{ tasks: Task[] }>()
const store = useProgressStore()

function taskHint(task: Task) {
  const entry = latestEntry(task)
  const extra = task.resources.length ? ` · ${task.resources.length} 个资源` : ''
  if (isBlocked(task) && entry) return `阻塞 · ${entry.content}${extra}`
  if (entry) return `${entryKindMap[entry.kind]} · ${entry.content}${extra}`
  return `${task.id.slice(0, 8)} · ${task.tags.join(' / ') || '无标签'}${extra}`
}
</script>

<template>
  <div class="overflow-x-auto rounded-xl border border-line bg-panel">
    <table class="data-table">
      <thead><tr><th>任务</th><th>状态</th><th>负责人</th><th>时间窗口</th><th>进度</th><th><span class="sr-only">操作</span></th></tr></thead>
      <tbody>
        <tr v-for="task in tasks" :key="task.id" tabindex="0" @click="store.openTask(task)" @keydown.enter="store.openTask(task)">
          <td><div class="flex items-center gap-3"><span :class="['priority', `priority--${task.priority}`]">{{ priorityMap[task.priority] }}</span><div><b>{{ task.title }}<span v-if="task.project_id" class="ml-2 font-mono text-[10px] font-normal text-cyan">{{ store.projects.find(project => project.id === task.project_id)?.name ?? '' }}</span></b><small>{{ taskHint(task) }}</small></div></div></td>
          <td><span :class="['status-chip', `status-chip--${isBlocked(task) ? 'blocked' : task.status}`]">{{ isBlocked(task) ? '阻塞' : statusMap[task.status] }}</span></td>
          <td><span class="flex items-center gap-2"><span class="avatar avatar--sm">{{ store.memberMap.get(task.assignee_id ?? '')?.name.slice(0, 2) ?? '--' }}</span>{{ store.memberMap.get(task.assignee_id ?? '')?.name ?? '未分配' }}</span></td>
          <td class="font-mono text-[11px] text-muted">{{ task.start_date?.slice(0, 10) ?? '—' }} → {{ task.due_date?.slice(0, 10) ?? '—' }}</td>
          <td><div class="w-28"><div class="progress-line"><i :style="{ width: `${task.progress}%` }" /></div><small class="font-mono">{{ task.progress }}%</small></div></td>
          <td><ChevronRight :size="15" class="text-muted" /></td>
        </tr>
      </tbody>
    </table>
    <p v-if="!tasks.length" class="p-10 text-center text-sm text-muted">没有匹配任务，尝试其他关键词。</p>
  </div>
</template>
