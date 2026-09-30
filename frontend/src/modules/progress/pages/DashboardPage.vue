<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowUpRight, ChartNoAxesCombined, CheckCheck, CircleAlert, Play, Plus, Radio, TimerReset } from '@lucide/vue'
import { useProgressStore } from '../store'
import type { TaskListPrefs } from '../store'
import { entryKindMap } from '../types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { kindBadgeVariant } from '../../../shared/kind-badge'

const store = useProgressStore()
const router = useRouter()
const active = computed(() => store.tasks.filter(task => task.status === 'in_progress'))

function averageOf(tasks: { progress: number }[]) {
  return tasks.length ? Math.round(tasks.reduce((sum, task) => sum + task.progress, 0) / tasks.length) : 0
}

/** 平均完成度按「全部任务」口径统计 */
const progress = computed(() => averageOf(store.tasks))
/** 进行中口径单独统计，避免与全部任务口径混用（审计 A10） */
const activeProgress = computed(() => averageOf(active.value))
const risks = computed(() => store.dashboard?.member_workloads.filter(item => item.overdue_risk) ?? [])

/** 带口径下钻到任务视图：先写入共享的列表偏好，TaskList 挂载时会还原（审计 A10） */
function goToTasks(patch: Partial<TaskListPrefs>) {
  store.setTaskListPrefs({ status: '', priority: '', assignee: '', project: '', sort: '', overdueOnly: false, ...patch })
  void router.push('/progress/tasks')
}

const stats = computed(() => [
  {
    label: '平均完成度', value: `${progress.value}%`, delta: `全部任务 · 共 ${store.dashboard?.total ?? 0} 个`, tone: 'text-cyan', icon: ChartNoAxesCombined, kind: 'progress',
    action: '查看全部任务', go: () => goToTasks({}),
  },
  {
    label: '进行中任务', value: String(store.dashboard?.by_status.in_progress ?? 0),
    delta: active.value.length ? `进行中平均完成度 ${activeProgress.value}%` : '暂无进行中任务',
    tone: 'text-text', icon: Play, kind: 'active',
    action: '查看进行中任务', go: () => goToTasks({ status: 'in_progress' }),
  },
  {
    label: '已完成任务', value: String(store.dashboard?.by_status.done ?? 0), delta: '累计完成', tone: 'text-text', icon: CheckCheck, kind: 'done',
    action: '查看已完成任务', go: () => goToTasks({ status: 'done' }),
  },
  {
    label: '逾期任务', value: String(store.dashboard?.overdue ?? 0), delta: store.dashboard?.overdue ? '需优先跟进' : '暂无逾期', tone: 'text-warning', icon: CircleAlert, kind: 'risk',
    action: '查看逾期任务', go: () => goToTasks({ overdueOnly: true, sort: 'due' }),
  },
])

function openRecent(taskId: string) {
  const task = store.tasks.find(item => item.id === taskId)
  if (task) store.openTask(task)
}

function formatTime(iso: string) {
  const at = new Date(iso)
  if (Number.isNaN(at.getTime())) return ''
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${pad(at.getMonth() + 1)}-${pad(at.getDate())} ${pad(at.getHours())}:${pad(at.getMinutes())}`
}

const refreshedLabel = computed(() => {
  const at = store.dashboardRefreshedAt
  if (!at) return ''
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${pad(at.getHours())}:${pad(at.getMinutes())}`
})
</script>

