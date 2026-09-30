<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  CheckCircle2,
  FlaskConical,
  LoaderCircle,
  Pencil,
  Plus,
  Power,
  Sparkles,
  Trash2,
  X,
} from '@lucide/vue'
import { api, apiError } from '../../shared/api/client'
import { confirmDialog } from '../../shared/confirm'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'

interface Skill {
  id: string
  name: string
  trigger: string
  instructions: string
  script: string | null
  enabled: boolean
  updated_at: string
}

const MAX_SKILLS = 12

const SAMPLE_SCRIPT = `from ai_settings.skill_runtime.base import PulseSkill, SkillPayload

class MySkill(PulseSkill):
    def execute(self, payload: SkillPayload):
        # payload.instruction：用户本轮的原始请求
        # payload.arguments：模型传入的字符串键值
        return {"summary": "在这里返回可 JSON 序列化的结果"}`

const skills = ref<Skill[]>([])
const loading = ref(true)
const error = ref('')
const notice = ref('')
const editingId = ref<string | null>(null) // null = 新建；'' = 未编辑
const editorOpen = ref(false)
const saving = ref(false)
const testing = ref(false)
const testOutput = ref<{ ok: boolean; text: string } | null>(null)
const togglingId = ref('')
const deletingId = ref('')

const form = reactive({
  name: '',
  trigger: '',
  instructions: '',
  script: '',
})

onMounted(load)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get<Skill[]>('/ai-settings/skills')
    skills.value = data
  } catch (cause) { error.value = apiError(cause) }
  finally { loading.value = false }
}

function startCreate() {
  editingId.value = null
  form.name = ''
  form.trigger = ''
  form.instructions = ''
  form.script = ''
  testOutput.value = null
  editorOpen.value = true
}

function startEdit(skill: Skill) {
  editingId.value = skill.id
  form.name = skill.name
  form.trigger = skill.trigger
  form.instructions = skill.instructions
  form.script = skill.script ?? ''
  testOutput.value = null
  editorOpen.value = true
}

function closeEditor() {
  editorOpen.value = false
  editingId.value = null
}

function formIssue(): string | null {
  if (!form.name.trim()) return '请填写技能名称'
  if (!form.trigger.trim()) return '请填写触发说明'
  if (!form.instructions.trim()) return '请填写指令内容'
  return null
}

async function save() {
  const issue = formIssue()
  if (issue) { error.value = issue; return }
  saving.value = true
  error.value = ''
  notice.value = ''
  testOutput.value = null
  try {
    const body = {
      name: form.name.trim(),
      trigger: form.trigger.trim(),
      instructions: form.instructions,
      script: form.script.trim() ? form.script : null,
      enabled: true,
    }
    if (editingId.value) {
      await api.put(`/ai-settings/skills/${editingId.value}`, body)
      notice.value = `技能「${body.name}」已更新`
    } else {
      await api.post('/ai-settings/skills', body)
      notice.value = `技能「${body.name}」已创建`
    }
    closeEditor()
    await load()
  } catch (cause) { error.value = apiError(cause) }
  finally { saving.value = false }
}

async function runTest() {
  if (!form.script.trim()) {
    testOutput.value = { ok: false, text: '先填写技能脚本再试运行' }
    return
  }
  testing.value = true
  testOutput.value = null
  try {
    const { data } = await api.post<{ result: unknown }>('/ai-settings/skills/test', {
      script: form.script,
      instruction: form.trigger || '试运行',
    }, { timeout: 60_000 })
    const text = JSON.stringify(data.result, null, 2)
    testOutput.value = { ok: true, text: text.length > 2000 ? `${text.slice(0, 2000)}…` : text }
  } catch (cause) {
    testOutput.value = { ok: false, text: apiError(cause) }
  } finally {
    testing.value = false
  }
}

