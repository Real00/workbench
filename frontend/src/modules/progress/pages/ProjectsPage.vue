<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowUpRight, ArrowUpDown, CalendarDays, FolderKanban, Plus, Search, Users } from '@lucide/vue'
import ChipSelect from '../../../shared/ChipSelect.vue'
import type { AppSelectOption } from '../../../shared/AppSelect.vue'
import { useProgressStore } from '../store'
import { projectStatusMap, type Project, type ProjectStatus } from '../types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const store = useProgressStore()

const statusOptions: AppSelectOption<ProjectStatus>[] = Object.entries(projectStatusMap).map(([value, label]) => ({
  value: value as ProjectStatus,
  label,
}))

/** 项目查找与排序（审计 A25）：默认按最近更新，项目变多后先按名称可查找 */
type ProjectSortId = 'updated' | 'created' | 'name'
const search = ref('')
const sort = ref<ProjectSortId>('updated')
const sortOptions: AppSelectOption<ProjectSortId>[] = [
  { value: 'updated', label: '最近更新 新→旧' },
  { value: 'created', label: '最近创建 新→旧' },
  { value: 'name', label: '名称 A→Z' },
]

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

async function onStatusChange(project: Project, status: ProjectStatus | null | undefined) {
  if (!status || status === project.status) return
  await store.patchProject(project.id, { status })
}

const query = computed(() => search.value.trim().toLowerCase())

/** 卡片指标拆成两套口径（审计 A24）：项目阶段看右上角状态，卡片底部只讲任务完成情况；
 *  没有可统计任务时 completion 为 null，不渲染进度条，避免看起来像 0% */
const projectCards = computed(() => {
  const rows = store.projects.map(project => {
    const tasks = projectTasks(project.id)
    const rated = tasks.filter(task => task.status !== 'cancelled')
    const doneCount = tasks.filter(task => task.status === 'done').length
    return {
      project,
      taskCount: tasks.length,
      doneCount,
      ratedCount: rated.length,
      completion: rated.length ? Math.round(doneCount / rated.length * 100) : null,
      activeCount: tasks.filter(task => task.status === 'in_progress').length,
    }
  })
  const filtered = query.value
    ? rows.filter(row =>
        [row.project.name, row.project.description, row.project.background, ...row.project.member_ids.map(id => store.memberMap.get(id)?.name ?? '')]
          .some(text => text?.toLowerCase().includes(query.value)))
    : rows
  const sorted = [...filtered]
  if (sort.value === 'updated') sorted.sort((left, right) => right.project.updated_at.localeCompare(left.project.updated_at))
  else if (sort.value === 'created') sorted.sort((left, right) => right.project.created_at.localeCompare(left.project.created_at))
  else sorted.sort((left, right) => left.project.name.localeCompare(right.project.name, 'zh-Hans-CN'))
  return sorted
})

function clearFilters() {
  search.value = ''
}
</script>