<template>
  <div class="page-wrap dashboard-page">
    <header class="page-header">
      <div><p class="eyebrow">Live workspace data</p><h1>进度总览</h1><p>任务健康度与当前交付节奏</p></div>
      <Button @click="store.openTask()"><Plus :size="16" />新建任务</Button>
    </header>
    <div v-if="store.loading" class="space-y-5">
      <div class="grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2 xl:grid-cols-4">
        <div v-for="i in 4" :key="i" class="bg-panel p-5"><div class="skeleton h-3 w-20" /><div class="skeleton mt-4 h-8 w-16" /></div>
      </div>
      <div class="grid gap-5 lg:grid-cols-2"><div v-for="i in 2" :key="i" class="card p-5"><div class="skeleton h-4 w-28" /><div class="skeleton mt-4 h-24" /></div></div>
    </div>
    <div v-else-if="!store.tasks.length" class="empty-state"><Radio :size="28" /><h2>工作台尚无任务数据</h2><p>创建第一个任务后，这里会显示真实进度、风险与成员工作量。</p><Button @click="store.openTask()">新建任务</Button></div>
    <template v-else>
    <section class="metric-grid grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <!-- 指标卡可下钻：点击数字进入相同口径的任务集合（审计 A10） -->
      <button v-for="stat in stats" :key="stat.label" type="button" :class="['metric-card', `metric-card--${stat.kind}`, 'w-full cursor-pointer text-left transition-[border-color,box-shadow] hover:border-[#b9c7dc] hover:shadow-[0_4px_12px_rgb(16_24_40/0.06)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#2563eb]']" :aria-label="`${stat.label}：${stat.value}，点击${stat.action}`" :title="stat.action" @click="stat.go()">
        <div class="metric-card-head"><p class="metric-label">{{ stat.label }}</p><span class="metric-icon"><component :is="stat.icon" :size="18" /></span></div><p :class="['mt-3 font-display text-3xl font-semibold', stat.tone]">{{ stat.value }}</p>
        <p class="mt-2 font-mono text-[12px] text-muted-foreground">{{ stat.delta }}</p>
      </button>
    </section>
    <section class="dashboard-grid mt-5 grid gap-5 xl:grid-cols-[1.55fr_.8fr]">
      <article class="card">
        <div class="card-head"><div><h2>进行中的任务</h2><p class="mt-2 text-xs text-muted-foreground">关注当前推进与交付进度</p></div><Badge variant="secondary">{{ active.length }}</Badge></div>
        <template v-if="active.length">
          <!-- 仅统计进行中样本，不再复用全部任务口径（审计 A10） -->
          <div class="mt-6 flex items-center justify-between text-xs text-muted-foreground"><span>进行中任务平均完成度 · 样本 {{ active.length }} 个</span><span class="font-mono text-cyan">{{ activeProgress }}%</span></div>
          <div class="progress-line mt-3" role="progressbar" aria-label="进行中任务平均完成度" :aria-valuenow="activeProgress" :aria-valuemin="0" :aria-valuemax="100"><i :style="{ width: `${activeProgress}%` }" /></div>
          <div class="mt-8 space-y-3">
            <button v-for="task in active" :key="task.id" class="task-row w-full text-left" :aria-label="`打开任务详情：${task.title}`" @click="store.openTask(task)">
              <span class="priority-dot" /><span class="min-w-0 flex-1"><b>{{ task.title }}</b><small>{{ store.memberMap.get(task.assignee_id ?? '')?.name ?? '未分配' }}</small></span>
              <span class="font-mono text-xs text-cyan">{{ task.progress }}%</span><ArrowUpRight :size="14" class="text-muted-foreground" />
            </button>
          </div>
        </template>
        <!-- 零进行中：给出解释与下一步动作，而不是留白（审计 A11） -->
        <div v-else class="mt-6 flex min-h-[180px] flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-[#cbd2dc] px-6 py-8 text-center">
          <p class="text-sm text-text">暂无进行中任务</p>
          <p class="text-xs text-muted-foreground">当前口径下暂无统计对象</p>
          <div class="mt-3 flex flex-wrap justify-center gap-2">
            <Button variant="secondary" size="sm" @click="goToTasks({ status: 'done' })">查看已完成任务</Button>
            <Button size="sm" @click="store.openTask()"><Plus :size="14" />新建任务</Button>
          </div>
        </div>
      </article>
      <div class="space-y-5">
        <article class="card">
          <div class="card-head"><h2>风险摘要</h2><CircleAlert :size="17" class="text-warning" /></div>
          <div v-if="risks.length || store.dashboard?.overdue" class="mt-5 space-y-4">
            <div v-if="store.dashboard?.overdue">
              <button type="button" class="flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-[#f8faff]" :aria-label="`查看 ${store.dashboard.overdue} 个逾期任务`" @click="goToTasks({ overdueOnly: true, sort: 'due' })">
                <span class="text-sm text-text">{{ store.dashboard.overdue }} 个任务已逾期</span><ArrowUpRight :size="14" class="flex-none text-muted-foreground" />
              </button>
              <p class="mt-1 px-2 text-xs text-muted-foreground">逾期口径：截止日期早于今天且任务未完成</p>
            </div>
            <template v-for="risk in risks" :key="risk.member.id">
              <div class="divider mb-4" />
              <p class="text-sm text-text">{{ risk.member.name }} 有临期或逾期任务</p>
              <p class="mt-1 px-2 text-xs text-muted-foreground">{{ risk.current_tasks.length }} 个未完成任务 · 风险口径：3 天内截止且进度未达 100%</p>
              <div class="mt-2 space-y-2 px-2">
                <button v-for="task in risk.current_tasks.slice(0, 3)" :key="task.id" class="task-row w-full text-left" :aria-label="`打开任务详情：${task.title}`" @click="store.openTask(task)">
                  <span class="min-w-0 flex-1"><b>{{ task.title }}</b><small>截止 {{ task.due_date?.slice(0, 10) ?? '—' }} · 进度 {{ task.progress }}%</small></span>
                  <ArrowUpRight :size="13" class="flex-none text-muted-foreground" />
                </button>
                <p v-if="risk.current_tasks.length > 3" class="text-xs text-muted-foreground">等共 {{ risk.current_tasks.length }} 个未完成任务</p>
              </div>
            </template>
          </div>
          <p v-else class="empty-inline">当前没有识别到交付风险</p>
        </article>
        <article class="card">
          <div class="card-head">
            <h2>操作记录</h2>
            <span class="flex flex-none items-center gap-2 text-[11px] text-muted-foreground"><template v-if="refreshedLabel">数据更新于 {{ refreshedLabel }}</template><TimerReset :size="17" class="text-cyan" /></span>
          </div>
          <div v-if="store.dashboard?.recent_progress.length" class="mt-5 space-y-3">
            <button v-for="item in store.dashboard.recent_progress" :key="`${item.task_id}-${item.created_at}`" class="task-row w-full text-left" :aria-label="`打开任务详情：${item.task_title}`" @click="openRecent(item.task_id)">
              <Badge :variant="kindBadgeVariant(item.kind)">{{ entryKindMap[item.kind] }}</Badge>
              <span class="min-w-0 flex-1"><b>{{ item.task_title }}</b><small>{{ item.content }}</small></span>
              <time :datetime="item.created_at" class="flex-none font-mono text-[11px] text-muted-foreground" :title="`记录时间 ${item.created_at}`">{{ formatTime(item.created_at) }}</time>
            </button>
          </div>
          <p v-else class="empty-inline">暂无进度记录</p>
        </article>
      </div>
    </section>
    </template>
  </div>
</template>
