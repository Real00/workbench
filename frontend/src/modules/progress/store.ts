import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { apiError } from '../../shared/api/client'
import { progressApi } from './api'
import { priorityMap, statusMap } from './types'
import type { DashboardData, Member, MemberEvaluationInput, MemberInput, Priority, ProgressEntryInput, Project, ProjectInput, Task, TaskInput, TaskStatus, TaskUpdate } from './types'

/** 任务列表排序口径（'' = 默认顺序） */
export type TaskSortId = '' | 'due' | 'priority' | 'progress' | 'updated'

/**
 * 任务视图列表的筛选 / 排序偏好：由 TaskList 维护，进度总览下钻时也会写入，
 * 持久化到 localStorage 以便刷新或返回后还原（审计 A15）
 */
export interface TaskListPrefs {
  status: '' | TaskStatus
  priority: '' | Priority
  /** '' = 全部；TASK_FILTER_NONE = 未分配；否则为成员 id */
  assignee: string
  /** '' = 全部；TASK_FILTER_NONE = 无项目；否则为项目 id */
  project: string
  sort: TaskSortId
  /** 仅看逾期（与后端 dashboard.overdue 同口径：有截止且早于今天、未完成） */
  overdueOnly: boolean
}

const TASK_LIST_PREFS_KEY = 'console.progress.task-list-prefs.v1'
const TASK_SORT_IDS: TaskSortId[] = ['', 'due', 'priority', 'progress', 'updated']

export function defaultTaskListPrefs(): TaskListPrefs {
  return { status: '', priority: '', assignee: '', project: '', sort: '', overdueOnly: false }
}

function loadTaskListPrefs(): TaskListPrefs {
  const fallback = defaultTaskListPrefs()
  try {
    const raw = localStorage.getItem(TASK_LIST_PREFS_KEY)
    if (!raw) return fallback
    const parsed = JSON.parse(raw) as Partial<TaskListPrefs>
    return {
      status: typeof parsed.status === 'string' && parsed.status in statusMap ? parsed.status as TaskStatus : '',
      priority: typeof parsed.priority === 'string' && parsed.priority in priorityMap ? parsed.priority as Priority : '',
      assignee: typeof parsed.assignee === 'string' ? parsed.assignee : '',
      project: typeof parsed.project === 'string' ? parsed.project : '',
      sort: TASK_SORT_IDS.includes(parsed.sort as TaskSortId) ? parsed.sort as TaskSortId : '',
      overdueOnly: parsed.overdueOnly === true,
    }
  } catch {
    return fallback
  }
}

