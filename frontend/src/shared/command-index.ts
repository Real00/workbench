import type { Component } from 'vue'
import type { Capture } from '../modules/capture/store'
import type { KnowledgeDocument, KnowledgeEntry } from '../modules/knowledge/types'
import type { Member, Project, Task } from '../modules/progress/types'

export type CommandKind = 'action' | 'nav' | 'task' | 'member' | 'project' | 'entry' | 'document' | 'capture'

export interface CommandItem {
  id: string
  kind: CommandKind
  label: string
  hint?: string
  /** 参与匹配但不作为标题展示：状态、优先级、标签、别名等 */
  keywords?: string[]
  icon?: Component
  /** 空搜索时的默认列表是否包含该条 */
  default?: boolean
  run: () => void
}

export interface CommandDeps {
  router: { push: (target: string) => unknown }
  tasks: Task[]
  members: Member[]
  projects: Project[]
  entries: KnowledgeEntry[]
  documents: KnowledgeDocument[]
  captures: Capture[]
  navItems: { label: string; to: string; icon?: Component }[]
  createTask: () => void
  quickCapture: () => void
  askAi: () => void
}

const TASK_STATUS: Record<Task['status'], string> = {
  todo: '待办', in_progress: '进行中', done: '已完成', cancelled: '已取消',
}
const PRIORITY: Record<Task['priority'], string> = { low: '低', medium: '中', high: '高', urgent: '紧急' }
const PROJECT_STATUS: Record<Project['status'], string> = {
  planning: '规划中', active: '进行中', completed: '已完成', archived: '已归档',
}

function truncate(text: string, max: number) {
  const line = text.split('\n')[0]!.trim()
  return line.length > max ? `${line.slice(0, max)}…` : line
}

/** 活跃任务优先：进行中 > 待办 > 其余，同级按最近更新 */
function taskRank(task: Task) {
  return task.status === 'in_progress' ? 2 : task.status === 'todo' ? 1 : 0
}

export function buildCommands(deps: CommandDeps): CommandItem[] {
  const go = (to: string) => () => { void deps.router.push(to) }
  const memberName = new Map(deps.members.map(member => [member.id, member.name]))
  const projectName = new Map(deps.projects.map(project => [project.id, project.name]))
  const items: CommandItem[] = []

  items.push(
    { id: 'action:new-task', kind: 'action', label: '新建任务', hint: '命令', default: true, run: deps.createTask },
    { id: 'action:quick-capture', kind: 'action', label: '快速记录', hint: '命令 · Ctrl/⌘+Shift+J', default: true, run: deps.quickCapture },
    { id: 'action:ask-ai', kind: 'action', label: '打开 AI 助手', hint: '命令 · Ctrl/⌘+I', default: true, run: deps.askAi },
  )
  for (const nav of deps.navItems) {
    items.push({ id: `nav:${nav.to}`, kind: 'nav', label: nav.label, hint: '页面', icon: nav.icon, default: true, run: go(nav.to) })
  }

  const activeTasks = [...deps.tasks]
    .sort((left, right) => taskRank(right) - taskRank(left) || right.updated_at.localeCompare(left.updated_at))
  activeTasks.forEach((task, order) => {
    const parts = [`任务 · ${TASK_STATUS[task.status]} · ${PRIORITY[task.priority]}`]
    if (task.assignee_id && memberName.get(task.assignee_id)) parts.push(memberName.get(task.assignee_id)!)
    if (task.project_id && projectName.get(task.project_id)) parts.push(projectName.get(task.project_id)!)
    items.push({
      id: `task:${task.id}`,
      kind: 'task',
      label: task.title,
      hint: parts.join(' · '),
      keywords: [task.status, TASK_STATUS[task.status], task.priority, ...task.tags],
      default: order < 8,
      run: go(`/progress/tasks?task=${task.id}`),
    })
  })

  for (const member of deps.members) {
    items.push({
      id: `member:${member.id}`, kind: 'member', label: member.name,
      hint: `成员 · ${member.title || '团队成员'}`, keywords: member.skills, run: go('/progress/members'),
    })
  }
  for (const project of deps.projects) {
    items.push({
      id: `project:${project.id}`, kind: 'project', label: project.name,
      hint: `项目 · ${PROJECT_STATUS[project.status]}`, keywords: [project.status, PROJECT_STATUS[project.status]],
      run: go('/progress/projects'),
    })
  }
  for (const entry of deps.entries) {
    items.push({
      id: `entry:${entry.id}`, kind: 'entry', label: entry.key,
      hint: `知识条目 · ${truncate(entry.value, 48)}`, keywords: entry.aliases,
      run: go(`/knowledge?entry=${entry.id}`),
    })
  }
  for (const document of deps.documents) {
    items.push({
      id: `document:${document.id}`, kind: 'document', label: document.title, hint: '知识文档',
      run: go(`/knowledge?document=${document.id}`),
    })
  }
  for (const capture of deps.captures) {
    items.push({
      id: `capture:${capture.id}`, kind: 'capture', label: truncate(capture.content, 44) || '（空记录）',
      hint: `随手记 · ${capture.created_at.slice(0, 10)}`, run: go('/captures'),
    })
  }
  return items
}

function matchScore(item: CommandItem, query: string) {
  const label = item.label.toLowerCase()
  let score = 0
  if (label === query) score = Math.max(score, 100)
  else if (label.startsWith(query)) score = Math.max(score, 80)
  else if (label.includes(query)) score = Math.max(score, 60)
  for (const keyword of item.keywords ?? []) {
    const key = keyword.toLowerCase()
    if (key === query) score = Math.max(score, 55)
    else if (key.startsWith(query)) score = Math.max(score, 40)
    else if (key.includes(query)) score = Math.max(score, 30)
  }
  if (item.hint?.toLowerCase().includes(query)) score = Math.max(score, 20)
  return score
}

/** 过滤打分；空查询返回默认列表（动作 + 页面 + 最近活跃任务） */
export function filterCommands(items: CommandItem[], query: string): CommandItem[] {
  const query_ = query.trim().toLowerCase()
  if (!query_) return items.filter(item => item.default)
  return items
    .map(item => ({ item, score: matchScore(item, query_) }))
    .filter(entry => entry.score > 0)
    .sort((left, right) => right.score - left.score)
    .map(entry => entry.item)
}
