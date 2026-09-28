import { describe, expect, it } from 'vitest'
import {
  emptyTaskViewFilters,
  hasActiveTaskFilters,
  TASK_FILTER_NONE,
  taskMatchesFilters,
} from './task-filters'
import type { Task } from './types'

function task(partial: Partial<Task> & Pick<Task, 'title'>): Task {
  return {
    id: 't1',
    description: '',
    status: 'todo',
    priority: 'medium',
    assignee_id: null,
    project_id: null,
    start_date: null,
    due_date: null,
    progress: 0,
    estimated_hours: null,
    tags: [],
    entries: [],
    resources: [],
    created_at: '',
    updated_at: '',
    ...partial,
  }
}

describe('taskMatchesFilters', () => {
  it('passes everything when filters are empty', () => {
    expect(taskMatchesFilters(task({ title: 'A' }), emptyTaskViewFilters(), {})).toBe(true)
  })

  it('filters by status priority assignee and project', () => {
    const item = task({
      title: '登录',
      status: 'in_progress',
      priority: 'high',
      assignee_id: 'm1',
      project_id: 'p1',
    })
    expect(taskMatchesFilters(item, { ...emptyTaskViewFilters(), status: 'todo' }, {})).toBe(false)
    expect(taskMatchesFilters(item, { ...emptyTaskViewFilters(), status: 'in_progress' }, {})).toBe(true)
    expect(taskMatchesFilters(item, { ...emptyTaskViewFilters(), priority: 'low' }, {})).toBe(false)
    expect(taskMatchesFilters(item, { ...emptyTaskViewFilters(), assignee: 'm2' }, {})).toBe(false)
    expect(taskMatchesFilters(item, { ...emptyTaskViewFilters(), assignee: 'm1' }, {})).toBe(true)
    expect(taskMatchesFilters(item, { ...emptyTaskViewFilters(), project: 'p2' }, {})).toBe(false)
    expect(taskMatchesFilters(item, { ...emptyTaskViewFilters(), project: 'p1' }, {})).toBe(true)
  })

  it('filters unassigned and unscoped with sentinel', () => {
    const open = task({ title: '杂项', assignee_id: null, project_id: null })
    const assigned = task({ title: '有主', assignee_id: 'm1', project_id: 'p1' })
    expect(taskMatchesFilters(open, { ...emptyTaskViewFilters(), assignee: TASK_FILTER_NONE }, {})).toBe(true)
    expect(taskMatchesFilters(assigned, { ...emptyTaskViewFilters(), assignee: TASK_FILTER_NONE }, {})).toBe(false)
    expect(taskMatchesFilters(open, { ...emptyTaskViewFilters(), project: TASK_FILTER_NONE }, {})).toBe(true)
    expect(taskMatchesFilters(assigned, { ...emptyTaskViewFilters(), project: TASK_FILTER_NONE }, {})).toBe(false)
  })

  it('matches query against title tags and names', () => {
    const item = task({ title: '登录页', tags: ['auth'] })
    expect(taskMatchesFilters(item, { ...emptyTaskViewFilters(), query: '登录' }, {})).toBe(true)
    expect(taskMatchesFilters(item, { ...emptyTaskViewFilters(), query: 'auth' }, {})).toBe(true)
    expect(taskMatchesFilters(item, { ...emptyTaskViewFilters(), query: '张三' }, { assigneeName: '张三' })).toBe(true)
    expect(taskMatchesFilters(item, { ...emptyTaskViewFilters(), query: '无' }, {})).toBe(false)
  })

  it('detects active filters', () => {
    expect(hasActiveTaskFilters(emptyTaskViewFilters())).toBe(false)
    expect(hasActiveTaskFilters({ ...emptyTaskViewFilters(), status: 'todo' })).toBe(true)
    expect(hasActiveTaskFilters({ ...emptyTaskViewFilters(), query: '  x  ' })).toBe(true)
  })
})