<template>
  <div class="page-wrap">
    <header class="page-header"><div><p class="eyebrow">Projects</p><h1>项目管理</h1><p>{{ store.projects.length }} 个项目 · 任务可自由选择归属</p></div><Button @click="store.openProject()"><Plus :size="16" />新增项目</Button></header>
    <div v-if="store.loading" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <div v-for="i in 3" :key="i" class="card p-4"><div class="skeleton h-12" /><div class="skeleton mt-3 h-3 w-1/3" /><div class="skeleton mt-3 h-3 w-full" /><div class="skeleton mt-2 h-3 w-4/5" /><div class="skeleton mt-3 h-5 w-2/3 rounded-full" /></div>
    </div>
    <div v-else-if="!store.projects.length" class="empty-state"><FolderKanban :size="28" /><h2>尚无项目</h2><p>立项后即可把相关任务挂到项目下，任务也可以不关联项目。</p><Button @click="store.openProject()">新增项目</Button></div>
    <template v-else>
      <!-- 搜索与排序（审计 A25）：项目变多后按名称即可定位 -->
      <div class="mb-4 flex flex-col gap-2 rounded-xl border border-line bg-panel p-2 md:flex-row md:items-center">
        <label class="search-box !h-8 !min-h-8 flex-1">
          <Search :size="15" />
          <span class="sr-only">搜索项目</span>
          <Input v-model="search" autocomplete="off" placeholder="搜索项目名称、描述或成员" class="!h-full !min-h-0 border-0 bg-transparent !p-0 shadow-none focus-visible:ring-0" />
        </label>
        <span class="flex items-center gap-1 text-xs text-muted-foreground md:shrink-0">
          <ArrowUpDown :size="13" aria-hidden="true" />
          <ChipSelect v-model="sort" :options="sortOptions" trigger-class="border-dashed bg-transparent font-normal text-muted-foreground hover:text-foreground" aria-label="项目排序方式" />
        </span>
        <span class="font-mono text-[11px] text-muted-foreground md:ml-auto">{{ projectCards.length }} / {{ store.projects.length }} 个项目</span>
      </div>
      <div v-if="!projectCards.length" class="empty-state"><FolderKanban :size="28" /><h2>没有匹配的项目</h2><p>换个关键词，或清除搜索后查看全部项目。</p><Button variant="outline" @click="clearFilters">清除搜索</Button></div>
    </template>
    <section v-if="!store.loading && projectCards.length" class="entity-grid grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <article
        v-for="item in projectCards"
        :key="item.project.id"
        class="card entity-card project-card text-left"
        :style="coverStyle(item.project)"
        role="button"
        tabindex="0"
        @click="store.openProject(item.project)"
        @keydown.enter="store.openProject(item.project)"
      >
        <div class="project-card-top">
          <span class="project-emblem"><FolderKanban :size="22" /></span>
          <div @click.stop title="项目阶段（点击可修改）">
            <ChipSelect
              :model-value="item.project.status"
              :options="statusOptions"
              :disabled="store.saving"
              :aria-label="`修改项目状态：${projectStatusMap[item.project.status]}`"
              @update:model-value="status => onStatusChange(item.project, status)"
            />
          </div>
        </div>
        <h2 class="project-title">{{ item.project.name }}</h2>
        <p class="project-description">{{ item.project.description || item.project.background || '添加项目说明，让目标与协作方向更清晰。' }}</p>
        <p class="project-date"><CalendarDays :size="13" />立项 {{ formatDate(item.project.started_at) }}</p>
        <div class="project-members">
          <Users :size="14" />
          <Badge v-for="memberId in item.project.member_ids.slice(0, 3)" :key="memberId" variant="secondary">{{ store.memberMap.get(memberId)?.name ?? '未知成员' }}</Badge>
          <span v-if="item.project.member_ids.length > 3" class="project-more-members">+{{ item.project.member_ids.length - 3 }}</span>
          <span v-if="!item.project.member_ids.length">暂未分配成员</span>
        </div>
        <div class="entity-footer project-card-footer">
          <!-- 项目阶段在右上角状态胶囊；这里只统计任务（审计 A24）：已完成/总数，无任务不画轨道 -->
          <div class="project-progress-label">
            <span>已完成任务</span>
            <b v-if="item.ratedCount">{{ item.doneCount }}/{{ item.ratedCount }}</b>
            <b v-else>—</b>
          </div>
          <div
            v-if="item.ratedCount"
            class="project-progress"
            role="progressbar"
            :aria-label="`任务完成度：已完成 ${item.doneCount} / 共 ${item.ratedCount} 个（不含已取消）`"
            :aria-valuenow="item.completion ?? 0"
            :aria-valuemin="0"
            :aria-valuemax="100"
          ><i :style="{ width: `${item.completion}%` }" /></div>
          <p v-else class="project-progress-none">暂无可统计的任务，不显示完成率</p>
          <div class="project-card-meta"><span>{{ item.taskCount }} 任务 <span aria-hidden="true">·</span> {{ item.activeCount }} 进行中</span><span class="project-open">查看项目<ArrowUpRight :size="14" /></span></div>
        </div>
      </article>
    </section>
  </div>
</template>

<style scoped>
/* 审计 A24：无任务的项目不渲染进度轨道，避免看起来像 0% 落后 */
.project-progress-none { margin-top: 9px; font-size: 12px; color: var(--muted-foreground); }
</style>
