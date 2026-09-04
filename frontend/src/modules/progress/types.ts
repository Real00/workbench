export type TaskStatus = 'todo' | 'in_progress' | 'done' | 'cancelled'
export type Priority = 'low' | 'medium' | 'high' | 'urgent'
export type ProgressEntryKind = 'update' | 'blocker' | 'extra_work'
export type ResourceKind = 'image' | 'document' | 'link'
export type MemberEvaluationKind = 'highlight' | 'risk' | 'note'
export type ProjectStatus = 'planning' | 'active' | 'completed' | 'archived'

export interface ProgressEntry {
  id: string
  kind: ProgressEntryKind
  content: string
  created_at: string
}

export interface TaskResource {
  id: string
  kind: ResourceKind
  name: string
  content_type: string
  size_bytes: number
  storage_key: string | null
  url: string | null
  created_at: string
}

export interface Task {
  id: string
  title: string
  description: string
  status: TaskStatus
  priority: Priority
  assignee_id: string | null
  project_id: string | null
  start_date: string | null
  due_date: string | null
  progress: number
  estimated_hours: number | null
  tags: string[]
  entries: ProgressEntry[]
  resources: TaskResource[]
  created_at: string
  updated_at: string
}

export type TaskInput = Omit<Task, 'id' | 'created_at' | 'updated_at' | 'entries' | 'resources'>

export interface ProgressEntryInput {
  kind: ProgressEntryKind
  content: string
}

export type TaskUpdate = Partial<TaskInput> & {
  add_entry?: ProgressEntryInput
}

export interface Member {
  id: string
  name: string
  title: string
  active: boolean
  operator: boolean
  color: string | null
  skills: string[]
  background: string
  evaluations: MemberEvaluation[]
  created_at?: string
  updated_at?: string
}

export interface MemberEvaluation {
  id: string
  kind: MemberEvaluationKind
  content: string
  created_at: string
}

export interface MemberEvaluationInput {
  kind: MemberEvaluationKind
  content: string
}

export interface Project {
  id: string
  name: string
  description: string
  background: string
  started_at: string | null
  member_ids: string[]
  status: ProjectStatus
  cover_color: string | null
  created_at: string
  updated_at: string
}

export type ProjectInput = Pick<Project, 'name' | 'description' | 'background' | 'started_at' | 'member_ids' | 'status' | 'cover_color'>

export type MemberInput = Pick<Member, 'name' | 'title' | 'active' | 'color' | 'skills' | 'background'>

export interface DashboardData {
  total: number
  by_status: Partial<Record<TaskStatus, number>>
  by_priority: Partial<Record<Priority, number>>
  overdue: number
  member_workloads: {
    member: Member
    current_tasks: Task[]
    average_progress: number
    estimated_remaining_days: number
    overdue_risk: boolean
  }[]
  recent_progress: {
    task_id: string
    task_title: string
    kind: ProgressEntryKind
    content: string
    created_at: string
  }[]
}

export type AiOperation =
  | { op: 'create_task'; changes: Record<string, unknown> }
  | { op: 'update_task'; task_id: string; changes: Record<string, unknown> }
  | { op: 'add_entry'; task_id: string; entry: ProgressEntryInput }
  | { op: 'create_member'; changes: Record<string, unknown> }
  | { op: 'update_member'; member_id: string; changes: Record<string, unknown> }
  | { op: 'add_member_evaluation'; member_id: string; evaluation: MemberEvaluationInput }
  | { op: 'create_project'; changes: Record<string, unknown> }
  | { op: 'update_project'; project_id: string; changes: Record<string, unknown> }
  | { op: 'create_tag'; changes: Record<string, unknown> }
  | { op: 'update_tag'; tag_id: string; changes: Record<string, unknown> }
  | { op: 'create_entry'; changes: Record<string, unknown> }
  | { op: 'update_entry'; entry_id: string; changes: Record<string, unknown> }
  | { op: 'create_document'; changes: Record<string, unknown> }
  | { op: 'update_document'; document_id: string; changes: Record<string, unknown> }
  | { op: 'link_entry'; document_id: string; entry_id: string }

export interface AiToolEvent {
  name: string
  status: 'start' | 'done' | 'retry'
  args?: Record<string, unknown>
  result?: string
}

export type AiStreamEvent =
  | { type: 'text'; delta: string }
  | { type: 'thinking'; delta: string }
  | ({ type: 'tool' } & AiToolEvent)
  | { type: 'done'; confirmation_token: string | null; operations: AiOperation[]; session_id?: string }
  | { type: 'cancelled'; message: string }
  | { type: 'error'; message: string }

export const statusMap: Record<TaskStatus, string> = {
  todo: '待处理', in_progress: '进行中', done: '已完成', cancelled: '已取消',
}

export const priorityMap: Record<Priority, string> = {
  low: '低', medium: '中', high: '高', urgent: '紧急',
}

export const entryKindMap: Record<ProgressEntryKind, string> = {
  update: '进展',
  blocker: '阻塞',
  extra_work: '额外处理',
}

export const evaluationKindMap: Record<MemberEvaluationKind, string> = {
  highlight: '亮点',
  risk: '风险',
  note: '备注',
}

export const projectStatusMap: Record<ProjectStatus, string> = {
  planning: '筹备中',
  active: '进行中',
  completed: '已完成',
  archived: '已归档',
}

export const resourceKindMap: Record<ResourceKind, string> = {
  image: '图片',
  document: '文档',
  link: '链接',
}

export const resourceAccept = '.png,.jpg,.jpeg,.gif,.webp,.pdf,.md,.txt,.csv,.doc,.docx,.xls,.xlsx,.ppt,.pptx'

export function formatBytes(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

export function latestEntry(task: Task): ProgressEntry | undefined {
  return task.entries.at(-1)
}

export function isBlocked(task: Task): boolean {
  return latestEntry(task)?.kind === 'blocker'
}
