import { createRouter, createWebHistory } from 'vue-router'
import { hasToken } from '../shared/api/client'
import WorkbenchShell from '../shell/WorkbenchShell.vue'
import WorkbenchHome from '../modules/home/WorkbenchHome.vue'
import { publicRoutes, shellRoutes } from './modules'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    ...publicRoutes,
    {
      path: '/',
      component: WorkbenchShell,
      children: [
        { path: '', name: 'home', component: WorkbenchHome },
        ...shellRoutes,
      ],
    },
  ],
})

router.beforeEach((to) => {
  if (!to.meta.public && !hasToken()) return { path: '/login', query: { redirect: to.fullPath } }
  if (to.path === '/login' && hasToken()) return '/'
})
