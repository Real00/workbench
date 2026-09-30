<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Bot, Check, Code, Copy, FileText, Maximize2, MessageSquarePlus, Minimize2, Paperclip, Pencil, RotateCcw, Send, Sparkles, Square, Undo2, Wrench, X } from '@lucide/vue'
import { api, apiError } from './api/client'
import { pulseApi } from './pulse-api'
import {
  defaultAttachmentPrompt,
  dropTurnsFrom,
  filesFromDataTransfer,
  findUserTurn,
  isPulseAttachmentMeta,
  isSupportedPulseAttachment,
  namedPastedFile,
  PULSE_ATTACHMENT_ACCEPT,
  PULSE_MAX_ATTACHMENT_BYTES,
  PULSE_MAX_ATTACHMENTS,
  rewindCompletedExchanges,
  type PulseAttachmentMeta,
} from './pulse-session'
import { IME_ENTER_GUARD_MS, isImeKeyEvent } from './ime'
import { moduleNavigation } from '../app/modules'
import { useKnowledgeStore } from '../modules/knowledge/store'
import { useProgressStore } from '../modules/progress/store'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import MarkdownView from './MarkdownView.vue'
import { kindBadgeVariant } from './kind-badge'
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
  type Task,
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
  /** 用户已放弃该轮待写入变更：保留预览但明确「未写入」 */
  discarded: boolean
  instruction: string
  attachments: PulseAttachmentMeta[]
  completed: boolean
}

const progress = useProgressStore()
const knowledge = useKnowledgeStore()
const emit = defineEmits<{ 'open-change': [open: boolean]; 'wide-change': [wide: boolean] }>()
const open = ref(false)
const WIDE_KEY = 'pulse-ai-wide-v1'
const wide = ref(false)
watch(open, value => emit('open-change', value))
watch(wide, value => {
  emit('wide-change', value)
  try { localStorage.setItem(WIDE_KEY, value ? '1' : '0') } catch { /* 忽略 */ }
})
const instruction = ref('')
const loading = ref(false)
const confirming = ref(false)
const turns = ref<ChatTurn[]>([])
const error = ref('')
const sessionId = ref<string | null>(null)
const scroller = ref<HTMLElement | null>(null)
const promptRef = ref<HTMLTextAreaElement | null>(null)
const fileRef = ref<HTMLInputElement | null>(null)
const editRef = ref<HTMLTextAreaElement | null>(null)
const promptEl = computed(() => promptRef.value)
const pendingAttachments = ref<PulseAttachmentMeta[]>([])
const uploading = ref(false)
const dragging = ref(false)
const editingUserTurnId = ref<number | null>(null)
const editDraft = ref('')
const imeComposing = ref(false)
let imeGuardUntil = 0
const route = useRoute()
let seq = 0
let abort: AbortController | null = null
const STREAM_TIMEOUT_MS = 240_000
const STORAGE_KEY = 'pulse-ai-session-v1'

function onImeCompositionStart() {
  imeComposing.value = true
}

function onImeCompositionEnd() {
  imeComposing.value = false
  // macOS：选中候选的 Enter 往往落在 compositionend 之后，短时内不触发发送
  imeGuardUntil = performance.now() + IME_ENTER_GUARD_MS
}

function imeBusy(event: KeyboardEvent) {
  return isImeKeyEvent(event, imeComposing.value, imeGuardUntil)
}

type MentionType = 'task' | 'member' | 'project' | 'document' | 'tool'
interface MentionCandidate { type: MentionType; id: string | null; label: string; hint?: string }
interface MentionPayload { type: MentionType; id: string | null; label: string }

const TYPE_LABELS: Record<MentionType, string> = {
  task: '任务', member: '成员', project: '项目', document: '知识', tool: '工具',
}
const MENTION_RE = /@(任务|成员|项目|知识|工具):「([^」]+)」/g
/** 候选按类型排序展示；每类先截取前几条，避免单一类型把 12 个席位占满 */
const MENTION_TYPE_ORDER: MentionType[] = ['task', 'member', 'project', 'document', 'tool']
const MENTION_POOL_PER_TYPE = 6
const MENTION_MAX_CANDIDATES = 12

const mentionQuery = ref<string | null>(null)
const mentionIndex = ref(0)
const toolRegistry = ref<{ name: string; description: string }[]>([])

function mentionTaskRank(task: Task) {
  return task.status === 'in_progress' ? 2 : task.status === 'todo' ? 1 : 0
}

const allCandidates = computed<MentionCandidate[]>(() => {
  const projectNameOf = (id: string | null) => (id ? progress.projects.find(project => project.id === id)?.name : '') ?? ''
  const memberNameOf = (id: string | null) => (id ? progress.memberMap.get(id)?.name : '') ?? ''
  const tasks = [...progress.tasks]
    .sort((left, right) => mentionTaskRank(right) - mentionTaskRank(left) || right.updated_at.localeCompare(left.updated_at))
    .map(task => ({
      type: 'task' as const,
      id: task.id,
      label: task.title,
      hint: [statusMap[task.status], projectNameOf(task.project_id), memberNameOf(task.assignee_id)].filter(Boolean).join(' · '),
    }))
  const documents = [...knowledge.documents]
    .sort((left, right) => (right.updated_at ?? '').localeCompare(left.updated_at ?? ''))
    .map(document => ({
      type: 'document' as const,
      id: document.id,
      label: document.title,
      hint: document.updated_at ? `更新于 ${document.updated_at.slice(0, 10)}` : '知识文档',
    }))
  return [
    ...tasks,
    ...progress.members.map(member => ({ type: 'member' as const, id: member.id, label: member.name, hint: member.title || undefined })),
    ...progress.projects.map(project => ({ type: 'project' as const, id: project.id, label: project.name, hint: projectStatusMap[project.status] })),
    ...documents,
    ...toolRegistry.value.map(tool => ({ type: 'tool' as const, id: null, label: tool.name, hint: tool.description })),
  ]
})

