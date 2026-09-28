import { Code2, Newspaper, Rss } from '@lucide/vue'
import type { WorkbenchModule } from '../../app/module-types'
import { subscriptionRoutes } from './routes'
import { loadSubscriptionWorkbench } from './workbench'

export const subscriptionModule: WorkbenchModule = {
  id: 'subscription',
  title: '订阅',
  description: '定时拉取远程源，用插件解析为可读文章。',
  icon: Rss,
  order: 25,
  homeCard: { to: '/subscription', action: '进入订阅' },
  workbench: { load: loadSubscriptionWorkbench },
  routeScope: 'shell',
  nav: [
    {
      id: 'subscription',
      label: '订阅',
      order: 25,
      items: [
        { label: '订阅源', to: '/subscription', icon: Rss, order: 10 },
        { label: '插件', to: '/subscription/plugins', icon: Code2, order: 20 },
        { label: '文章', to: '/subscription/articles', icon: Newspaper, order: 30 },
      ],
    },
  ],
  routes: subscriptionRoutes,
}
