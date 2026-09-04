<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { Bot, Check, ChevronDown, MessageSquarePlus, RotateCcw, Send, Sparkles, Square, Wrench, X } from '@lucide/vue'
import { apiError } from './api/client'
import { pulseApi } from './pulse-api'
import { useKnowledgeStore } from '../modules/knowledge/store'
import { useProgressStore } from '../modules/progress/store'
import {
  entryKindMap,
  evaluationKindMap,
  priorityMap,
  projectStatusMap,
  statusMap,
  type AiOperation,
  type AiStreamEvent,
  type AiToolEvent,
  type Priority,
  type ProgressEntryKind,
  type ProjectStatus,
  type TaskStatus,
} from '../modules/progress/types'

interface ChatTurn {
  id: number
  role: 'user' | 'assistant'
  text: string
  thinking: string
  tools: AiToolEvent[]
  operations: AiOperation[]
  token: string | null
  error: string
  applied: boolean
  instruction: string
}

const progress = useProgressStore()
const knowledge = useKnowledgeStore()
const open = ref(false)
const instruction = ref('')
const loading = ref(false)
const confirming = ref(false)
const turns = ref<ChatTurn[]>([])
const error = ref('')
const sessionId = ref<string | null>(null)
const scroller = ref<HTMLElement | null>(null)
let seq = 0
let abort: AbortController | null = null
const STREAM_TIMEOUT_MS = 240_000
const abortMessage = ref('已中断')
const labels: Record<string, string> = {
  title: '标题', description: '描述', status: '状态', priority: '优先级', assignee_id: '负责人',
  start_date: '开始日期', due_date: '截止日期', progress: '进度', estimated_hours: '预估工时', tags: '标签',
  name: '姓名', skills: '技能', background: '项目背景',
  key: '键', value: '值', aliases: '别名', explanation: '解释', body: '正文',
}
const toolLabels: Record<string, string> = {
  list_tasks: '查看任务',
  list_members: '查看成员',
  get_task: '读取任务',
  create_task: '排队创建任务',
  update_task: '排队更新任务',
  add_progress_entry: '排队记录',
  create_member: '排队新增成员',
  update_member: '排队更新成员',
  record_member_evaluation: '排队记录评价',
  create_project: '排队创建项目',
  update_project: '排队更新项目',
  search_knowledge: '检索知识',
  read_knowledge: '阅读知识',
  list_tags: '查看标签',
  list_entries: '查看条目',
  create_tag: '排队创建标签',
  create_entry: '排队创建条目',
  update_entry: '排队更新条目',
  create_document: '排队创建文档',
  update_document: '排队更新文档',
  link_entry: '排队关联条目',
}

function display(field: string, value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  if (field === 'assignee_id') return progress.memberMap.get(String(value))?.name ?? String(value)
  if (field === 'status') return statusMap[value as TaskStatus] ?? String(value)
  if (field === 'priority') return priorityMap[value as Priority] ?? String(value)
  if (Array.isArray(value)) return value.join(', ')
  return String(value)
}

function taskTitle(id: string) {
  return progress.tasks.find(task => task.id === id)?.title ?? '匹配任务'
}

function memberName(id: string) {
  return progress.memberMap.get(id)?.name ?? '成员'
}

function projectName(id: string) {
  return progress.projects.find(project => project.id === id)?.name ?? '项目'
}