const mentionCandidates = computed<MentionCandidate[]>(() => {
  if (mentionQuery.value === null) return []
  const query = mentionQuery.value.trim().toLowerCase()
  const pool = query
    ? allCandidates.value.filter(candidate => candidate.label.toLowerCase().includes(query))
    : allCandidates.value
  const perType = new Map<MentionType, number>()
  const capped: MentionCandidate[] = []
  for (const candidate of pool) {
    const count = perType.get(candidate.type) ?? 0
    if (count >= MENTION_POOL_PER_TYPE) continue
    perType.set(candidate.type, count + 1)
    capped.push(candidate)
  }
  // 当前页正在编辑的对象置顶；其余按类型分节（类型内保持上面的活跃/最近顺序）
  const contextIds = new Set<string>()
  if (progress.editingTask) contextIds.add(progress.editingTask.id)
  if (knowledge.editingDocument) contextIds.add(knowledge.editingDocument.id)
  const contextFirst = (candidate: MentionCandidate) => (candidate.id && contextIds.has(candidate.id) ? 0 : 1)
  const typeOrder = (candidate: MentionCandidate) => MENTION_TYPE_ORDER.indexOf(candidate.type)
  return [...capped]
    .sort((left, right) => contextFirst(left) - contextFirst(right) || typeOrder(left) - typeOrder(right))
    .slice(0, MENTION_MAX_CANDIDATES)
})

/** 渲染用分组：startIndex 让键盘高亮索引与扁平候选列表保持一致 */
const mentionGroups = computed(() => {
  const groups: { type: MentionType; label: string; startIndex: number; items: MentionCandidate[] }[] = []
  let index = 0
  for (const candidate of mentionCandidates.value) {
    const last = groups[groups.length - 1]
    if (last && last.type === candidate.type) last.items.push(candidate)
    else groups.push({ type: candidate.type, label: TYPE_LABELS[candidate.type], startIndex: index, items: [candidate] })
    index += 1
  }
  return groups
})

async function ensureToolRegistry() {
  if (toolRegistry.value.length) return
  try {
    const { data } = await api.get<{ modules: { tools: { name: string; description: string }[] }[] }>('/ai-settings/tools')
    toolRegistry.value = data.modules.flatMap(module => module.tools)
  } catch {
    toolRegistry.value = []
  }
}

function updateMentionQuery() {
  const el = promptEl.value
  if (!el) {
    mentionQuery.value = null
    return
  }
  const upToCaret = el.value.slice(0, el.selectionStart ?? el.value.length)
  const match = upToCaret.match(/@([^@\n「」]*)$/)
  mentionQuery.value = match ? match[1] : null
  mentionIndex.value = 0
  if (match) void ensureToolRegistry()
}

function selectMention(candidate: MentionCandidate) {
  const el = promptEl.value
  if (!el) return
  const caret = el.selectionStart ?? el.value.length
  const before = el.value.slice(0, caret)
  const match = before.match(/@([^@\n「」]*)$/)
  mentionQuery.value = null
  if (!match) return
  const token = `@${TYPE_LABELS[candidate.type]}:「${candidate.label}」`
  const start = caret - match[0].length
  instruction.value = before.slice(0, start) + token + ' ' + el.value.slice(caret)
  void nextTick(() => {
    const pos = start + token.length + 1
    el.focus()
    el.setSelectionRange(pos, pos)
  })
}

function extractMentions(text: string): MentionPayload[] {
  const payloads: MentionPayload[] = []
  const seen = new Set<string>()
  for (const match of text.matchAll(MENTION_RE)) {
    const typeKey = match[1] as keyof typeof TYPE_LABELS
    const type = (Object.keys(TYPE_LABELS) as MentionType[]).find(key => TYPE_LABELS[key] === typeKey)
    if (!type) continue
    const label = match[2]
    const key = `${type}:${label}`
    if (seen.has(key)) continue
    seen.add(key)
    const found = allCandidates.value.find(candidate => candidate.type === type && candidate.label === label)
    payloads.push({ type, id: found?.id ?? null, label })
  }
  return payloads
}

const contextChips = computed(() => {
  const chips: string[] = []
  if (progress.taskEditorOpen && progress.editingTask) chips.push(`关联任务：${progress.editingTask.title}`)
  if (knowledge.documentEditorOpen && knowledge.editingDocument) chips.push(`关联文档：${knowledge.editingDocument.title}`)
  return chips
})

/** 当前所在页面，让用户知道助手能看到哪些上下文（与侧栏命名一致） */
const currentPageLabel = computed(() => {
  const path = route.path
  const matches = moduleNavigation
    .flatMap(group => group.items.map(item => ({ label: item.label, to: item.to })))
    .filter(item => (item.to === '/' ? path === '/' : path.startsWith(item.to)))
    .sort((left, right) => right.to.length - left.to.length)
  return matches[0]?.label ?? null
})

