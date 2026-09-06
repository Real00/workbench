import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { apiError } from '../../shared/api/client'
import { progressApi } from './api'
import type { DashboardData, Member, MemberEvaluationInput, MemberInput, ProgressEntryInput, Project, ProjectInput, Task, TaskInput } from './types'

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

  function openTask(task?: Task) {
    editingTask.value = task ?? null
    taskEditorOpen.value = true
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
      taskEditorOpen.value = false
      await refreshTasks()
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
      taskEditorOpen.value = false
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
    initialize, refreshAll, refreshTasks, openTask, saveTask, addTaskEntry, uploadTaskResource, addTaskLink, deleteTaskResource, deleteTask, openMember, saveMember, deleteMember, addMemberEvaluation, removeMemberEvaluation, openProject, saveProject, deleteProject,
  }
})
