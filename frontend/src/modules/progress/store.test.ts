import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { progressApi } from './api'
import { useProgressStore } from './store'
import type { DashboardData, Member, Project, Task, TaskInput } from './types'

const member: Member = {
  id: 'member-1',
  name: '林晓',
  title: '工程师',
  active: true,
  color: '#36d9e9',
  skills: ['API', '工单对接'],
  background: '做过内部工单系统联调',
  operator: false,
  evaluations: [],
}

const project: Project = {
  id: 'project-1',
  name: 'MYAI 工单平台',
  description: '工单系统二期',
  background: '沿用现有审批流',
  started_at: '2026-09-01',
  member_ids: [member.id],
  status: 'active',
  cover_color: '#36d9e9',
  created_at: '2026-09-01T00:00:00Z',
  updated_at: '2026-09-01T00:00:00Z',
}

const task: Task = {
  id: 'task-1',
  title: '接通进度 API',
  description: '',
  status: 'in_progress',
  priority: 'high',
  assignee_id: member.id,
  project_id: project.id,
  start_date: '2026-09-01',
  due_date: '2026-09-03',
  progress: 60,
  estimated_hours: 8,
  tags: ['api'],
  entries: [],
  resources: [],
  created_at: '2026-09-01T00:00:00Z',
  updated_at: '2026-09-01T00:00:00Z',
}

const dashboard: DashboardData = {
  total: 1,
  by_status: { in_progress: 1 },
  by_priority: { high: 1 },
  overdue: 0,
  member_workloads: [],
  recent_progress: [],
}

function mockReads() {
  vi.spyOn(progressApi, 'getTasks').mockResolvedValue([task])
  vi.spyOn(progressApi, 'getMembers').mockResolvedValue([member])
  vi.spyOn(progressApi, 'getProjects').mockResolvedValue([project])
  vi.spyOn(progressApi, 'getDashboard').mockResolvedValue(dashboard)
}