const quickTemplates = computed<string[]>(() => {
  const path = route.path
  const extras = pendingAttachments.value.length ? ['把附件存进知识库'] : []
  const task = progress.editingTask
  const document_ = knowledge.editingDocument
  const taskRef = task ? `@任务:「${task.title}」` : ''
  const docRef = document_ ? `@知识:「${document_.title}」` : ''
  if (path.startsWith('/progress/members')) {
    const who = progress.editingMember ? `@成员:「${progress.editingMember.name}」` : '「姓名」'
    return [...extras, `给${who}记一条亮点评价：今天…`, `把${who}的技能更新为：`, '新建成员：姓名、职位…']
  }
  if (path.startsWith('/progress/projects')) {
    return [...extras, '立项新项目「名称」：一句话背景…', '把项目「名称」的状态改为：进行中', '给项目「名称」补充背景：…']
  }
  if (path.startsWith('/progress/tasks')) {
    return [...extras,
      taskRef ? `在${taskRef}记录一条进展：今天完成了…` : '新建任务：标题…，负责人与截止…',
      taskRef ? `把${taskRef}的状态改为：` : '分析一个想法：…，帮我拆解成任务',
      '检索知识库：…',
    ]
  }
  if (path.startsWith('/knowledge')) {
    return [...extras,
      docRef ? `总结${docRef}的要点` : '检索知识库：…',
      '在知识库新建条目：名称…，内容…',
      '新建知识文档：标题…',
    ]
  }
  return [...extras, '新建任务：标题…，负责人与截止…', '分析一个想法：…，帮我拆解成任务', '检索知识库：…']
})

const canSend = computed(() => (
  !loading.value && !uploading.value && Boolean(instruction.value.trim() || pendingAttachments.value.length)
))

const lastAssistantId = computed(() => (
  [...turns.value].reverse().find(turn => turn.role === 'assistant')?.id ?? null
))
const rawAssistantIds = ref<Set<number>>(new Set())
const copiedTurnId = ref<number | null>(null)
let copiedTimer: number | null = null

const pendingTurn = computed(
  () => [...turns.value].reverse().find(turn => turn.token && turn.operations.length && !turn.applied && !turn.discarded) ?? null,
)

function applyTemplate(template: string) {
  instruction.value = instruction.value ? `${instruction.value.trimEnd()} ${template}` : template
  void nextTick(() => {
    promptEl.value?.focus()
    promptEl.value?.setSelectionRange(instruction.value.length, instruction.value.length)
  })
}

