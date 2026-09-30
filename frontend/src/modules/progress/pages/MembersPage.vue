<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowUpDown, CircleCheck, Plus, Search, ShieldCheck, Users, X } from '@lucide/vue'
import ChipSelect from '../../../shared/ChipSelect.vue'
import type { AppSelectOption } from '../../../shared/AppSelect.vue'
import MemberDeskSprite from '../components/MemberDeskSprite.vue'
import { memberHasDeskWork } from '../pixel-avatar'
import { useProgressStore } from '../store'
import type { Member } from '../types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const store = useProgressStore()
const workloads = computed(() => new Map(store.dashboard?.member_workloads.map(item => [item.member.id, item]) ?? []))

/** 单成员负荷视图（审计 A26）：没有未完成任务时平均值与剩余工时都没有统计对象，用 null 表示而非 0 */
const memberViews = computed(() =>
  store.members.map(member => {
    const workload = workloads.value.get(member.id)
    const currentCount = workload?.current_tasks.length ?? 0
    return {
      member,
      currentCount,
      average: currentCount ? workload?.average_progress ?? null : null,
      remainingDays: currentCount ? workload?.estimated_remaining_days ?? null : null,
    }
  }))

/** 按技能 / 负荷找人（审计 A28）：搜索姓名、职位、技能与背景，可只看可分配并按负荷排序 */
type MemberSortId = '' | 'load' | 'remaining' | 'name'
const search = ref('')
const availableOnly = ref(false)
const sort = ref<MemberSortId>('')
const sortOptions: AppSelectOption<MemberSortId>[] = [
  { value: '', label: '默认顺序' },
  { value: 'load', label: '未完成任务 多→少' },
  { value: 'remaining', label: '剩余工时 多→少' },
  { value: 'name', label: '名称 A→Z' },
]
const query = computed(() => search.value.trim().toLowerCase())
const filtering = computed(() => Boolean(search.value.trim()) || availableOnly.value || sort.value !== '')
const displayMembers = computed(() => {
  let rows = memberViews.value
  if (availableOnly.value) rows = rows.filter(row => row.member.active)
  if (query.value) {
    rows = rows.filter(row =>
      [row.member.name, row.member.title, row.member.background, ...row.member.skills]
        .some(text => text?.toLowerCase().includes(query.value)))
  }
  if (sort.value === 'load') rows = [...rows].sort((left, right) => right.currentCount - left.currentCount)
  else if (sort.value === 'remaining') rows = [...rows].sort((left, right) => (right.remainingDays ?? 0) - (left.remainingDays ?? 0))
  else if (sort.value === 'name') rows = [...rows].sort((left, right) => left.member.name.localeCompare(right.member.name, 'zh-Hans-CN'))
  return rows
})

function clearFilters() {
  search.value = ''
  availableOnly.value = false
  sort.value = ''
}

/** 剩余工时口径已在后端核实：剩余预估工时之和 / 8 折算为工作日（backend/progress/application.py） */
const remainingHint = '剩余预估工时之和按 1 个工作日 = 8 小时折算'

function isBusy(memberId: string) {
  return memberHasDeskWork(workloads.value.get(memberId)?.current_tasks.length ?? 0)
}

async function toggleActive(member: Member) {
  if (member.operator || store.saving) return
  await store.patchMember(member.id, { active: !member.active })
}
</script>

