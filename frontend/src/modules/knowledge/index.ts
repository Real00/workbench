import { BookOpen } from '@lucide/vue'
import type { WorkbenchModule } from '../../app/module-types'
import { knowledgeRoutes } from './routes'

export const knowledgeModule: WorkbenchModule = {
  id: 'knowledge',
  title: '知识库',
  description: '用文档、键值条目和标签沉淀可检索的工作知识。',
  icon: BookOpen,
  order: 20,
  homeCard: { to: '/knowledge', action: '进入知识库' },
  routeScope: 'shell',
  nav: [
    {
      id: 'knowledge',
      label: '知识库',
      order: 20,
      items: [
        { label: '知识库', to: '/knowledge', icon: BookOpen, order: 10 },
      ],
    },
  ],
  routes: knowledgeRoutes,
}
