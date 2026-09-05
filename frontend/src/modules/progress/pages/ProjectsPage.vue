<script setup lang="ts">
import { computed } from 'vue'
import { FolderKanban, Plus } from '@lucide/vue'
import { useProgressStore } from '../store'
import { projectStatusMap, type Project } from '../types'

const store = useProgressStore()

function formatDate(value: string | null) {
  return value ? value.slice(0, 10) : '未设置'
}

function projectTasks(projectId: string) {
  return store.tasks.filter(task => task.project_id === projectId)
}

function coverStyle(project: Project) {
  const color = project.cover_color
  if (!color) return undefined
  const hex = color.length === 4
    ? `#${color[1]}${color[1]}${color[2]}${color[2]}${color[3]}${color[3]}`
    : color
  return { background: `linear-gradient(120deg, ${hex}33, ${hex}80)` }
}

const projectCards = computed(() =>
  store.projects.map(project => {
    const tasks = projectTasks(project.id)
    return {
      project,
      taskCount: tasks.length,
      activeCount: tasks.filter(task => task.status === 'in_progress').length,
    }
  }),
)
</script>

<template>
  <div class="page-wrap">
    <header class="page-header"><div><p class="eyebrow">Projects</p><h1>项目管理</h1><p>{{ store.projects.length }} 个项目 · 任务可自由选择归属</p></div><button class="btn-primary" @click="store.openProject()"><Plus :size="16" />新增项目</button></header>
    <div v-if="store.loading" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <div v-for="i in 3" :key="i" class="card p-4"><div class="skeleton h-12" /><div class="skeleton mt-3 h-3 w-1/3" /><div class="skeleton mt-3 h-3 w-full" /><div class="skeleton mt-2 h-3 w-4/5" /><div class="skeleton mt-3 h-5 w-2/3 rounded-full" /></div>
    </div>
    <div v-else-if="!store.projects.length" class="empty-state"><FolderKanban :size="28" /><h2>尚无项目</h2><p>立项后即可把相关任务挂到项目下，任务也可以不关联项目。</p><button class="btn-primary" @click="store.openProject()">新增项目</button></div>
    <section v-else class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <button v-for="item in projectCards" :key="item.project.id" class="card group text-left" @click="store.openProject(item.project)">
        <div class="project-cover" :style="coverStyle(item.project)">
          <span :class="['project-status', `project-status--${item.project.status}`]">{{ projectStatusMap[item.project.status] }}</span>
          <b class="truncate font-display text-base text-white">{{ item.project.name }}</b>
        </div>
        <p class="mt-3 font-mono text-[11px] text-muted">立项 {{ formatDate(item.project.started_at) }}</p>
        <p v-if="item.project.description" class="mt-2 line-clamp-2 text-xs leading-5 text-slate-300">{{ item.project.description }}</p>
        <p v-if="item.project.background" class="mt-2 line-clamp-2 text-[12px] leading-5 text-slate-400">{{ item.project.background }}</p>
        <div v-if="item.project.member_ids.length" class="mt-3 flex flex-wrap gap-1.5">
          <span v-for="memberId in item.project.member_ids.slice(0, 5)" :key="memberId" class="skill-chip">{{ store.memberMap.get(memberId)?.name ?? '?' }}</span>
          <span v-if="item.project.member_ids.length > 5" class="skill-chip">+{{ item.project.member_ids.length - 5 }}</span>
        </div>
        <div class="divider my-4" />
        <div class="flex justify-between font-mono text-[11px] text-muted"><span>{{ item.taskCount }} 任务 · {{ item.activeCount }} 进行中</span><span>{{ item.taskCount ? `${Math.round(item.taskCount / store.tasks.length * 100)}% 占比` : '暂无关联任务' }}</span></div>
      </button>
    </section>
  </div>
</template>