async function toggle(skill: Skill) {
  togglingId.value = skill.id
  error.value = ''
  try {
    await api.put(`/ai-settings/skills/${skill.id}`, {
      name: skill.name,
      trigger: skill.trigger,
      instructions: skill.instructions,
      script: skill.script,
      enabled: !skill.enabled,
    })
    await load()
  } catch (cause) { error.value = apiError(cause) }
  finally { togglingId.value = '' }
}

async function remove(skill: Skill) {
  const ok = await confirmDialog({
    title: `删除技能「${skill.name}」？`,
    message: '删除后立即生效，Pulse 将不再收到该技能的指令与脚本工具。',
    confirmText: '删除技能',
    danger: true,
  })
  if (!ok) return
  deletingId.value = skill.id
  error.value = ''
  try {
    await api.delete(`/ai-settings/skills/${skill.id}`)
    await load()
  } catch (cause) { error.value = apiError(cause) }
  finally { deletingId.value = '' }
}
</script>

<template>
  <section class="card p-5">
    <div class="card-head">
      <div>
        <p class="eyebrow">Skills</p>
        <h2>自定义技能</h2>
        <p class="mt-2 text-xs text-muted-foreground">技能由「触发说明 + Markdown 指令」组成：当请求匹配触发说明时，指令会注入给 Pulse 作为工作方式参考；可选绑定一个沙箱脚本让 Pulse 直接执行。</p>
      </div>
      <div class="flex items-center gap-2">
        <Badge variant="outline">最多 {{ MAX_SKILLS }} 个</Badge>
        <Sparkles :size="17" class="text-cyan" />
      </div>
    </div>

    <p v-if="loading" class="empty-inline mt-5">正在读取技能…</p>
    <template v-else>
      <div v-if="!skills.length && !editorOpen" class="empty-state mt-5 gap-2 p-8">
        <Sparkles :size="22" class="text-muted-foreground" />
        <p class="text-sm font-medium text-text">还没有技能</p>
        <p class="max-w-md text-[12px] leading-5">创建第一个技能：填写触发说明与 Markdown 指令，Pulse 会在匹配的请求中采纳它。</p>
      </div>

      <div v-if="skills.length" class="mt-5 space-y-3">
        <article v-for="skill in skills" :key="skill.id" class="rounded-lg border border-line bg-panel-2 p-3">
          <header class="flex flex-wrap items-start justify-between gap-2">
            <div class="min-w-0">
              <b class="flex flex-wrap items-center gap-2 text-sm text-text">
                {{ skill.name }}
                <Badge v-if="!skill.enabled" variant="outline" class="text-muted-foreground">已停用</Badge>
                <Badge v-if="skill.script" variant="outline" class="border-warning/40 text-[11px] text-warning">绑定脚本</Badge>
              </b>
              <p class="mt-1 text-[12px] leading-5 text-muted-foreground">触发：{{ skill.trigger }}</p>
            </div>
            <div class="flex shrink-0 items-center gap-1">
              <Button type="button" variant="ghost" size="icon" :aria-label="skill.enabled ? `停用技能 ${skill.name}` : `启用技能 ${skill.name}`" :disabled="togglingId === skill.id" @click="toggle(skill)">
                <LoaderCircle v-if="togglingId === skill.id" :size="15" class="animate-spin" /><Power v-else :size="15" :class="skill.enabled ? 'text-success' : 'text-muted-foreground'" />
              </Button>
              <Button type="button" variant="ghost" size="icon" :aria-label="`编辑技能 ${skill.name}`" @click="startEdit(skill)"><Pencil :size="15" /></Button>
              <Button type="button" variant="ghost" size="icon" :aria-label="`删除技能 ${skill.name}`" :disabled="deletingId === skill.id" @click="remove(skill)">
                <LoaderCircle v-if="deletingId === skill.id" :size="15" class="animate-spin" /><Trash2 v-else :size="15" class="text-danger" />
              </Button>
            </div>
          </header>
          <p class="mt-2 line-clamp-2 text-[12px] leading-5 text-text-secondary">{{ skill.instructions }}</p>
        </article>
      </div>

      <div v-if="editorOpen" class="mt-5 space-y-4 rounded-xl border border-line p-4">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <h3 class="text-sm font-semibold text-text">{{ editingId ? '编辑技能' : '新建技能' }}</h3>
          <Button type="button" variant="ghost" size="icon" aria-label="关闭编辑器" @click="closeEditor"><X :size="15" /></Button>
        </div>
        <label class="field-label">名称<Input v-model="form.name" :maxlength="48" autocomplete="off" placeholder="周报整理" /><small>展示用名称；同名（不区分大小写）技能不能重复。</small></label>
        <label class="field-label">触发说明<Input v-model="form.trigger" :maxlength="400" autocomplete="off" placeholder="当用户要求整理周报或汇总项目进度时" /><small>描述什么情况下应用本技能；Pulse 会据此判断是否采纳下面的指令。</small></label>
        <label class="field-label">指令（Markdown）<Textarea v-model="form.instructions" :maxlength="8000" class="min-h-28 font-mono text-[13px]" placeholder="1. 按项目分组汇总本周进展&#10;2. 标注阻塞项与下周计划" /><small>匹配触发时注入给 Pulse 的工作方式说明；是对平台规则的细化，不是覆盖。</small></label>
        <div class="field-label">
          <span class="flex flex-wrap items-center justify-between gap-2">
            可执行脚本（可选）
            <Button type="button" v-if="!form.script" variant="link" class="h-auto px-0 text-[12px] font-semibold" @click="form.script = SAMPLE_SCRIPT">填入模板</Button>
          </span>
          <Textarea v-model="form.script" :maxlength="40000" class="min-h-40 font-mono text-[12px]" placeholder="留空则本技能只注入指令。绑定脚本后，Pulse 可在对话中直接调用执行。" />
          <small>在服务端沙箱子进程执行：白名单环境变量、30 秒超时、128KB 输出上限；须定义 PulseSkill 子类并返回可 JSON 序列化结果。保存后请先「试运行」验证。</small>
        </div>
        <p v-if="testOutput" class="text-[12px] font-medium" :class="testOutput.ok ? 'text-success' : 'text-danger'" :role="testOutput.ok ? 'status' : 'alert'">
          {{ testOutput.ok ? '试运行结果：' : '试运行失败：' }}
        </p>
        <pre v-if="testOutput" class="max-h-52 overflow-auto rounded-lg border border-line bg-ink p-3 font-mono text-[12px] leading-5 text-text-secondary">{{ testOutput.text }}</pre>
        <p v-if="error" class="error-box" role="alert">{{ error }}</p>
        <footer class="flex flex-wrap justify-end gap-2 border-t border-line pt-4">
          <Button v-if="form.script.trim()" type="button" variant="outline" :disabled="testing || saving" @click="runTest">
            <LoaderCircle v-if="testing" :size="15" class="animate-spin" /><FlaskConical v-else :size="15" />{{ testing ? '运行中…' : '试运行脚本' }}
          </Button>
          <Button :disabled="saving || testing" @click="save">
            <LoaderCircle v-if="saving" :size="15" class="animate-spin" /><CheckCircle2 v-else :size="15" />{{ saving ? '保存中…' : editingId ? '保存修改' : '创建技能' }}
          </Button>
        </footer>
      </div>

      <p v-if="!editorOpen && error" class="error-box mt-4" role="alert">{{ error }}</p>
      <p v-if="notice && !editorOpen" class="success-box mt-4"><CheckCircle2 :size="14" />{{ notice }}</p>

      <footer v-if="!editorOpen" class="mt-4 flex flex-wrap justify-end gap-2 border-t border-line pt-5">
        <Button v-if="skills.length < MAX_SKILLS" type="button" @click="startCreate"><Plus :size="15" />新建技能</Button>
        <Badge v-else variant="outline" class="text-muted-foreground">已达上限 {{ MAX_SKILLS }} 个</Badge>
      </footer>
    </template>
  </section>
</template>
