import type { RouteRecordRaw } from 'vue-router'
import KnowledgeLayout from './layout/KnowledgeLayout.vue'
import KnowledgePage from './pages/KnowledgePage.vue'

export const knowledgeRoutes: RouteRecordRaw[] = [
  {
    path: 'knowledge',
    component: KnowledgeLayout,
    children: [
      { path: '', name: 'knowledge', component: KnowledgePage },
    ],
  },
]