function operationLabel(operation: AiOperation) {
  if (operation.op === 'create_task') return `创建「${String(operation.changes.title ?? '新任务')}」`
  if (operation.op === 'add_entry') {
    return `在「${taskTitle(operation.task_id)}」记录${entryKindMap[operation.entry.kind]}`
  }
  if (operation.op === 'add_member_evaluation') {
    return `给「${memberName(operation.member_id)}」记录${evaluationKindMap[operation.evaluation.kind]}`
  }
  if (operation.op === 'create_project') return `创建项目「${String(operation.changes.name ?? '新项目')}」`
  if (operation.op === 'update_project') return `更新项目「${projectName(operation.project_id)}」`
  if (operation.op === 'create_member') return `新增成员「${String(operation.changes.name ?? '未命名')}」`
  if (operation.op === 'update_member') return `更新成员「${memberName(operation.member_id)}」`
  if (operation.op === 'create_tag') return `创建标签「${String(operation.changes.name ?? '标签')}」`
  if (operation.op === 'create_entry') return `创建条目「${String(operation.changes.key ?? '条目')}」`
  if (operation.op === 'update_entry') return '更新知识条目'
  if (operation.op === 'create_document') return `创建文档「${String(operation.changes.title ?? '文档')}」`
  if (operation.op === 'update_document') return '更新知识文档'
  if (operation.op === 'link_entry') return '把条目挂到文档'
  if (operation.op === 'update_task') return `更新「${taskTitle(operation.task_id)}」`
  return operation.op
}

function operationChanges(operation: AiOperation) {
  if (operation.op === 'add_entry' || operation.op === 'link_entry') return []
  if (operation.op === 'create_project' || operation.op === 'update_project') return []
  if ('changes' in operation) return Object.entries(operation.changes)
  return []
}

interface ProjectChangeRow { label: string; text: string; color?: string }

function projectChangeRows(operation: Extract<AiOperation, { op: 'create_project' | 'update_project' }>) {
  const changes = operation.changes
  const rows: ProjectChangeRow[] = []
  if (typeof changes.status === 'string' && changes.status in projectStatusMap) {
    rows.push({ label: '状态', text: projectStatusMap[changes.status as ProjectStatus] })
  }
  if (typeof changes.started_at === 'string' && changes.started_at) {
    rows.push({ label: '立项', text: changes.started_at })
  }
  if (typeof changes.cover_color === 'string' && changes.cover_color) {
    rows.push({ label: '封面色', text: changes.cover_color, color: changes.cover_color })
  }
  if (Array.isArray(changes.member_ids)) {
    const names = (changes.member_ids as string[]).map(id => memberName(id)).join('、')
    if (names) rows.push({ label: '成员', text: names })
  }
  for (const field of ['description', 'background'] as const) {
    if (typeof changes[field] === 'string' && changes[field]) {
      rows.push({ label: field === 'description' ? '描述' : '背景', text: String(changes[field]).slice(0, 60) })
    }
  }
  return rows
}

async function scrollBottom() {
  await nextTick()
  scroller.value?.scrollTo({ top: scroller.value.scrollHeight })
}

async function send() {
  const text = instruction.value.trim()
  if (!text || loading.value) return
  instruction.value = ''
  await runTurn(text)
}

async function retry(turn: ChatTurn) {
  if (loading.value || !turn.instruction) return
  await runTurn(turn.instruction)
}

function newConversation() {
  if (loading.value) return
  sessionId.value = null
  turns.value = []
  error.value = ''
}

async function runTurn(text: string) {
  abort?.abort()
  abort = new AbortController()
  abortMessage.value = '已中断'
  loading.value = true
  error.value = ''
  turns.value.push({ id: ++seq, role: 'user', text, thinking: '', tools: [], operations: [], token: null, error: '', applied: false, instruction: text })
  turns.value.push({
    id: ++seq, role: 'assistant', text: '', thinking: '', tools: [], operations: [], token: null, error: '', applied: false, instruction: text,
  })
  const assistant = turns.value[turns.value.length - 1]!
  await scrollBottom()
  const timeoutId = window.setTimeout(() => {
    abortMessage.value = '请求超时，已中断'
    abort?.abort()
  }, STREAM_TIMEOUT_MS)
  try {
    await pulseApi.run(
      {
        instruction: text,
        session_id: sessionId.value,
        ...(progress.editingTask && { context_task_id: progress.editingTask.id }),
        ...(knowledge.editingDocument && { context_document_id: knowledge.editingDocument.id }),
      },
      (event: AiStreamEvent) => {
        if (event.type === 'text') assistant.text += event.delta
        if (event.type === 'thinking') assistant.thinking += event.delta
        if (event.type === 'tool') {
          const current = assistant.tools.find(item => item.name === event.name && item.status === 'start')
          if (current && event.status !== 'start') {
            current.status = event.status
            current.result = event.result
          } else {
            assistant.tools.push({ name: event.name, status: event.status, args: event.args, result: event.result })
          }
        }
        if (event.type === 'done') {
          assistant.operations = event.operations
          assistant.token = event.confirmation_token
          if (event.session_id) sessionId.value = event.session_id
        }
        if (event.type === 'cancelled') assistant.error = event.message || '已中断'
        if (event.type === 'error') assistant.error = event.message
        void scrollBottom()
      },
      abort.signal,
    )
  } catch (cause) {
    if ((cause as { name?: string }).name === 'AbortError') {
      assistant.error = assistant.error || abortMessage.value
      return
    }
    assistant.error = apiError(cause)
  } finally {
    window.clearTimeout(timeoutId)
    loading.value = false
    abort = null
  }
}