function autosizePrompt() {
  const el = promptEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 160)}px`
}

function onPromptKeydown(event: KeyboardEvent) {
  if (imeBusy(event)) return
  const menuOpen = mentionQuery.value !== null && mentionCandidates.value.length > 0
  if (menuOpen) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      mentionIndex.value = (mentionIndex.value + 1) % mentionCandidates.value.length
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      mentionIndex.value = (mentionIndex.value + mentionCandidates.value.length - 1) % mentionCandidates.value.length
      return
    }
    if (event.key === 'Enter' || event.key === 'Tab') {
      event.preventDefault()
      const candidate = mentionCandidates.value[mentionIndex.value]
      if (candidate) selectMention(candidate)
      return
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      mentionQuery.value = null
      return
    }
  }
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    if (canSend.value) void send()
    return
  }
  if (event.key === 'ArrowUp' && !instruction.value && !pendingAttachments.value.length) {
    const last = [...turns.value].reverse().find(turn => turn.role === 'user' && turn.text)
    if (last) {
      event.preventDefault()
      startEdit(last)
    }
  }
}

function onDockKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && editingUserTurnId.value !== null && mentionQuery.value === null) {
    event.preventDefault()
    cancelEdit()
    return
  }
  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
    const turn = pendingTurn.value
    if (turn && !confirming.value) {
      event.preventDefault()
      void confirm(turn)
    }
  }
}

function onGlobalKeydown(event: KeyboardEvent) {
  // Ctrl/⌘+K 已让位给命令面板，AI 助手呼出改为 Ctrl/⌘+I
  if ((event.metaKey || event.ctrlKey) && !event.shiftKey && !event.altKey && event.key.toLowerCase() === 'i') {
    event.preventDefault()
    if (loading.value) return
    open.value = !open.value
    if (open.value) void nextTick(() => promptEl.value?.focus())
  }
}

function composeCapture(event: Event) {
  const text = (event as CustomEvent<string>).detail
  if (typeof text !== 'string') return
  open.value = true
  instruction.value = instruction.value.trim() ? `${instruction.value}\n\n${text}` : text
  void nextTick(() => { autosizePrompt(); promptEl.value?.focus() })
}

function persistSession() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      sessionId: sessionId.value,
      turns: turns.value.slice(-100),
      draft: instruction.value,
      draftAttachments: pendingAttachments.value,
    }))
  } catch { /* localStorage 不可用时静默跳过 */ }
}

function restoreTurn(item: unknown): ChatTurn | null {
  if (!item || typeof item !== 'object') return null
  const turn = item as Partial<ChatTurn>
  if (typeof turn.text !== 'string' || (turn.role !== 'user' && turn.role !== 'assistant')) return null
  return {
    id: Number(turn.id) || 0,
    role: turn.role,
    text: turn.text,
    thinking: typeof turn.thinking === 'string' ? turn.thinking : '',
    tools: Array.isArray(turn.tools) ? turn.tools : [],
    operations: Array.isArray(turn.operations) ? turn.operations : [],
    token: typeof turn.token === 'string' ? turn.token : null,
    error: typeof turn.error === 'string' ? turn.error : '',
    applied: Boolean(turn.applied),
    discarded: Boolean(turn.discarded),
    instruction: typeof turn.instruction === 'string' ? turn.instruction : turn.text,
    attachments: Array.isArray(turn.attachments) ? turn.attachments.filter(isPulseAttachmentMeta) : [],
    completed: Boolean(turn.completed),
  }
}

function restoreSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const data = JSON.parse(raw) as { sessionId?: unknown; turns?: unknown; draft?: unknown; draftAttachments?: unknown }
    if (typeof data.sessionId === 'string') sessionId.value = data.sessionId
    if (Array.isArray(data.turns)) {
      turns.value = data.turns.map(restoreTurn).filter((item): item is ChatTurn => item !== null)
      seq = turns.value.reduce((max, item) => Math.max(max, Number(item.id) || 0), 0)
    }
    if (typeof data.draft === 'string' && data.draft) instruction.value = data.draft
    if (Array.isArray(data.draftAttachments)) {
      pendingAttachments.value = data.draftAttachments.filter(isPulseAttachmentMeta)
    }
  } catch { /* 数据损坏时丢弃，重新开始 */ }
}

onMounted(() => {
  restoreSession()
  try { wide.value = localStorage.getItem(WIDE_KEY) === '1' } catch { /* 忽略 */ }
  window.addEventListener('keydown', onGlobalKeydown)
  window.addEventListener('pulse-compose', composeCapture)
  void nextTick(() => autosizePrompt())
})
onUnmounted(() => {
  window.removeEventListener('keydown', onGlobalKeydown)
  window.removeEventListener('pulse-compose', composeCapture)
  if (copiedTimer) window.clearTimeout(copiedTimer)
})
watch([turns, sessionId, instruction, pendingAttachments], persistSession, { deep: true })
const abortMessage = ref('已中断')
const labels: Record<string, string> = {
  title: '标题', description: '描述', status: '状态', priority: '优先级', assignee_id: '负责人',
  start_date: '开始日期', due_date: '截止日期', progress: '进度', estimated_hours: '预估工时', tags: '标签',
  project_id: '所属项目',
  name: '姓名', skills: '技能', background: '项目背景', active: '可分配', color: '头像色',
  key: '名称', value: '内容', aliases: '别名', explanation: '解释', body: '正文',
  tag_ids: '标签', entry_ids: '关联条目', document_ids: '关联文档', member_ids: '成员',
}

function fieldLabel(operation: AiOperation, field: string) {
  // 「name」在成员/标签变更中含义不同
  if (field === 'name' && (operation.op === 'create_tag' || operation.op === 'update_tag')) return '标签名'
  return labels[field] ?? field
}
const toolLabels: Record<string, string> = {
  list_tasks: '查看任务',
  list_projects: '查看项目',
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
  update_tag: '排队更新标签',
  create_entry: '排队创建条目',
  update_entry: '排队更新条目',
  create_document: '排队创建文档',
  save_attachment_as_document: '排队存为知识文档',
  read_attachment: '阅读附件',
  update_document: '排队更新文档',
  link_entry: '排队关联条目',
}

function idListText(value: unknown, resolve: (id: string) => string | undefined) {
  if (!Array.isArray(value)) return String(value)
  if (!value.length) return '—'
  return value.map(id => resolve(String(id)) ?? id).join('、')
}

function display(field: string, value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  if (field === 'project_id') return progress.projects.find(project => project.id === String(value))?.name ?? String(value)
  if (field === 'assignee_id') return progress.memberMap.get(String(value))?.name ?? String(value)
  if (field === 'status') return statusMap[value as TaskStatus] ?? String(value)
  if (field === 'priority') return priorityMap[value as Priority] ?? String(value)
  if (field === 'document_ids') return idListText(value, id => knowledge.documents.find(item => item.id === id)?.title)
  if (field === 'entry_ids') return idListText(value, id => knowledge.entryMap.get(id)?.key)
  if (field === 'tag_ids') return idListText(value, id => knowledge.tagMap.get(id)?.name)
  if (field === 'member_ids') return idListText(value, id => progress.memberMap.get(id)?.name)
  if (typeof value === 'boolean') return value ? '是' : '否'
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

function entryKey(id: string) {
  return knowledge.entryMap.get(id)?.key ?? '知识条目'
}

function documentTitle(id: string) {
  return knowledge.documents.find(item => item.id === id)?.title ?? '知识文档'
}

function tagName(id: string, changes: Record<string, unknown>) {
  return knowledge.tagMap.get(id)?.name ?? String(changes.name ?? '标签')
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
  if (operation.op === 'update_tag') return `更新标签「${tagName(operation.tag_id, operation.changes)}」`
  if (operation.op === 'create_entry') return `创建条目「${String(operation.changes.key ?? '条目')}」`
  if (operation.op === 'update_entry') return `更新条目「${entryKey(operation.entry_id)}」`
  if (operation.op === 'create_document') return `创建文档「${String(operation.changes.title ?? '文档')}」`
  if (operation.op === 'create_document_from_attachment') {
    return `把「${operation.filename}」存为知识文档「${String(operation.changes.title ?? '文档')}」`
  }
  if (operation.op === 'update_document') return `更新文档「${documentTitle(operation.document_id)}」`
  if (operation.op === 'link_entry') return `把条目「${entryKey(operation.entry_id)}」关联到文档「${documentTitle(operation.document_id)}」`
  if (operation.op === 'update_task') return `更新「${taskTitle(operation.task_id)}」`
  // 穷尽所有已知操作后的兜底；新增操作类型时显示原始 op，便于发现遗漏
  return (operation as { op: string }).op
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

function bindEditRef(el: unknown) {
  editRef.value = el instanceof HTMLTextAreaElement ? el : null
}

function autosizeEdit() {
  const el = editRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 200)}px`
}

