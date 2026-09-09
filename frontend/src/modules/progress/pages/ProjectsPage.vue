<script setup lang="ts">
import { computed } from 'vue'
import { ArrowUpRight, CalendarDays, FolderKanban, Plus, Users }  from '@lucide/vue'
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
  const color = project.cover_color ?? '#2563eb'
  return { '--project-accent': /^#(?:[0-9a-f]{3}|[0-9a-f]{6})$/i.test(color) ? color : '#2563eb' }
}

const projectCards = computed(() =>
  store.projects.map(project => {
    const tasks = projectTasks(project.id)
    return {
      project,
      taskCount: tasks.length,
      completion: tasks.filter(task => task.status !== 'cancelled').length
        ? Math.round(tasks.filter(task => task.status === 'done').length / tasks.filter(task => task.status !== 'cancelled').length * 100)
        : 0,
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
    <section v-else class="entity-grid grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <button v-for="item in projectCards" :key="item.project.id" class="card entity-card project-card text-left" :style="coverStyle(item.project)" @click="store.openProject(item.project)">
        <div class="project-card-top">
          <span class="project-emblem"><FolderKanban :size="22" /></span>
          <span :class="['project-status', `project-status--${item.project.status}`]">{{ projectStatusMap[item.project.status] }}</span>
        </div>
        <h2 class="project-title">{{ item.project.name }}</h2>
        <p class="project-description">{{ item.project.description || item.project.background || '添加项目说明，让目标与协作方向更清晰。' }}</p>
        <p class="project-date"><CalendarDays :size="13" />立项 {{ formatDate(item.project.started_at) }}</p>
        <div class="project-members">
          <Users :size="14" />
          <span v-for="memberId in item.project.member_ids.slice(0, 3)" :key="memberId" class="skill-chip">{{ store.memberMap.get(memberId)?.name ?? '未知成员' }}</span>
          <span v-if="item.project.member_ids.length > 3" class="project-more-members">+{{ item.project.member_ids.length - 3 }}</span>
          <span v-if="!item.project.member_ids.length">暂未分配成员</span>
        </div>
        <div class="entity-footer project-card-footer">
          <div class="project-progress-label"><span>任务完成度</span><b>{{ item.taskCount ? `${item.completion}%` : '—' }}</b></div>
          <div class="project-progress" role="progressbar" aria-label="任务完成度（不含已取消任务）" :aria-valuenow="item.completion" :aria-valuemin="0" :aria-valuemax="100"><i :style="{ width: `${item.completion}%` }" /></div>
          <div class="project-card-meta"><span>{{ item.taskCount }} 任务 <span aria-hidden="true">·</span> {{ item.activeCount }} 进行中</span><span class="project-open">查看项目<ArrowUpRight :size="14" /></span></div>
        </div>
      </button>
    </section>
  </div>
</template>
