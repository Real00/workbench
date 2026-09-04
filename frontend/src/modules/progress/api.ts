import { api, streamSse } from '../../shared/api/client'
import type { AiStreamEvent, DashboardData, Member, MemberEvaluationInput, MemberInput, Project, ProjectInput, Task, TaskInput, TaskUpdate } from './types'

const base = '/progress'

export const progressApi = {
  getTasks: async () => (await api.get<Task[]>(`${base}/tasks`)).data,
  createTask: async (payload: TaskInput) => (await api.post<Task>(`${base}/tasks`, payload)).data,
  updateTask: async (id: string, payload: TaskUpdate) => (await api.patch<Task>(`${base}/tasks/${id}`, payload)).data,
  deleteTask: async (id: string) => api.delete(`${base}/tasks/${id}`),
  uploadResource: async (id: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return (await api.post<Task>(`${base}/tasks/${id}/resources/file`, form, {
      timeout: 60_000,
      transformRequest: [(data, headers) => {
        if (headers && 'delete' in headers) headers.delete('Content-Type')
        return data
      }],
    })).data
  },
  addResourceLink: async (id: string, payload: { name: string; url: string }) => (
    await api.post<Task>(`${base}/tasks/${id}/resources/link`, payload)
  ).data,
  deleteResource: async (taskId: string, resourceId: string) => (
    await api.delete<Task>(`${base}/tasks/${taskId}/resources/${resourceId}`)
  ).data,
  downloadResource: async (taskId: string, resourceId: string) => (
    await api.get<Blob>(`${base}/tasks/${taskId}/resources/${resourceId}/file`, { responseType: 'blob' })
  ).data,
  getMembers: async () => (await api.get<Member[]>(`${base}/members`)).data,
  createMember: async (payload: MemberInput) => (await api.post<Member>(`${base}/members`, payload)).data,
  updateMember: async (id: string, payload: MemberInput) => (await api.patch<Member>(`${base}/members/${id}`, payload)).data,
  deleteMember: async (id: string) => api.delete(`${base}/members/${id}`),
  addMemberEvaluation: async (id: string, payload: MemberEvaluationInput) => (await api.post<Member>(`${base}/members/${id}/evaluations`, payload)).data,
  removeMemberEvaluation: async (id: string, evaluationId: string) => (await api.delete<Member>(`${base}/members/${id}/evaluations/${evaluationId}`)).data,
  getProjects: async () => (await api.get<Project[]>(`${base}/projects`)).data,
  createProject: async (payload: ProjectInput) => (await api.post<Project>(`${base}/projects`, payload)).data,
  updateProject: async (id: string, payload: ProjectInput) => (await api.patch<Project>(`${base}/projects/${id}`, payload)).data,
  deleteProject: async (id: string) => api.delete(`${base}/projects/${id}`),
  getDashboard: async () => (await api.get<DashboardData>(`${base}/dashboard`)).data,
  runAiTask: async (
    payload: { instruction: string; context_task_id?: string },
    onEvent: (event: AiStreamEvent) => void,
    signal?: AbortSignal,
  ) => {
    await streamSse(`${base}/ai/run`, payload, event => onEvent(event as AiStreamEvent), signal)
  },
  confirmAiTask: async (confirmation_token: string) => (
    await api.post(`${base}/ai/confirm`, { confirmation_token })
  ).data,
}
