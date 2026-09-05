import { createRouter, createWebHistory } from 'vue-router'
import { ensureSession, hasToken } from '../shared/api/client'
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

router.beforeEach(async (to) => {
  if (!to.meta.public && !hasToken()) {
    // JWT 缺失/过期时尝试用设备绑定凭证静默续登，失败才进登录页
    if (!(await ensureSession())) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }
  if (to.path === '/login' && hasToken()) return '/'
})
