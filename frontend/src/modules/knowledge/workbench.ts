import type { WorkbenchItem } from '../../app/module-types'
import { knowledgeApi } from './api'

export async function loadKnowledgeWorkbench(): Promise<WorkbenchItem[]> {
  const [documents, entries] = await Promise.all([knowledgeApi.getDocuments(), knowledgeApi.getEntries()])
  return [
    ...documents.map(item => ({ id: `document:${item.id}`, title: item.title, summary: '知识文档更新', to: `/knowledge?document=${encodeURIComponent(item.id)}`, occurredAt: item.updated_at ?? item.created_at ?? '', kind: 'activity' as const })),
    ...entries.map(item => ({ id: `entry:${item.id}`, title: item.key, summary: '知识条目更新', to: `/knowledge?entry=${encodeURIComponent(item.id)}`, occurredAt: item.updated_at ?? item.created_at ?? '', kind: 'activity' as const })),
  ]
}
