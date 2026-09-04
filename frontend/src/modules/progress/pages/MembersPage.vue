<script setup lang="ts">
import { computed } from 'vue'
import { Plus, ShieldCheck, Users } from '@lucide/vue'
import MemberDeskSprite from '../components/MemberDeskSprite.vue'
import { memberHasDeskWork } from '../pixel-avatar'
import { useProgressStore } from '../store'

const store = useProgressStore()
const workloads = computed(() => new Map(store.dashboard?.member_workloads.map(item => [item.member.id, item]) ?? []))

function isBusy(memberId: string) {
  return memberHasDeskWork(workloads.value.get(memberId)?.current_tasks.length ?? 0)
}
</script>

<template>
  <div class="page-wrap">
    <header class="page-header"><div><p class="eyebrow">People & capacity</p><h1>成员管理</h1><p>{{ store.members.length }} 位成员 · {{ store.members.filter(m => m.active).length }} 位可分配</p></div><button class="btn-primary" @click="store.openMember()"><Plus :size="16" />新增成员</button></header>
    <div v-if="!store.loading && !store.members.length" class="empty-state"><Users :size="28" /><h2>尚无团队成员</h2><p>新增成员后即可分配任务并查看工作量。</p><button class="btn-primary" @click="store.openMember()">新增成员</button></div>
    <section class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <button v-for="member in store.members" :key="member.id" class="card group text-left" @click="store.openMember(member)">
        <div class="relative">
          <MemberDeskSprite :seed="member.id" :name="member.name" :color="member.color" :busy="isBusy(member.id)" />
          <span class="absolute top-2 right-2 flex gap-1.5">
            <span v-if="member.operator" class="status-chip">本人</span>
            <span class="status-chip">{{ member.active ? '可分配' : '停用' }}</span>
          </span>
        </div>
        <h2 class="mt-4 font-display text-lg text-white">{{ member.name }}</h2>
        <p class="mt-1 text-xs text-muted">{{ member.title || '未设置职位' }}</p>
        <div v-if="member.skills.length" class="mt-3 flex flex-wrap gap-1.5">
          <span v-for="skill in member.skills.slice(0, 4)" :key="skill" class="skill-chip">{{ skill }}</span>
          <span v-if="member.skills.length > 4" class="skill-chip">+{{ member.skills.length - 4 }}</span>
        </div>
        <p v-if="member.background" class="mt-3 line-clamp-2 text-[11px] leading-5 text-slate-400">{{ member.background }}</p>
        <div class="divider my-5" />
        <div class="flex justify-between text-xs"><span class="text-muted">任务平均进度</span><b class="text-white">{{ workloads.get(member.id)?.average_progress ?? 0 }}%</b></div>
        <div class="progress-line mt-2"><i :style="{ width: `${workloads.get(member.id)?.average_progress ?? 0}%`, backgroundColor: member.color ?? '#36d9e9' }" /></div>
        <div class="mt-4 flex justify-between font-mono text-[10px] text-muted"><span>{{ workloads.get(member.id)?.current_tasks.length ?? 0 }} 个进行任务</span><span>{{ member.evaluations?.length ?? 0 }} 条评价</span><span>{{ workloads.get(member.id)?.estimated_remaining_days ?? 0 }}d 剩余</span></div>
      </button>
    </section>
    <section v-if="store.members.length" class="mt-5">
      <article class="card"><div class="card-head"><div><p class="eyebrow">Team load</p><h2>容量分布</h2></div><ShieldCheck :size="17" class="text-cyan" /></div>
        <div class="mt-6 space-y-5"><div v-for="member in store.members" :key="member.id" class="grid grid-cols-[70px_1fr_42px] items-center gap-3 text-xs"><b class="truncate text-white">{{ member.name }}</b><div class="progress-line"><i :style="{ width: `${workloads.get(member.id)?.average_progress ?? 0}%`, backgroundColor: member.color ?? '#36d9e9' }" /></div><span class="font-mono text-right text-muted">{{ workloads.get(member.id)?.average_progress ?? 0 }}%</span></div></div>
      </article>
    </section>
  </div>
</template>
