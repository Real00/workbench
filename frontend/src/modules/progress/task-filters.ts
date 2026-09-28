import type { Priority, Task, TaskStatus } from './types'

/** 筛选「未分配 / 无项目」的哨兵；空字符串表示「全部」 */
export const TASK_FILTER_NONE = '__none__'

export interface TaskViewFilters {
  query: string
  status: '' | TaskStatus
  priority: '' | Priority
  /** '' = 全部；TASK_FILTER_NONE = 未分配；否则为成员 id */
  assignee: string
  /** '' = 全部；TASK_FILTER_NONE = 无项目；否则为项目 id */
  project: string
}

export function emptyTaskViewFilters(): TaskViewFilters {
  return { query: '', status: '', priority: '', assignee: '', project: '' }
}

export function hasActiveTaskFilters(filters: TaskViewFilters): boolean {
  return Boolean(
    filters.query.trim()
    || filters.status
    || filters.priority
    || filters.assignee
    || filters.project,
  )
}

export function taskMatchesFilters(
  task: Task,
  filters: TaskViewFilters,
  names: { assigneeName?: string; projectName?: string },
): boolean {
  if (filters.status && task.status !== filters.status) return false
  if (filters.priority && task.priority !== filters.priority) return false
  if (filters.assignee === TASK_FILTER_NONE) {
    if (task.assignee_id) return false
  } else if (filters.assignee && task.assignee_id !== filters.assignee) {
    return false
  }
  if (filters.project === TASK_FILTER_NONE) {
    if (task.project_id) return false
  } else if (filters.project && task.project_id !== filters.project) {
    return false
  }
  const needle = filters.query.trim().toLocaleLowerCase()
  if (!needle) return true
  const haystack = [
    task.title,
    ...task.tags,
    names.assigneeName,
    names.projectName,
  ].filter(Boolean).join(' ').toLocaleLowerCase()
  return haystack.includes(needle)
}
