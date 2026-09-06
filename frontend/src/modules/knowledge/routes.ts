import type { RouteRecordRaw } from 'vue-router'
const KnowledgeLayout = () => import('./layout/KnowledgeLayout.vue')
const KnowledgePage = () => import('./pages/KnowledgePage.vue')

export const knowledgeRoutes: RouteRecordRaw[] = [
  {
    path: 'knowledge',
    component: KnowledgeLayout,
    children: [
      { path: '', name: 'knowledge', component: KnowledgePage },
    ],
  },
]
