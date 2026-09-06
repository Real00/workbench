import { describe, expect, it, vi } from 'vitest'
import type { Capture } from '../modules/capture/store'
import type { KnowledgeDocument, KnowledgeEntry } from '../modules/knowledge/types'
import type { Member, Project, Task } from '../modules/progress/types'
import { buildCommands, filterCommands, type CommandDeps } from './command-index'

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 'task-1', title: '接通进度 API', description: '', status: 'in_progress', priority: 'high',
    assignee_id: null, project_id: null, start_date: null, due_date: null, progress: 0,
    estimated_hours: null, tags: [], entries: [], resources: [],
    created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z',
    ...overrides,
  }
}

const member: Member = {
  id: 'member-1', name: '林晓', title: '工程师', active: true, color: '#36d9e9',
  skills: ['API', '工单对接'], background: '', operator: false, evaluations: [],
}

const project: Project = {
  id: 'project-1', name: 'MYAI 工单平台', description: '工单系统二期', background: '',
  started_at: '2026-09-01', member_ids: [member.id], status: 'active', cover_color: null,
  created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z',
}

const entry: KnowledgeEntry = {
  id: 'entry-1', key: 'MYAI', value: '公司内部工单平台', tag_ids: [], document_ids: [], aliases: ['内部平台'],
}

const document: KnowledgeDocument = {
  id: 'doc-1', title: '部署手册', body: '', tag_ids: [], entry_ids: [],
  raw_filename: null, raw_storage_key: null, has_raw: false, canvas_x: 0, canvas_y: 0,
}

const capture: Capture = {
  id: 'cap-1', content: '明天同步部署进度', pinned: false, archived: false, created_at: '2026-09-05T10:00:00Z',
}

function buildDeps(overrides: Partial<CommandDeps> = {}): CommandDeps {
  return {
    router: { push: vi.fn() },
    tasks: [], members: [], projects: [], entries: [], documents: [], captures: [],
    navItems: [{ label: '任务看板', to: '/progress/tasks' }],
    createTask: vi.fn(), quickCapture: vi.fn(), askAi: vi.fn(),
    ...overrides,
  }
}

describe('buildCommands', () => {
  it('空查询默认列表：动作 + 页面 + 活跃任务优先', () => {
    const items = buildCommands(buildDeps({
      tasks: [
        makeTask({ id: 'done-1', title: '旧任务', status: 'done', updated_at: '2026-09-04T00:00:00Z' }),
        makeTask({ updated_at: '2026-09-05T00:00:00Z' }),
      ],
    }))
    const defaults = filterCommands(items, '')
    const ids = defaults.map(item => item.id)
    expect(ids).toContain('action:new-task')
    expect(ids).toContain('nav:/progress/tasks')
    expect(ids.indexOf('task:task-1')).toBeLessThan(ids.indexOf('task:done-1'))
  })

  it('任务按进行中 > 待办排序，深度链接到任务编辑器', () => {
    const deps = buildDeps({
      tasks: [
        makeTask({ id: 'todo-1', status: 'todo', updated_at: '2026-09-05T00:00:00Z' }),
        makeTask({ id: 'doing-1', status: 'in_progress', updated_at: '2026-09-02T00:00:00Z' }),
      ],
    })
    const tasks = buildCommands(deps).filter(item => item.kind === 'task')
    expect(tasks[0]!.id).toBe('task:doing-1')
    tasks[0]!.run()
    expect(deps.router.push).toHaveBeenCalledWith('/progress/tasks?task=doing-1')
  })

  it('任务提示带负责人与项目名，标签参与匹配', () => {
    const items = buildCommands(buildDeps({
      tasks: [makeTask({ assignee_id: member.id, project_id: project.id, tags: ['周报'] })],
      members: [member], projects: [project],
    }))
    const task = items.find(item => item.kind === 'task')!
    expect(task.hint).toContain('林晓')
    expect(task.hint).toContain('MYAI 工单平台')
    expect(filterCommands(items, '周报').map(item => item.id)).toEqual(['task:task-1'])
  })

  it('成员/项目/条目/文档/速记均可检索并跳转', () => {
    const deps = buildDeps({ members: [member], projects: [project], entries: [entry], documents: [document], captures: [capture] })
    const items = buildCommands(deps)
    const byId = (id: string) => items.find(item => item.id === id)!
    byId('member:member-1').run()
    expect(deps.router.push).toHaveBeenCalledWith('/progress/members')
    byId('project:project-1').run()
    expect(deps.router.push).toHaveBeenCalledWith('/progress/projects')
    byId('entry:entry-1').run()
    expect(deps.router.push).toHaveBeenCalledWith('/knowledge?entry=entry-1')
    byId('document:doc-1').run()
    expect(deps.router.push).toHaveBeenCalledWith('/knowledge?document=doc-1')
    byId('capture:cap-1').run()
    expect(deps.router.push).toHaveBeenCalledWith('/captures')
    expect(byId('capture:cap-1').label).toBe('明天同步部署进度')
  })

  it('条目别名参与匹配', () => {
    const result = filterCommands(buildCommands(buildDeps({ entries: [entry] })), '内部平台')
    expect(result.map(item => item.id)).toEqual(['entry:entry-1'])
  })

  it('快捷动作绑定到回调', () => {
    const deps = buildDeps()
    const items = buildCommands(deps)
    items.find(item => item.id === 'action:quick-capture')!.run()
    items.find(item => item.id === 'action:ask-ai')!.run()
    items.find(item => item.id === 'action:new-task')!.run()
    expect(deps.quickCapture).toHaveBeenCalledTimes(1)
    expect(deps.askAi).toHaveBeenCalledTimes(1)
    expect(deps.createTask).toHaveBeenCalledTimes(1)
  })
})

describe('filterCommands', () => {
  const items = buildCommands(buildDeps({
    tasks: [makeTask({ title: '周报自动化' }), makeTask({ id: 'task-2', title: '无关任务', tags: ['周报'] })],
  }))

  it('标题前缀命中排在子串命中之前', () => {
    const result = filterCommands(items, '周报')
    expect(result[0]!.label).toBe('周报自动化')
  })

  it('关键词命中晚于标题命中', () => {
    const result = filterCommands(items, '周报')
    expect(result[result.length - 1]!.id).toBe('task:task-2')
  })

  it('无匹配时返回空列表', () => {
    expect(filterCommands(items, '不存在的关键词xyz')).toEqual([])
  })
})
