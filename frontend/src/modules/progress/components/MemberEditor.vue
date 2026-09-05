<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Save, Trash2, X } from '@lucide/vue'
import { useProgressStore } from '../store'
import { memberPixelUri } from '../pixel-avatar'
import {
  evaluationKindMap,
  type MemberEvaluationInput,
  type MemberEvaluationKind,
} from '../types'

const MAX_SKILLS = 20

const store = useProgressStore()
const form = reactive({ name: '', title: '', color: '#36d9e9', active: true, background: '' })
const skills = ref<string[]>([])
const skillDraft = ref('')
const title = computed(() => store.editingMember ? '编辑成员' : '新增成员')
const isOperator = computed(() => Boolean(store.editingMember?.operator))
const avatar = computed(() =>
  store.editingMember ? memberPixelUri(store.editingMember.id, form.color) : null,
)

const evaluationKind = ref<MemberEvaluationKind>('note')
const evaluationContent = ref('')
const evaluations = computed(() => [...(store.editingMember?.evaluations ?? [])].reverse())

const composing = ref(false)

function commitSkillText(text: string) {
  for (const part of text.split(/[,，]/)) {
    const skill = part.trim()
    if (!skill || skills.value.some(item => item.toLowerCase() === skill.toLowerCase())) continue
    if (skills.value.length >= MAX_SKILLS) break
    skills.value.push(skill)
  }
}

function onSkillInput() {
  if (composing.value) return
  if (/[，,]/.test(skillDraft.value)) {
    commitSkillText(skillDraft.value)
    skillDraft.value = ''
  }
}

function onSkillKeydown(event: KeyboardEvent) {
  if (event.isComposing || composing.value) return
  if (event.key === 'Enter') {
    event.preventDefault()
    if (skillDraft.value.trim()) {
      commitSkillText(skillDraft.value)
      skillDraft.value = ''
    }
  } else if (event.key === 'Backspace' && !skillDraft.value && skills.value.length) {
    skills.value.pop()
  }
}

function onCompositionEnd() {
  composing.value = false
  onSkillInput()
}

function removeSkill(index: number) {
  skills.value.splice(index, 1)
}

watch(() => store.memberEditorOpen, (open) => {
  if (!open) return
  const source = store.editingMember
  Object.assign(form, {
    name: source?.name ?? '',
    title: source?.title ?? '',
    color: source?.color ?? '#36d9e9',
    active: source ? (source.operator ? true : source.active) : true,
    background: source?.background ?? '',
  })
  skills.value = [...(source?.skills ?? [])]
  skillDraft.value = ''
  evaluationKind.value = 'note'
  evaluationContent.value = ''
})

async function submit() {
  await store.saveMember({ ...form, skills: [...skills.value] })
}

async function recordEvaluation() {
  if (!store.editingMember || !evaluationContent.value.trim()) return
  const payload: MemberEvaluationInput = {
    kind: evaluationKind.value,
    content: evaluationContent.value.trim(),
  }
  if (await store.addMemberEvaluation(store.editingMember.id, payload)) evaluationContent.value = ''
}

async function removeEvaluation(evaluationId: string) {
  if (!store.editingMember) return
  await store.removeMemberEvaluation(store.editingMember.id, evaluationId)
}

function formatTime(value: string) {
  return value.replace('T', ' ').slice(0, 16)
}
</script>