describe('progress store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('并行加载任务、成员和总览', async () => {
    mockReads()
    const store = useProgressStore()
    expect(store.initialized).toBe(false)
    await store.initialize()
    expect(store.initialized).toBe(true)
    expect(store.tasks).toEqual([task])
    expect(store.memberMap.get(member.id)?.name).toBe('林晓')
    expect(store.dashboard?.total).toBe(1)
  })

  it('静默刷新不触发 loading 且更新全部数据', async () => {
    mockReads()
    const store = useProgressStore()
    await store.initialize()
    const refreshedTask = { ...task, title: '新标题' }
    vi.spyOn(progressApi, 'getTasks').mockResolvedValue([refreshedTask])
    const loadingSpy = vi.fn()
    store.$subscribe(() => { loadingSpy(store.loading) })
    await store.refreshAll()
    expect(store.tasks).toEqual([refreshedTask])
    expect(store.loading).toBe(false)
  })

  it('创建任务后刷新任务和总览', async () => {
    mockReads()
    const create = vi.spyOn(progressApi, 'createTask').mockResolvedValue(task)
    const store = useProgressStore()
    const payload: TaskInput = {
      title: task.title,
      description: '',
      status: 'todo',
      priority: 'high',
      assignee_id: member.id,
      project_id: task.project_id,
      start_date: task.start_date,
      due_date: task.due_date,
      progress: 0,
      estimated_hours: 8,
      tags: [],
    }
    expect(await store.saveTask(payload)).toBe(true)
    expect(create).toHaveBeenCalledWith(payload)
    expect(store.tasks).toEqual([task])
    expect(store.taskEditorOpen).toBe(false)
  })

  it('给任务追加进度记录后刷新并保持编辑对象', async () => {
    mockReads()
    const updated = {
      ...task,
      entries: [{ id: 'entry-1', kind: 'blocker' as const, content: '接口超时', created_at: '2026-09-01T01:00:00Z' }],
    }
    vi.spyOn(progressApi, 'updateTask').mockResolvedValue(updated)
    vi.spyOn(progressApi, 'getTasks').mockResolvedValue([updated])
    const store = useProgressStore()
    await store.initialize()
    store.openTask(task)
    expect(await store.addTaskEntry(task.id, { kind: 'blocker', content: '接口超时' })).toBe(true)
    expect(store.editingTask?.entries).toHaveLength(1)
    expect(store.taskEditorOpen).toBe(true)
  })

  it('上传任务资源后刷新并保持编辑对象', async () => {
    mockReads()
    const file = new File(['png'], 'shot.png', { type: 'image/png' })
    const updated = {
      ...task,
      resources: [{
        id: 'res-1',
        kind: 'image' as const,
        name: 'shot.png',
        content_type: 'image/png',
        size_bytes: 3,
        storage_key: 'task-1/res-1.png',
        url: null,
        created_at: '2026-09-01T01:00:00Z',
      }],
    }
    vi.spyOn(progressApi, 'uploadResource').mockResolvedValue(updated)
    vi.spyOn(progressApi, 'getTasks').mockResolvedValue([updated])
    const store = useProgressStore()
    await store.initialize()
    store.openTask(task)
    expect(await store.uploadTaskResource(task.id, file)).toBe(true)
    expect(store.editingTask?.resources).toHaveLength(1)
    expect(store.taskEditorOpen).toBe(true)
  })

  it('给成员添加评价后刷新并保持编辑对象', async () => {
    mockReads()
    const evaluated = {
      ...member,
      evaluations: [{ id: 'eval-1', kind: 'highlight' as const, content: '联调推进很稳', created_at: '2026-09-02T01:00:00Z' }],
    }
    vi.spyOn(progressApi, 'addMemberEvaluation').mockResolvedValue(evaluated)
    vi.spyOn(progressApi, 'getMembers').mockResolvedValue([evaluated])
    const store = useProgressStore()
    await store.initialize()
    store.openMember(member)
    expect(await store.addMemberEvaluation(member.id, { kind: 'highlight', content: '联调推进很稳' })).toBe(true)
    expect(store.editingMember?.evaluations).toHaveLength(1)
    expect(store.memberEditorOpen).toBe(true)
  })

  it('删除成员评价后刷新并保持编辑对象', async () => {
    mockReads()
    const evaluated = { ...member, evaluations: [{ id: 'eval-1', kind: 'risk' as const, content: '排期偏紧', created_at: '2026-09-02T01:00:00Z' }] }
    vi.spyOn(progressApi, 'removeMemberEvaluation').mockResolvedValue({ ...evaluated, evaluations: [] })
    vi.spyOn(progressApi, 'getMembers').mockResolvedValue([{ ...evaluated, evaluations: [] }])
    const store = useProgressStore()
    await store.initialize()
    store.openMember(evaluated)
    expect(await store.removeMemberEvaluation(member.id, 'eval-1')).toBe(true)
    expect(store.editingMember?.evaluations).toHaveLength(0)
    expect(store.memberEditorOpen).toBe(true)
  })

  it('创建项目后关闭抽屉并全量刷新', async () => {
    mockReads()
    const create = vi.spyOn(progressApi, 'createProject').mockResolvedValue(project)
    const store = useProgressStore()
    await store.initialize()
    expect(await store.saveProject({
      name: project.name,
      description: project.description,
      background: project.background,
      started_at: project.started_at,
      member_ids: project.member_ids,
      status: project.status,
      cover_color: project.cover_color,
    })).toBe(true)
    expect(create).toHaveBeenCalled()
    expect(store.projects).toEqual([project])
    expect(store.projectEditorOpen).toBe(false)
  })

  it('删除项目后关闭抽屉并刷新任务归属', async () => {
    mockReads()
    vi.spyOn(progressApi, 'deleteProject').mockResolvedValue({} as never)
    vi.spyOn(progressApi, 'getProjects').mockResolvedValue([])
    const store = useProgressStore()
    await store.initialize()
    store.openProject(project)
    expect(await store.deleteProject(project.id)).toBe(true)
    expect(store.projectEditorOpen).toBe(false)
    expect(store.projects).toEqual([])
  })
})