<template>
  <div class="page-wrap members-page">
    <header class="page-header"><div><p class="eyebrow">People & capacity</p><h1>成员管理</h1><p>{{ store.members.length }} 位成员 · {{ store.members.filter(m => m.active).length }} 位可分配</p></div><Button @click="store.openMember()"><Plus :size="16" />新增成员</Button></header>
    <div v-if="store.loading" class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <div v-for="i in 4" :key="i" class="card p-4"><div class="skeleton h-[150px]" /><div class="skeleton mt-4 h-4 w-1/2" /><div class="skeleton mt-2 h-3 w-1/3" /><div class="skeleton mt-4 h-3 w-full" /><div class="skeleton mt-2 h-3 w-4/5" /></div>
    </div>
    <div v-else-if="!store.members.length" class="empty-state"><Users :size="28" /><h2>尚无团队成员</h2><p>新增成员后即可分配任务并查看工作量。</p><Button @click="store.openMember()">新增成员</Button></div>
    <template v-else>
      <!-- 搜索 / 可分配筛选 / 负荷排序（审计 A28），键盘可直接操作 -->
      <div class="mb-4 flex flex-col gap-2 rounded-xl border border-line bg-panel p-2 md:flex-row md:items-center">
        <label class="search-box !h-8 !min-h-8 flex-1">
          <Search :size="15" />
          <span class="sr-only">搜索成员</span>
          <Input v-model="search" autocomplete="off" placeholder="搜索姓名、职位或技能" class="!h-full !min-h-0 border-0 bg-transparent !p-0 shadow-none focus-visible:ring-0" />
        </label>
        <button
          type="button"
          :class="['inline-flex h-7 items-center gap-1 whitespace-nowrap rounded-lg border px-2 text-xs transition-colors',
                   availableOnly ? 'border-[#b2ccf7] bg-[#eff6ff] font-normal text-[#1d4ed8]' : 'border-dashed bg-transparent font-normal text-muted-foreground hover:text-foreground']"
          :aria-pressed="availableOnly"
          aria-label="仅看可分配成员"
          @click="availableOnly = !availableOnly"
        >
          <CircleCheck :size="13" aria-hidden="true" />仅看可分配
        </button>
        <span class="flex items-center gap-1 text-muted-foreground md:shrink-0">
          <ArrowUpDown :size="13" aria-hidden="true" />
          <ChipSelect v-model="sort" :options="sortOptions" trigger-class="border-dashed bg-transparent font-normal text-muted-foreground hover:text-foreground" aria-label="成员排序方式" />
        </span>
        <button v-if="filtering" type="button" class="btn-ghost btn-ghost--sm" @click="clearFilters"><X :size="13" />清除筛选</button>
        <span class="font-mono text-[11px] text-muted-foreground md:ml-auto">命中 {{ displayMembers.length }} / 共 {{ store.members.length }} 位</span>
      </div>
      <section v-if="displayMembers.length" class="entity-grid grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article
          v-for="row in displayMembers"
          :key="row.member.id"
          class="card entity-card member-card group text-left"
          role="button"
          tabindex="0"
          @click="store.openMember(row.member)"
          @keydown.enter="store.openMember(row.member)"
        >
          <div class="relative member-portrait">
            <MemberDeskSprite :seed="row.member.id" :name="row.member.name" :color="row.member.color" :busy="isBusy(row.member.id)" />
          </div>
          <span class="member-badges">
            <Badge v-if="row.member.operator" variant="secondary" class="status-tag">本人</Badge>
            <Badge
              as="button"
              type="button"
              variant="outline"
              :class="['status-tag', 'status-tag--interactive', row.member.active ? 'status-tag--active' : 'status-tag--inactive']"
              :disabled="row.member.operator || store.saving"
              :aria-label="row.member.operator ? '本人始终可分配' : `切换为${row.member.active ? '停用' : '可分配'}`"
              :title="row.member.operator ? '本人始终可分配' : '点击切换可分配状态'"
              @click.stop="toggleActive(row.member)"
            >
              <span aria-hidden="true" class="status-dot" :class="row.member.active ? 'status-dot--on' : 'status-dot--off'" />{{ row.member.active ? '可分配' : '停用' }}
            </Badge>
          </span>
          <h2 class="mt-3 font-display text-lg text-text">{{ row.member.name }}</h2>
          <p class="mt-1 text-xs text-muted-foreground">{{ row.member.title || '未设置职位' }}</p>
          <div v-if="row.member.skills.length" class="mt-3 flex flex-wrap gap-1.5">
            <Badge v-for="skill in row.member.skills.slice(0, 4)" :key="skill" variant="secondary">{{ skill }}</Badge>
            <Badge v-if="row.member.skills.length > 4" variant="outline">+{{ row.member.skills.length - 4 }}</Badge>
          </div>
          <p v-if="row.member.background" class="mt-3 line-clamp-2 text-[12px] leading-5 text-muted-foreground">{{ row.member.background }}</p>
          <div class="entity-footer"><div class="divider mb-4" />
          <div class="flex justify-between text-xs">
            <span class="text-muted-foreground" :title="row.currentCount ? `按当前 ${row.currentCount} 个未完成任务平均` : '当前没有未完成任务，暂无统计'">任务平均进度</span>
            <b class="text-text">{{ row.average === null ? '—' : `${row.average}%` }}</b>
          </div>
          <div v-if="row.average !== null" class="progress-line mt-2"><i :style="{ width: `${row.average}%`, backgroundColor: row.member.color ?? '#36d9e9' }" /></div>
          <div class="member-workload">
            <span :class="{ 'member-workload--idle': !row.currentCount }">{{ row.currentCount ? `${row.currentCount} 个未完成任务` : '空闲 · 暂无进行中任务' }}</span>
            <span>{{ row.member.evaluations?.length ?? 0 }} 条评价</span>
            <span :title="row.remainingDays === null ? undefined : remainingHint">{{ row.remainingDays === null ? '—' : `${row.remainingDays}d 剩余` }}</span>
          </div></div>
        </article>
      </section>
      <div v-else class="empty-state"><Users :size="28" /><h2>没有匹配的成员</h2><p>换个关键词，或清除筛选后查看全部成员。</p><Button variant="outline" @click="clearFilters">清除筛选</Button></div>
      <section class="mt-5">
        <article class="card member-summary"><div class="card-head"><div><p class="eyebrow">Completion</p><h2>成员任务完成度</h2></div><ShieldCheck :size="17" class="text-cyan" /></div>
          <div class="mt-6 space-y-5"><div v-for="row in memberViews" :key="row.member.id" class="grid grid-cols-[70px_1fr_42px] items-center gap-3 text-xs">
            <b class="truncate text-text">{{ row.member.name }}</b>
            <template v-if="row.average !== null">
              <div class="progress-line"><i :style="{ width: `${row.average}%`, backgroundColor: row.member.color ?? '#36d9e9' }" /></div>
              <span class="font-mono text-right text-muted-foreground">{{ row.average }}%</span>
            </template>
            <p v-else class="col-span-2 text-[12px] text-muted-foreground" title="当前没有未完成任务，暂无统计">空闲 · 暂无进行中任务</p>
          </div></div>
          <p class="mt-5 text-[12px] text-muted-foreground">平均进度按每位成员当前未完成任务计算；「Xd 剩余」为剩余预估工时之和，{{ remainingHint }}。</p>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped>
/* 审计 A27：像素头像保留但缩小，把卡片主面积还给工作量与状态信息 */
.members-page .member-portrait { height: 88px; }
/* 可分配开关的状态点：让控件像开关而不是普通标签（审计 A27） */
.status-dot { width: 6px; height: 6px; flex-shrink: 0; border-radius: 999px; }
.status-dot--on { background: #2563eb; }
.status-dot--off { background: #98a2b3; }
/* 空闲时的负荷胶囊用中性色，不与进行中的蓝色胶囊混淆（审计 A26） */
.members-page .member-workload > span.member-workload--idle { background: #f2f4f7; color: #667085; }
</style>