export const useProgressStore = defineStore('progress', () => {
  const tasks = ref<Task[]>([])
  const members = ref<Member[]>([])
  const projects = ref<Project[]>([])
  const dashboard = ref<DashboardData | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  const error = ref('')
  const initialized = ref(false)
  const taskEditorOpen = ref(false)
  const editingTask = ref<Task | null>(null)
  const memberEditorOpen = ref(false)
  const editingMember = ref<Member | null>(null)
  const projectEditorOpen = ref(false)
  const editingProject = ref<Project | null>(null)
  const memberMap = computed(() => new Map(members.value.map(member => [member.id, member])))
  const operatorMember = computed(() => members.value.find(member => member.operator) ?? null)
  const assignableMembers = computed(() =>
    [...members.value.filter(member => member.active)].sort(
      (left, right) => Number(right.operator) - Number(left.operator),
    ),
  )
  const taskListPrefs = ref<TaskListPrefs>(loadTaskListPrefs())
  /** 最近一次成功拉取 dashboard 的时间，用于页面标注数据新鲜度（审计 A11） */
  const dashboardRefreshedAt = ref<Date | null>(null)

  function setTaskListPrefs(patch: Partial<TaskListPrefs>) {
    taskListPrefs.value = { ...taskListPrefs.value, ...patch }
    try {
      localStorage.setItem(TASK_LIST_PREFS_KEY, JSON.stringify(taskListPrefs.value))
    } catch {
      /* 隐私模式等场景下持久化失败可接受，仅影响跨会话记忆 */
    }
  }

  function resetTaskListPrefs() {
    setTaskListPrefs(defaultTaskListPrefs())
  }

  function openTask(task?: Task) {
    editingTask.value = task ?? null
    taskEditorOpen.value = true
  }

  function closeTask() {
    taskEditorOpen.value = false
    editingTask.value = null
  }

  function openMember(member?: Member) {
    editingMember.value = member ?? null
    memberEditorOpen.value = true
  }

  function openProject(project?: Project) {
    editingProject.value = project ?? null
    projectEditorOpen.value = true
  }

  async function initialize() {
    loading.value = true
    error.value = ''
    try {
      const [taskData, memberData, projectData, dashboardData] = await Promise.all([
        progressApi.getTasks(),
        progressApi.getMembers(),
        progressApi.getProjects(),
        progressApi.getDashboard(),
      ])
      tasks.value = taskData
      members.value = memberData
      projects.value = projectData
      dashboard.value = dashboardData
      dashboardRefreshedAt.value = new Date()
      initialized.value = true
    } catch (cause) {
      error.value = apiError(cause)
    } finally {
      loading.value = false
    }
  }

  /** 静默全量刷新：不触发 loading，用于事件总线推送与子菜单切换的后台同步 */
  async function refreshAll() {
    try {
      const [taskData, memberData, projectData, dashboardData] = await Promise.all([
        progressApi.getTasks(),
        progressApi.getMembers(),
        progressApi.getProjects(),
        progressApi.getDashboard(),
      ])
      tasks.value = taskData
      members.value = memberData
      projects.value = projectData
      dashboard.value = dashboardData
      dashboardRefreshedAt.value = new Date()
    } catch {
      /* 后台刷新失败不打扰用户，下次事件或切换菜单会再试 */
    }
  }

  async function refreshTasks() {
    const [taskData, dashboardData] = await Promise.all([
      progressApi.getTasks(),
      progressApi.getDashboard(),
    ])
    tasks.value = taskData
    dashboard.value = dashboardData
    dashboardRefreshedAt.value = new Date()
  }

  async function runSave(action: () => Promise<void>) {
    saving.value = true
    error.value = ''
    try {
      await action()
      return true
    } catch (cause) {
      error.value = apiError(cause)
      return false
    } finally {
      saving.value = false
    }
  }

  async function reloadEditing(id: string) {
    await refreshTasks()
    const fresh = tasks.value.find(task => task.id === id)
    if (fresh && editingTask.value?.id === id) editingTask.value = fresh
  }

  async function saveTask(payload: TaskInput) {
    return runSave(async () => {
      if (editingTask.value) await progressApi.updateTask(editingTask.value.id, payload)
      else await progressApi.createTask(payload)
      closeTask()
      await refreshTasks()
    })
  }

  async function patchTask(id: string, patch: TaskUpdate) {
    return runSave(async () => {
      await progressApi.updateTask(id, patch)
      await reloadEditing(id)
    })
  }

  async function updateTaskStatus(id: string, status: NonNullable<TaskUpdate['status']>) {
    return patchTask(id, { status })
  }

  async function patchMember(id: string, patch: Partial<MemberInput>) {
    return runSave(async () => {
      await progressApi.updateMember(id, patch)
      await refreshMembers()
      syncEditingMember(id)
      dashboard.value = await progressApi.getDashboard()
    })
  }

  async function patchProject(id: string, patch: Partial<ProjectInput>) {
    return runSave(async () => {
      await progressApi.updateProject(id, patch)
      projects.value = await progressApi.getProjects()
      if (editingProject.value?.id === id) {
        editingProject.value = projects.value.find(project => project.id === id) ?? editingProject.value
      }
    })
  }

  async function addTaskEntry(id: string, entry: ProgressEntryInput) {
    return runSave(async () => {
      await progressApi.updateTask(id, { add_entry: entry })
      await reloadEditing(id)
    })
  }

  async function uploadTaskResource(id: string, file: File) {
    return runSave(async () => {
      await progressApi.uploadResource(id, file)
      await reloadEditing(id)
    })
  }

  async function addTaskLink(id: string, payload: { name: string; url: string }) {
    return runSave(async () => {
      await progressApi.addResourceLink(id, payload)
      await reloadEditing(id)
    })
  }

  async function deleteTaskResource(id: string, resourceId: string) {
    return runSave(async () => {
      await progressApi.deleteResource(id, resourceId)
      await reloadEditing(id)
    })
  }

  async function deleteTask(id: string) {
    return runSave(async () => {
      await progressApi.deleteTask(id)
      closeTask()
      await refreshTasks()
    })
  }

  async function saveMember(payload: MemberInput) {
    return runSave(async () => {
      if (editingMember.value) await progressApi.updateMember(editingMember.value.id, payload)
      else await progressApi.createMember(payload)
      memberEditorOpen.value = false
      await initialize()
    })
  }

  async function refreshMembers() {
    members.value = await progressApi.getMembers()
  }

  function syncEditingMember(id: string) {
    const fresh = members.value.find(member => member.id === id)
    if (fresh && editingMember.value?.id === id) editingMember.value = fresh
  }

  async function addMemberEvaluation(id: string, payload: MemberEvaluationInput) {
    return runSave(async () => {
      await progressApi.addMemberEvaluation(id, payload)
      await refreshMembers()
      syncEditingMember(id)
    })
  }

  async function removeMemberEvaluation(id: string, evaluationId: string) {
    return runSave(async () => {
      await progressApi.removeMemberEvaluation(id, evaluationId)
      await refreshMembers()
      syncEditingMember(id)
    })
  }

  async function deleteMember(id: string) {
    return runSave(async () => {
      await progressApi.deleteMember(id)
      memberEditorOpen.value = false
      await initialize()
    })
  }

  async function saveProject(payload: ProjectInput) {
    return runSave(async () => {
      if (editingProject.value) await progressApi.updateProject(editingProject.value.id, payload)
      else await progressApi.createProject(payload)
      projectEditorOpen.value = false
      await initialize()
    })
  }

  async function deleteProject(id: string) {
    return runSave(async () => {
      await progressApi.deleteProject(id)
      projectEditorOpen.value = false
      await initialize()
    })
  }

  return {
    tasks, members, projects, dashboard, memberMap, operatorMember, assignableMembers, loading, saving, error, initialized,
    taskEditorOpen, editingTask, memberEditorOpen, editingMember, projectEditorOpen, editingProject,
    taskListPrefs, dashboardRefreshedAt, setTaskListPrefs, resetTaskListPrefs,
    initialize, refreshAll, refreshTasks, openTask, closeTask, saveTask, patchTask, updateTaskStatus, patchMember, patchProject, addTaskEntry, uploadTaskResource, addTaskLink, deleteTaskResource, deleteTask, openMember, saveMember, deleteMember, addMemberEvaluation, removeMemberEvaluation, openProject, saveProject, deleteProject,
  }
})