<template>
  <Teleport to="body">
    <div v-if="store.memberEditorOpen" class="fixed inset-0 z-50 bg-black/65" @click.self="store.memberEditorOpen = false">
      <aside class="editor-panel" role="dialog" aria-modal="true" :aria-label="title">
        <header class="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
          <div class="flex min-w-0 items-center gap-3">
            <img v-if="avatar" :src="avatar" alt="" width="36" height="36" class="member-avatar" />
            <div class="min-w-0">
              <p class="eyebrow">Team member</p>
              <h2 class="mt-1 truncate font-display text-xl text-white">{{ title }}</h2>
            </div>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <template v-if="store.editingMember">
              <span v-if="store.editingMember.operator" class="status-chip">本人</span>
              <span class="status-chip">{{ store.editingMember.active ? '可分配' : '停用' }}</span>
            </template>
            <button class="icon-btn" aria-label="关闭" @click="store.memberEditorOpen = false"><X :size="18" /></button>
          </div>
        </header>
        <form class="space-y-5 overflow-y-auto p-5" @submit.prevent="submit">
          <section class="space-y-4">
            <p class="eyebrow">基本信息</p>
            <div class="grid grid-cols-2 gap-3">
              <label class="field-label">姓名<input v-model="form.name" class="input" required maxlength="100" /></label>
              <label class="field-label">职位 / 角色<input v-model="form.title" class="input" maxlength="100" /></label>
            </div>
            <label class="field-label">识别色<span class="mt-2 flex items-center gap-3"><input v-model="form.color" type="color" class="h-10 w-14 rounded border border-line bg-transparent p-1" /><input v-model="form.color" class="input !mt-0 font-mono" /></span></label>
            <label class="flex items-center gap-3 text-xs text-slate-300"><input v-model="form.active" type="checkbox" class="accent-cyan" :disabled="isOperator" />成员当前可参与任务分配</label>
            <p v-if="isOperator" class="text-[11px] leading-5 text-muted">管理员对应的成员不能停用或删除，否则无法把任务分给自己。</p>
          </section>
          <section class="space-y-4 border-t border-line pt-5">
            <p class="eyebrow">能力与背景</p>
            <div class="field-label">技能
              <small>回车或逗号添加，点 × 移除；供 Pulse 匹配任务时参考，最多 20 个</small>
              <div class="skill-input">
                <span v-for="(skill, index) in skills" :key="skill" class="skill-chip">{{ skill }}<button type="button" class="skill-chip-remove" :aria-label="`移除技能 ${skill}`" @click="removeSkill(index)"><X :size="10" /></button></span>
                <input
                  v-model="skillDraft"
                  class="skill-input-field"
                  maxlength="40"
                  :placeholder="skills.length ? '继续添加…' : '工单对接, Python, 接口联调'"
                  @input="onSkillInput"
                  @keydown="onSkillKeydown"
                  @compositionstart="composing = true"
                  @compositionend="onCompositionEnd"
                />
              </div>
            </div>
            <label class="field-label">项目背景
              <small class="flex items-center justify-between gap-3"><span>做过什么、熟悉哪些系统或业务，帮助分配时说明理由</span><span class="font-mono">{{ form.background.length }}/2000</span></small>
              <textarea v-model="form.background" class="input min-h-28 py-3" maxlength="2000" placeholder="例如：主导过 MYAI 与 IT 工单系统联调，熟悉审批流和回调。" />
            </label>
          </section>
          <section v-if="store.editingMember" class="space-y-3 border-t border-line pt-5">
            <p class="eyebrow">评价记录</p>
            <p class="text-[11px] text-muted">随手记录对这位成员的观察；也可以直接在 AI 对话里说一句，让 Pulse 帮你记。</p>
            <div class="flex flex-wrap gap-1.5">
              <button v-for="(label, kind) in evaluationKindMap" :key="kind" type="button" :class="['kind-option', { 'kind-option--active': evaluationKind === kind }]" @click="evaluationKind = kind">{{ label }}</button>
            </div>
            <textarea v-model="evaluationContent" class="input min-h-20 py-3" maxlength="2000" placeholder="例如：本周主动接管 MYAI 联调，排查问题很稳。" />
            <button type="button" class="btn-secondary" :disabled="store.saving || !evaluationContent.trim()" @click="recordEvaluation">添加评价</button>
            <ol v-if="evaluations.length" class="entry-timeline">
              <li v-for="evaluation in evaluations" :key="evaluation.id" class="entry-item">
                <div class="flex items-center justify-between gap-2">
                  <span :class="['entry-kind', `entry-kind--${evaluation.kind}`]">{{ evaluationKindMap[evaluation.kind] }}</span>
                  <button type="button" class="icon-btn !h-6 !w-6" aria-label="删除这条评价" @click="removeEvaluation(evaluation.id)"><Trash2 :size="12" /></button>
                </div>
                <p class="whitespace-pre-wrap">{{ evaluation.content }}</p>
                <time>{{ formatTime(evaluation.created_at) }}</time>
              </li>
            </ol>
            <p v-else class="empty-inline !py-4">还没有评价</p>
          </section>
          <p v-else class="empty-inline !py-2">保存成员后即可随时补充评价记录。</p>
          <p v-if="store.error" class="error-box">{{ store.error }}</p>
          <footer class="flex justify-end gap-2 border-t border-line pt-5"><button v-if="store.editingMember && !isOperator" type="button" class="btn-danger mr-auto" :disabled="store.saving" @click="store.deleteMember(store.editingMember.id)"><Trash2 :size="14" />删除</button><button type="button" class="btn-secondary" @click="store.memberEditorOpen = false"><X :size="14" />取消</button><button class="btn-primary" :disabled="store.saving"><Save :size="14" />{{ store.saving ? '保存中…' : '保存成员' }}</button></footer>
        </form>
      </aside>
    </div>
  </Teleport>
</template>