function stop() {
  abortMessage.value = '已中断'
  abort?.abort()
}

async function confirm(turn: ChatTurn) {
  if (!turn.token) return
  confirming.value = true
  error.value = ''
  try {
    await pulseApi.confirm(turn.token)
    await Promise.all([progress.initialize(), knowledge.initialize()])
    if (progress.editingTask) {
      const fresh = progress.tasks.find(task => task.id === progress.editingTask?.id)
      if (fresh) progress.editingTask = fresh
    }
    if (progress.editingMember) {
      const fresh = progress.members.find(member => member.id === progress.editingMember?.id)
      if (fresh) progress.editingMember = fresh
    }
    if (knowledge.editingDocument) {
      const fresh = knowledge.documents.find(item => item.id === knowledge.editingDocument?.id)
      if (fresh) knowledge.editingDocument = fresh
    }
    turn.applied = true
    turn.token = null
  } catch (cause) {
    error.value = apiError(cause)
  } finally {
    confirming.value = false
  }
}

function discard(turn: ChatTurn) {
  turn.token = null
  turn.operations = []
}
</script>

<template>
  <section :class="['ai-dock', open && 'ai-dock--open']" aria-label="Pulse AI 助手">
    <button v-if="!open" class="ai-trigger" @click="open = true">
      <span class="relative"><Sparkles :size="17" /><i /></span>
      <b>Pulse AI</b>
      <small>直接描述，流式回复后再确认</small>
      <ChevronDown class="ml-auto rotate-180" :size="16" />
    </button>
    <template v-else>
      <header class="flex items-center gap-3 border-b border-line px-4 py-3">
        <span class="grid size-8 place-items-center rounded-lg bg-cyan/10 text-cyan"><Bot :size="17" /></span>
        <div>
          <b class="text-sm text-white">Pulse AI</b>
          <p class="text-[10px] text-muted">{{ sessionId ? '多轮对话中，可指代上文' : '工具会排队变更，确认后才写入' }}</p>
        </div>
        <button class="icon-btn ml-auto" :disabled="loading" :aria-label="sessionId ? '清空对话，开始新会话' : '新对话'" :title="sessionId ? '清空历史，开始新会话' : '新对话'" @click="newConversation"><MessageSquarePlus :size="16" /></button>
        <button class="icon-btn" aria-label="收起助手" @click="open = false"><X :size="16" /></button>
      </header>
      <div ref="scroller" class="ai-transcript">
        <p v-if="!turns.length" class="empty-inline !py-8">可以说任务、成员，或让我检索知识库。例如「登录页卡在验证码超时」或「grep 工单对接」。</p>
        <article v-for="turn in turns" :key="turn.id" :class="['ai-turn', `ai-turn--${turn.role}`]">
          <p v-if="turn.role === 'user'" class="ai-bubble ai-bubble--user">{{ turn.text }}</p>
          <template v-else>
            <div v-if="turn.tools.length" class="ai-tools">
              <span v-for="(tool, index) in turn.tools" :key="`${tool.name}-${index}`" :class="['ai-tool', `ai-tool--${tool.status}`]">
                <Wrench :size="11" />{{ toolLabels[tool.name] ?? tool.name }}
              </span>
            </div>
            <div v-if="turn.thinking" class="ai-think">
              <b>思考过程</b>
              <p>{{ turn.thinking }}<span v-if="loading && turn === turns.at(-1) && !turn.text" class="ai-cursor" /></p>
            </div>
            <p v-if="turn.text" class="ai-bubble ai-bubble--assistant">{{ turn.text }}<span v-if="loading && turn === turns.at(-1)" class="ai-cursor" /></p>
            <p v-else-if="loading && turn === turns.at(-1) && !turn.thinking" class="ai-bubble ai-bubble--assistant text-muted">正在调用模型…<span class="ai-cursor" /></p>
            <div v-if="turn.operations.length" class="ai-ops">
              <article v-for="(operation, index) in turn.operations" :key="`${operation.op}-${index}`" class="rounded-lg border border-line bg-panel-2 p-3">
                <b class="text-xs text-white">{{ operationLabel(operation) }}</b>
                <p v-if="operation.op === 'add_entry'" class="mt-2 text-xs text-white">
                  <span :class="['entry-kind', `entry-kind--${operation.entry.kind}`]">{{ entryKindMap[operation.entry.kind as ProgressEntryKind] }}</span>
                  <span class="ml-2">{{ operation.entry.content }}</span>
                </p>
                <p v-if="operation.op === 'add_member_evaluation'" class="mt-2 text-xs text-white">
                  <span :class="['entry-kind', `entry-kind--${operation.evaluation.kind}`]">{{ evaluationKindMap[operation.evaluation.kind] }}</span>
                  <span class="ml-2">{{ operation.evaluation.content }}</span>
                </p>
                <p v-if="operation.op === 'create_project' || operation.op === 'update_project'" class="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                  <span v-for="row in projectChangeRows(operation)" :key="row.label" class="flex items-center gap-1.5 text-[11px] text-muted">
                    {{ row.label }}
                    <span v-if="row.color" class="size-2.5 rounded-full" :style="{ backgroundColor: row.color }" />
                    <span class="text-white">{{ row.text }}</span>
                  </span>
                </p>
                <p v-for="[field, after] in operationChanges(operation)" :key="field" class="mt-2 text-[11px] text-muted">
                  {{ labels[field] ?? field }}
                  <span class="ml-1 text-white">{{ display(field, after) }}</span>
                </p>
              </article>
            </div>
            <div v-if="turn.token && turn.operations.length && !turn.applied" class="mt-3 flex justify-end gap-2">
              <button class="btn-secondary" @click="discard(turn)">放弃</button>
              <button class="btn-primary" :disabled="confirming" @click="confirm(turn)">
                <Check :size="14" />{{ confirming ? '应用中…' : '确认应用' }}
              </button>
            </div>
            <div v-if="turn.applied" class="success-box mt-3"><Check :size="15" />变更已应用并刷新数据</div>
            <div v-if="turn.error && !loading" class="mt-3 flex justify-end">
              <button class="btn-secondary" @click="retry(turn)"><RotateCcw :size="13" />重试</button>
            </div>
            <p v-if="turn.error" class="error-box mt-3" role="alert">{{ turn.error }}</p>
          </template>
        </article>
        <p v-if="error" class="error-box" role="alert">{{ error }}</p>
      </div>
      <form class="flex gap-2 border-t border-line p-3" @submit.prevent="send">
        <label class="sr-only" for="ai-prompt">输入调整要求</label>
        <input id="ai-prompt" v-model="instruction" class="input !mt-0 flex-1" placeholder="描述任务、成员或知识库变更..." :disabled="loading" />
        <button v-if="loading" type="button" class="btn-secondary shrink-0" @click="stop">
          <Square :size="12" fill="currentColor" />中断
        </button>
        <button v-else class="btn-primary shrink-0" :disabled="!instruction.trim()">
          <Send :size="15" />发送
        </button>
      </form>
    </template>
  </section>
</template>
