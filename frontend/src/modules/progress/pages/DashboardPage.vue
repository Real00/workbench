<script setup lang="ts">
import { computed } from 'vue'
import { ArrowUpRight, ChartNoAxesCombined, CheckCheck, CircleAlert, Play, Plus, Radio, TimerReset } from '@lucide/vue'
import { useProgressStore } from '../store'
import { entryKindMap } from '../types'

const store = useProgressStore()
const active = computed(() => store.tasks.filter(task => task.status === 'in_progress'))
const progress = computed(() => store.tasks.length ? Math.round(store.tasks.reduce((sum, task) => sum + task.progress, 0) / store.tasks.length) : 0)
const risks = computed(() => store.dashboard?.member_workloads.filter(item => item.overdue_risk) ?? [])
const stats = computed(() => [
  { label: '平均完成度', value: `${progress.value}%`, delta: `${store.dashboard?.total ?? 0} 个任务`, tone: 'text-cyan', icon: ChartNoAxesCombined, kind: 'progress' },
  { label: '进行中任务', value: String(store.dashboard?.by_status.in_progress ?? 0), delta: `${store.members.filter(m => m.active).length} 位可分配成员`, tone: 'text-text', icon: Play, kind: 'active' },
  { label: '已完成任务', value: String(store.dashboard?.by_status.done ?? 0), delta: '累计完成', tone: 'text-text', icon: CheckCheck, kind: 'done' },
  { label: '逾期任务', value: String(store.dashboard?.overdue ?? 0), delta: store.dashboard?.overdue ? '需优先跟进' : '暂无逾期', tone: 'text-warning', icon: CircleAlert, kind: 'risk' },
])

function openRecent(taskId: string) {
  const task = store.tasks.find(item => item.id === taskId)
  if (task) store.openTask(task)
}
</script>

<template>
  <div class="page-wrap dashboard-page">
    <header class="page-header">
      <div><p class="eyebrow">Live workspace data</p><h1>进度总览</h1><p>任务健康度与当前交付节奏</p></div>
      <button class="btn-primary" @click="store.openTask()"><Plus :size="16" />新建任务</button>
    </header>
    <div v-if="store.loading" class="space-y-5">
      <div class="grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2 xl:grid-cols-4">
        <div v-for="i in 4" :key="i" class="bg-panel p-5"><div class="skeleton h-3 w-20" /><div class="skeleton mt-4 h-8 w-16" /></div>
      </div>
      <div class="grid gap-5 lg:grid-cols-2"><div v-for="i in 2" :key="i" class="card p-5"><div class="skeleton h-4 w-28" /><div class="skeleton mt-4 h-24" /></div></div>
    </div>
    <div v-else-if="!store.tasks.length" class="empty-state"><Radio :size="28" /><h2>工作台尚无任务数据</h2><p>创建第一个任务后，这里会显示真实进度、风险与成员工作量。</p><button class="btn-primary" @click="store.openTask()">新建任务</button></div>
    <template v-else>
    <section class="metric-grid grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <article v-for="stat in stats" :key="stat.label" :class="['metric-card', `metric-card--${stat.kind}`]">
        <div class="metric-card-head"><p class="metric-label">{{ stat.label }}</p><span class="metric-icon"><component :is="stat.icon" :size="18" /></span></div><p :class="['mt-3 font-display text-3xl font-semibold', stat.tone]">{{ stat.value }}</p>
        <p class="mt-2 font-mono text-[12px] text-muted">{{ stat.delta }}</p>
      </article>
    </section>
    <section class="dashboard-grid mt-5 grid gap-5 xl:grid-cols-[1.55fr_.8fr]">
      <article class="card">
        <div class="card-head"><div><h2>进行中的任务</h2><p class="mt-2 text-xs text-muted">关注当前推进与交付进度</p></div><span class="count-badge">{{ active.length }}</span></div>
        <div class="mt-6 flex items-center justify-between text-xs text-muted"><span>全部任务平均完成度</span><span class="font-mono text-cyan">{{ progress }}%</span></div>
        <div class="progress-line mt-3" role="progressbar" aria-label="全部任务平均完成度" :aria-valuenow="progress" :aria-valuemin="0" :aria-valuemax="100"><i :style="{ width: `${progress}%` }" /></div>
        <div class="mt-8 space-y-3">
          <button v-for="task in active" :key="task.id" class="task-row w-full text-left" @click="store.openTask(task)">
            <span class="priority-dot" /><span class="min-w-0 flex-1"><b>{{ task.title }}</b><small>{{ task.id.slice(0, 8) }} · {{ store.memberMap.get(task.assignee_id ?? '')?.name ?? '未分配' }}</small></span>
            <span class="font-mono text-xs text-cyan">{{ task.progress }}%</span><ArrowUpRight :size="14" class="text-muted" />
          </button>
          <p v-if="!active.length" class="empty-inline">暂无进行中任务</p>
        </div>
      </article>
      <div class="space-y-5">
        <article class="card">
          <div class="card-head"><h2>风险摘要</h2><CircleAlert :size="17" class="text-warning" /></div>
          <div v-if="risks.length || store.dashboard?.overdue" class="mt-5 space-y-4">
            <div v-if="store.dashboard?.overdue"><p class="text-sm text-text">{{ store.dashboard.overdue }} 个任务已逾期</p><p class="mt-1 text-xs text-muted">请检查截止日期与任务进度</p></div>
            <div v-for="risk in risks" :key="risk.member.id"><div class="divider mb-4" /><p class="text-sm text-text">{{ risk.member.name }} 有临期或逾期任务</p><p class="mt-1 text-xs text-muted">{{ risk.current_tasks.length }} 个未完成任务</p></div>
          </div><p v-else class="empty-inline">当前没有识别到交付风险</p>
        </article>
        <article class="card"><div class="card-head"><h2>操作记录</h2><TimerReset :size="17" class="text-cyan" /></div>
          <div v-if="store.dashboard?.recent_progress.length" class="mt-5 space-y-3">
            <button v-for="item in store.dashboard.recent_progress" :key="`${item.task_id}-${item.created_at}`" class="task-row w-full text-left" @click="openRecent(item.task_id)">
              <span :class="['entry-kind', `entry-kind--${item.kind}`]">{{ entryKindMap[item.kind] }}</span>
              <span class="min-w-0 flex-1"><b>{{ item.task_title }}</b><small>{{ item.content }}</small></span>
            </button>
          </div>
          <p v-else class="empty-inline">暂无进度记录</p>
        </article>
      </div>
    </section>
    </template>
  </div>
</template>
