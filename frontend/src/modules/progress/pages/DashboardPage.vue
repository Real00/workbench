<script setup lang="ts">
import { computed } from 'vue'
import { ArrowUpRight, CircleAlert, Plus, Radio, TimerReset } from '@lucide/vue'
import { useProgressStore } from '../store'
import { entryKindMap } from '../types'

const store = useProgressStore()
const active = computed(() => store.tasks.filter(task => task.status === 'in_progress'))
const progress = computed(() => store.tasks.length ? Math.round(store.tasks.reduce((sum, task) => sum + task.progress, 0) / store.tasks.length) : 0)
const risks = computed(() => store.dashboard?.member_workloads.filter(item => item.overdue_risk) ?? [])
const stats = computed(() => [
  { label: '平均完成度', value: `${progress.value}%`, delta: `${store.dashboard?.total ?? 0} 个任务`, tone: 'text-cyan' },
  { label: '进行中任务', value: String(store.dashboard?.by_status.in_progress ?? 0), delta: `${store.members.filter(m => m.active).length} 位可分配成员`, tone: 'text-white' },
  { label: '已完成任务', value: String(store.dashboard?.by_status.done ?? 0), delta: '已完成', tone: 'text-white' },
  { label: '逾期任务', value: String(store.dashboard?.overdue ?? 0), delta: '需关注', tone: 'text-amber-300' },
])

function openRecent(taskId: string) {
  const task = store.tasks.find(item => item.id === taskId)
  if (task) store.openTask(task)
}
</script>

<template>
  <div class="page-wrap">
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
    <section class="grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2 xl:grid-cols-4">
      <article v-for="stat in stats" :key="stat.label" class="bg-panel p-5">
        <p class="metric-label">{{ stat.label }}</p><p :class="['mt-3 font-display text-3xl font-semibold', stat.tone]">{{ stat.value }}</p>
        <p class="mt-2 font-mono text-[11px] text-muted">{{ stat.delta }}</p>
      </article>
    </section>
    <section class="mt-5 grid gap-5 xl:grid-cols-[1.55fr_.8fr]">
      <article class="card">
        <div class="card-head"><div><p class="eyebrow">Iteration pulse</p><h2>迭代脉冲轨道</h2></div><span class="status-live"><Radio :size="12" /> API</span></div>
        <div class="mt-8 pulse-track pulse-track--large" :aria-label="`任务平均进度 ${progress}%`">
          <span class="pulse-progress" :style="{ width: `${progress}%` }" /><i v-for="n in 5" :key="n" :style="{ left: `${n * 17}%` }" />
        </div>
        <div class="mt-4 flex justify-between font-mono text-[10px] text-muted"><span>0%</span><span>{{ progress }}%</span><span>100%</span></div>
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
          <div class="card-head"><h2>风险摘要</h2><CircleAlert :size="17" class="text-amber-300" /></div>
          <div v-if="risks.length || store.dashboard?.overdue" class="mt-5 space-y-4">
            <div v-if="store.dashboard?.overdue"><p class="text-sm text-white">{{ store.dashboard.overdue }} 个任务已逾期</p><p class="mt-1 text-xs text-muted">请检查截止日期与任务进度</p></div>
            <div v-for="risk in risks" :key="risk.member.id"><div class="divider mb-4" /><p class="text-sm text-white">{{ risk.member.name }} 的任务临近截止</p><p class="mt-1 text-xs text-muted">{{ risk.current_tasks.length }} 个进行中任务</p></div>
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