function startEdit(turn: ChatTurn) {
  if (loading.value || turn.role !== 'user') return
  editingUserTurnId.value = turn.id
  editDraft.value = turn.text
  error.value = ''
  void nextTick(() => {
    autosizeEdit()
    const el = editRef.value
    if (!el) return
    el.focus()
    el.setSelectionRange(editDraft.value.length, editDraft.value.length)
    el.scrollIntoView({ block: 'nearest' })
  })
}

function cancelEdit() {
  editingUserTurnId.value = null
  editDraft.value = ''
}

function onEditKeydown(event: KeyboardEvent, turn: ChatTurn) {
  if (imeBusy(event)) return
  if (event.key === 'Escape') {
    event.preventDefault()
    cancelEdit()
    return
  }
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    void submitEdit(turn)
  }
}

async function submitEdit(turn: ChatTurn) {
  if (loading.value) return
  const text = editDraft.value.trim() || (turn.attachments.length ? defaultAttachmentPrompt() : '')
  if (!text) return
  if (text.length > 32000) { error.value = '内容超过 32000 字符，请分段发送。'; return }
  const files = [...turn.attachments]
  const rewind = rewindCompletedExchanges(turns.value, turn.id)
  editingUserTurnId.value = null
  editDraft.value = ''
  turns.value = dropTurnsFrom(turns.value, turn.id)
  await runTurn(text, files, rewind)
}

function onPaste(event: ClipboardEvent) {
  const files = filesFromDataTransfer(event.clipboardData).map(namedPastedFile)
  if (!files.length) return
  // 只在面板根处理一次；输入框/编辑气泡不要再绑 @paste，否则冒泡会添加两份附件
  event.preventDefault()
  event.stopPropagation()
  const intoEdit = Boolean(
    editingUserTurnId.value && (event.target as HTMLElement | null)?.closest?.('.ai-bubble--edit'),
  )
  void addFiles(files, intoEdit ? 'edit' : 'composer')
}

function onDragLeave(event: DragEvent) {
  const current = event.currentTarget as HTMLElement
  const related = event.relatedTarget as Node | null
  if (related && current.contains(related)) return
  dragging.value = false
}

function onDrop(event: DragEvent) {
  dragging.value = false
  const files = filesFromDataTransfer(event.dataTransfer).map(namedPastedFile)
  if (files.length) void addFiles(files)
}

function onPickFiles(event: Event) {
  const input = event.target as HTMLInputElement
  const files = [...(input.files ?? [])]
  input.value = ''
  if (files.length) void addFiles(files)
}

function attachmentBucket(target: 'composer' | 'edit') {
  if (target === 'edit') {
    return turns.value.find(item => item.id === editingUserTurnId.value)?.attachments ?? pendingAttachments.value
  }
  return pendingAttachments.value
}

async function addFiles(files: File[], target: 'composer' | 'edit' = 'composer') {
  if (loading.value || uploading.value) return
  const bucket = attachmentBucket(target)
  const room = PULSE_MAX_ATTACHMENTS - bucket.length
  if (room <= 0) {
    error.value = `一次最多 ${PULSE_MAX_ATTACHMENTS} 个附件`
    return
  }
  const batch = files.slice(0, room)
  uploading.value = true
  error.value = ''
  try {
    for (const file of batch) {
      if (!isSupportedPulseAttachment(file.name)) {
        error.value = `暂不支持「${file.name}」，目前支持 .md / .txt / .docx`
        continue
      }
      if (file.size > PULSE_MAX_ATTACHMENT_BYTES) {
        error.value = `「${file.name}」超过 10MB`
        continue
      }
      if (bucket.some(item => item.name === file.name && item.size === file.size)) continue
      bucket.push(await pulseApi.uploadAttachment(file))
    }
    if (files.length > room) error.value = `一次最多 ${PULSE_MAX_ATTACHMENTS} 个附件`
  } catch (cause) {
    error.value = apiError(cause)
  } finally {
    uploading.value = false
  }
}

function removeAttachment(id: string) {
  pendingAttachments.value = pendingAttachments.value.filter(item => item.id !== id)
}

function removeTurnAttachment(turn: ChatTurn, id: string) {
  turn.attachments = turn.attachments.filter(item => item.id !== id)
}

async function send() {
  if (!canSend.value) return
  if (editingUserTurnId.value) cancelEdit()
  const text = instruction.value.trim() || defaultAttachmentPrompt()
  if (text.length > 32000) { error.value = '内容超过 32000 字符，请分段发送。'; return }
  const files = [...pendingAttachments.value]
  instruction.value = ''
  pendingAttachments.value = []
  await nextTick(() => autosizePrompt())
  await runTurn(text, files)
}

async function retry(turn: ChatTurn) {
  if (loading.value) return
  const user = turn.role === 'user' ? turn : findUserTurn(turns.value, turn)
  if (!user) return
  const rewind = rewindCompletedExchanges(turns.value, user.id)
  const files = [...user.attachments]
  turns.value = dropTurnsFrom(turns.value, user.id)
  cancelEdit()
  await runTurn(user.instruction || user.text, files, rewind)
}

function newConversation() {
  if (loading.value) return
  sessionId.value = null
  turns.value = []
  error.value = ''
  editingUserTurnId.value = null
  editDraft.value = ''
  pendingAttachments.value = []
}

