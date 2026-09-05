import type { WorkbenchItem } from '../../app/module-types'
import { progressApi } from './api'

export async function loadProgressWorkbench(): Promise<WorkbenchItem[]> {
  const tasks = await progressApi.getTasks()
  const today = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai' }).format(new Date())
  return tasks.flatMap(task => {
    const to = `/progress/tasks?task=${encodeURIComponent(task.id)}`
    const activity: WorkbenchItem = { id: `task:${task.id}`, title: task.title, summary: '任务更新', to, occurredAt: task.updated_at, kind: 'activity' }
    const overdue = task.due_date && task.due_date < today && !['done', 'cancelled'].includes(task.status)
    return overdue ? [{ ...activity, id: `overdue:${task.id}`, summary: `已过截止日期 ${task.due_date}`, kind: 'attention' as const }, activity] : [activity]
  })
}
