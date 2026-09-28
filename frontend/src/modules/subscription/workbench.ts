import type { WorkbenchItem } from '../../app/module-types'
import { subscriptionApi } from './api'

export async function loadSubscriptionWorkbench(): Promise<WorkbenchItem[]> {
  const [sources, articles] = await Promise.all([
    subscriptionApi.getSources(),
    subscriptionApi.getArticles({ limit: 8 }),
  ])
  const items: WorkbenchItem[] = []
  for (const source of sources.filter(item => item.last_status === 'error').slice(0, 3)) {
    items.push({
      id: `sub-err-${source.id}`,
      kind: 'attention',
      title: `订阅失败：${source.name}`,
      summary: source.last_error || '刷新出错',
      to: '/subscription',
      occurredAt: source.updated_at,
    })
  }
  for (const article of articles.slice(0, 5)) {
    items.push({
      id: `sub-art-${article.id}`,
      kind: 'activity',
      title: article.title,
      summary: article.author || '订阅文章',
      to: `/subscription/articles/${article.id}`,
      occurredAt: article.published_at || article.fetched_at,
    })
  }
  return items
}