async function runTurn(text: string, attachments: PulseAttachmentMeta[] = [], rewindExchanges = 0) {
  abort?.abort()
  abort = new AbortController()
  abortMessage.value = '已中断'
  loading.value = true
  error.value = ''
  turns.value.push({
    id: ++seq, role: 'user', text, thinking: '', tools: [], operations: [], token: null, error: '',
    applied: false, discarded: false, instruction: text, attachments, completed: false,
  })
  turns.value.push({
    id: ++seq, role: 'assistant', text: '', thinking: '', tools: [], operations: [], token: null, error: '',
    applied: false, discarded: false, instruction: text, attachments: [], completed: false,
  })
  const assistant = turns.value[turns.value.length - 1]!
  await scrollBottom()
  const timeoutId = window.setTimeout(() => {
    abortMessage.value = '请求超时，已中断'
    abort?.abort()
  }, STREAM_TIMEOUT_MS)
  try {
    const mentions = extractMentions(text)
    await pulseApi.run(
      {
        instruction: text,
        session_id: sessionId.value,
        ...(mentions.length && { mentions }),
        ...(attachments.length && { attachment_ids: attachments.map(item => item.id) }),
        ...(rewindExchanges && { rewind_exchanges: rewindExchanges }),
        ...(progress.taskEditorOpen && progress.editingTask && { context_task_id: progress.editingTask.id }),
        ...(knowledge.documentEditorOpen && knowledge.editingDocument && { context_document_id: knowledge.editingDocument.id }),
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
          assistant.completed = true
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
  if (!turn.token || turn.discarded) return
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
    window.dispatchEvent(new Event('workbench-changed'))
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
  turn.discarded = true
}

function isRawView(id: number) {
  return rawAssistantIds.value.has(id)
}

function toggleRawView(id: number) {
  const next = new Set(rawAssistantIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  rawAssistantIds.value = next
}

function copyTurn(turn: ChatTurn) {
  if (!turn.text) return
  void navigator.clipboard?.writeText(turn.text).then(() => {
    copiedTurnId.value = turn.id
    if (copiedTimer) window.clearTimeout(copiedTimer)
    copiedTimer = window.setTimeout(() => { copiedTurnId.value = null }, 1600)
  }).catch(() => { /* 剪贴板不可用时忽略 */ })
}
</script>

<template>
  <section :class="['ai-dock', open && 'ai-dock--open', open && wide && 'ai-dock--wide']" aria-label="Pulse AI 助手" @keydown.capture="onDockKeydown" @paste="onPaste">
    <button v-if="!open" class="ai-trigger" aria-label="打开 Pulse AI 对话（快捷键 Ctrl/Cmd+I）" title="提问、分析或发起操作 · Ctrl/Cmd+I 快速呼出" @click="open = true">
      <span class="relative"><Sparkles :size="17" /><i /></span>
      <b>Pulse AI</b>
    </button>
    <template v-else>
      <header class="flex items-center gap-3 border-b border-line px-4 py-3">
        <span class="grid size-8 place-items-center rounded-lg bg-cyan/10 text-cyan"><Bot :size="17" /></span>
        <div>
          <b class="text-sm text-text">Pulse AI</b>
          <p class="text-[12px] text-muted-foreground">{{ sessionId ? '多轮对话中，可指代上文' : '工具会排队变更，确认后才写入' }}</p>
        </div>
        <Tooltip>
          <TooltipTrigger as-child>
            <Button
              class="ml-auto hidden sm:inline-flex"
              variant="ghost"
              size="icon"
              :aria-label="wide ? '恢复默认宽度' : '加宽面板'"
              @click="wide = !wide"
            >
              <Minimize2 v-if="wide" :size="16" />
              <Maximize2 v-else :size="16" />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom">{{ wide ? '恢复默认宽度' : '加宽面板' }}</TooltipContent>
        </Tooltip>
        <Button :disabled="loading" :aria-label="sessionId ? '清空对话，开始新会话' : '新对话'" :title="sessionId ? '清空历史，开始新会话' : '新对话'" @click="newConversation" variant="ghost" size="icon"><MessageSquarePlus :size="16" /></Button>
        <Button aria-label="收起助手" @click="open = false" variant="ghost" size="icon"><X :size="16" /></Button>
      </header>
      <div ref="scroller" class="ai-transcript">
        <div v-if="!turns.length" class="rounded-xl border border-line bg-panel-2/50 p-3 text-xs leading-relaxed text-muted-foreground">
          <p>可以分析想法、检索知识或操作已接入的模块；写入类变更会先排队，经你确认后才生效。只想保存原文时，用「随手记」。</p>
          <p v-if="currentPageLabel || contextChips.length" class="mt-2 flex flex-wrap items-center gap-x-1.5 gap-y-1">
            <span>当前上下文：</span>
            <Badge v-if="currentPageLabel" variant="outline">页面 · {{ currentPageLabel }}</Badge>
            <Badge v-for="chip in contextChips" :key="chip" variant="secondary">{{ chip }}</Badge>
          </p>
        </div>
        <article v-for="turn in turns" :key="turn.id" :class="['ai-turn', `ai-turn--${turn.role}`, editingUserTurnId === turn.id && 'ai-turn--editing']">
          <div v-if="turn.role === 'user'" class="ai-user">
            <textarea
              v-if="editingUserTurnId === turn.id"
              :ref="bindEditRef"
              v-model="editDraft"
              class="ai-bubble ai-bubble--user ai-bubble--edit"
              rows="1"
              :disabled="loading"
              @input="autosizeEdit"
              @keydown="onEditKeydown($event, turn)"
              @compositionstart="onImeCompositionStart"
              @compositionend="onImeCompositionEnd"
            />
            <p v-else class="ai-bubble ai-bubble--user">{{ turn.text }}</p>
            <div v-if="turn.attachments.length" class="ai-attach-chips">
              <span v-for="file in turn.attachments" :key="file.id" class="ai-attach-chip">
                <FileText :size="11" />{{ file.name }}
                <button
                  v-if="editingUserTurnId === turn.id"
                  type="button"
                  class="ai-attach-chip__remove"
                  :aria-label="`移除 ${file.name}`"
                  @click="removeTurnAttachment(turn, file.id)"
                >
                  <X :size="10" />
                </button>
              </span>
            </div>
            <div v-if="!loading" class="ai-turn-actions">
              <template v-if="editingUserTurnId === turn.id">
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button type="button" variant="ghost" size="icon-xs" class="ai-icon-btn" aria-label="取消修改" @click="cancelEdit">
                      <X :size="12" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="top">取消</TooltipContent>
                </Tooltip>
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button type="button" variant="ghost" size="icon-xs" class="ai-icon-btn" aria-label="重发修改" :disabled="!editDraft.trim() && !turn.attachments.length" @click="submitEdit(turn)">
                      <Send :size="12" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="top">重发</TooltipContent>
                </Tooltip>
              </template>
              <Tooltip v-else>
                <TooltipTrigger as-child>
                  <Button type="button" variant="ghost" size="icon-xs" class="ai-icon-btn" aria-label="修改这条消息" @click="startEdit(turn)">
                    <Pencil :size="12" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="top">修改</TooltipContent>
              </Tooltip>
            </div>
          </div>
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
            <div v-if="turn.text" :class="['ai-bubble', 'ai-bubble--assistant', !isRawView(turn.id) && 'ai-bubble--md']">
              <MarkdownView v-if="!isRawView(turn.id)" :source="turn.text" />
              <template v-else>{{ turn.text }}</template>
              <span v-if="loading && turn === turns.at(-1)" class="ai-cursor" />
            </div>
            <p v-else-if="loading && turn === turns.at(-1) && !turn.thinking" class="ai-bubble ai-bubble--assistant text-muted-foreground">正在调用模型…<span class="ai-cursor" /></p>
            <div v-if="!loading && (turn.text || turn.error || turn.id === lastAssistantId)" class="ai-turn-actions ai-turn-actions--reply">
              <Tooltip v-if="turn.text">
                <TooltipTrigger as-child>
                  <Button type="button" variant="ghost" size="icon-xs" class="ai-icon-btn" aria-label="复制原文" @click="copyTurn(turn)">
                    <Check v-if="copiedTurnId === turn.id" :size="12" />
                    <Copy v-else :size="12" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="top">{{ copiedTurnId === turn.id ? '已复制' : '复制' }}</TooltipContent>
              </Tooltip>
              <Tooltip v-if="turn.text">
                <TooltipTrigger as-child>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-xs"
                    :class="['ai-icon-btn', isRawView(turn.id) && 'ai-icon-btn--on']"
                    :aria-label="isRawView(turn.id) ? '查看渲染' : '查看原文'"
                    @click="toggleRawView(turn.id)"
                  >
                    <Code :size="12" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="top">{{ isRawView(turn.id) ? '查看渲染' : '查看原文' }}</TooltipContent>
              </Tooltip>
              <Tooltip v-if="turn.error || turn.id === lastAssistantId">
                <TooltipTrigger as-child>
                  <Button type="button" variant="ghost" size="icon-xs" class="ai-icon-btn" aria-label="重试" @click="retry(turn)">
                    <RotateCcw :size="12" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="top">重试</TooltipContent>
              </Tooltip>
            </div>
            <div v-if="turn.operations.length" class="ai-ops">
              <article v-for="(operation, index) in turn.operations" :key="`${operation.op}-${index}`" class="rounded-lg border border-line bg-panel-2 p-3">
                <b class="text-xs text-text">{{ operationLabel(operation) }}</b>
                <p v-if="operation.op === 'add_entry'" class="mt-2 text-xs text-text">
                  <Badge :variant="kindBadgeVariant(operation.entry.kind)">{{ entryKindMap[operation.entry.kind as ProgressEntryKind] }}</Badge>
                  <span class="ml-2">{{ operation.entry.content }}</span>
                </p>
                <p v-if="operation.op === 'add_member_evaluation'" class="mt-2 text-xs text-text">
                  <Badge :variant="kindBadgeVariant(operation.evaluation.kind)">{{ evaluationKindMap[operation.evaluation.kind] }}</Badge>
                  <span class="ml-2">{{ operation.evaluation.content }}</span>
                </p>
                <p v-if="operation.op === 'create_document_from_attachment'" class="mt-2 text-[12px] text-muted-foreground">
                  原件 <span class="text-text">{{ operation.filename }}</span>
                  将归档，抽出正文写入知识文档
                </p>
                <p v-if="operation.op === 'create_project' || operation.op === 'update_project'" class="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                  <span v-for="row in projectChangeRows(operation)" :key="row.label" class="flex items-center gap-1.5 text-[12px] text-muted-foreground">
                    {{ row.label }}
                    <span v-if="row.color" class="size-2.5 rounded-full" :style="{ backgroundColor: row.color }" />
                    <span class="text-text">{{ row.text }}</span>
                  </span>
                </p>
                <p v-for="[field, after] in operationChanges(operation)" :key="field" class="mt-2 text-[12px] text-muted-foreground">
                  {{ fieldLabel(operation, field) }}
                  <span class="ml-1 text-text">{{ display(field, after) }}</span>
                </p>
              </article>
            </div>
            <div v-if="turn.token && turn.operations.length && !turn.applied" class="mt-3 flex justify-end gap-1.5">
              <Button size="sm" :disabled="confirming" @click="discard(turn)" variant="outline"><Undo2 :size="12" />放弃</Button>
              <Button size="sm" :disabled="confirming" @click="confirm(turn)">
                <Check :size="12" />{{ confirming ? '应用中…' : '确认应用' }}
              </Button>
            </div>
            <div v-if="turn.applied" class="success-box mt-3"><Check :size="15" />变更已应用并刷新数据</div>
            <p v-else-if="turn.discarded" class="mt-3 text-xs text-muted-foreground">已放弃，未写入</p>
            <p v-if="turn.error" class="error-box mt-3" role="alert">{{ turn.error }}</p>
          </template>
        </article>
        <p v-if="error" class="error-box" role="alert">{{ error }}</p>
      </div>
      <form
        :class="['ai-dock-form', dragging && 'ai-dock-form--drop']"
        @submit.prevent="send"
        @dragover.prevent="dragging = true"
        @dragleave="onDragLeave"
        @drop.prevent="onDrop"
      >
        <input
          ref="fileRef"
          type="file"
          class="sr-only"
          :accept="PULSE_ATTACHMENT_ACCEPT"
          multiple
          @change="onPickFiles"
        >
        <div v-if="contextChips.length" class="ai-context-row">
          <Badge v-for="chip in contextChips" :key="chip" variant="secondary">{{ chip }}</Badge>
        </div>
        <div v-if="!loading" class="ai-suggest-row" aria-label="快捷建议">
          <button
            v-for="template in quickTemplates"
            :key="template"
            type="button"
            class="ai-suggest"
            @click="applyTemplate(template)"
          >{{ template }}</button>
        </div>
        <div v-if="mentionQuery !== null && !mentionCandidates.length" class="ai-mention-empty">没有匹配的「{{ mentionQuery }}」，可直接继续输入或按 Esc 关闭</div>
        <div v-else-if="mentionQuery !== null" class="ai-mention-list" role="listbox" aria-label="引用候选">
          <div v-for="group in mentionGroups" :key="group.type" role="group" :aria-label="group.label">
            <p role="presentation" class="px-2 pb-0.5 pt-1.5 text-[11px] font-medium text-muted-foreground">{{ group.label }}</p>
            <button
              v-for="(candidate, i) in group.items"
              :key="`${candidate.type}-${candidate.id ?? candidate.label}`"
              type="button"
              role="option"
              :aria-selected="group.startIndex + i === mentionIndex"
              :class="['ai-mention-item', group.startIndex + i === mentionIndex && 'ai-mention-item--active']"
              :title="[candidate.label, candidate.hint].filter(Boolean).join(' · ')"
              @mousedown.prevent="selectMention(candidate)"
              @mousemove="mentionIndex = group.startIndex + i"
            >
              <b>{{ candidate.label }}</b>
              <small v-if="candidate.hint">{{ candidate.hint }}</small>
            </button>
          </div>
        </div>
        <div v-if="pendingAttachments.length || uploading" class="ai-attach-chips ai-attach-chips--composer">
          <span v-for="file in pendingAttachments" :key="file.id" class="ai-attach-chip">
            <FileText :size="11" />{{ file.name }}
            <button type="button" class="ai-attach-chip__remove" :aria-label="`移除 ${file.name}`" @click="removeAttachment(file.id)">
              <X :size="10" />
            </button>
          </span>
          <span v-if="uploading" class="ai-attach-chip ai-attach-chip--muted">正在读取附件…</span>
        </div>
        <div :class="['ai-composer', loading && 'ai-composer--busy', canSend && 'ai-composer--ready']">
          <label class="sr-only" for="ai-prompt">输入调整要求</label>
          <textarea
            id="ai-prompt"
            ref="promptRef"
            v-model="instruction"
            class="ai-composer__input"
            rows="1"
            placeholder="描述操作、粘贴文件，或 @ 引用…"
            :disabled="loading"
            @input="autosizePrompt(); updateMentionQuery()"
            @keydown="onPromptKeydown"
            @click="updateMentionQuery"
            @compositionstart="onImeCompositionStart"
            @compositionend="onImeCompositionEnd"
          />
          <div class="ai-composer__bar">
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              class="ai-composer__attach"
              aria-label="添加附件"
              title="粘贴或选择 .md / .txt / .docx"
              :disabled="loading || uploading"
              @click="fileRef?.click()"
            >
              <Paperclip :size="14" />
            </Button>
            <Button
              v-if="loading"
              type="button"
              class="ai-composer__send ai-composer__send--stop"
              variant="outline"
              size="icon-sm"
              aria-label="中断生成"
              title="中断"
              @click="stop"
            >
              <Square :size="11" fill="currentColor" />
            </Button>
            <Button
              v-else
              type="submit"
              class="ai-composer__send"
              size="icon-sm"
              aria-label="发送"
              title="发送 · Enter"
              :disabled="!canSend"
            >
              <Send :size="14" />
            </Button>
          </div>
        </div>
        <details class="ai-help"><summary>快捷键与引用帮助</summary><p>⌘/Ctrl+I 开关面板 · @ 引用任务、知识或工具<br />Enter 发送 · Shift+Enter 换行 · ⌘/Ctrl+Enter 应用变更 · ↑ 在上一条原文修改<br />气泡内 Enter 重发 · Esc 取消 · 可粘贴或拖入 .md / .txt / .docx</p></details>
      </form>
    </template>
  </section>
</template>
