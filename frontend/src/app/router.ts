import { createRouter, createWebHistory } from 'vue-router'
import { bindCurrentDevice, ensureSession, hasToken } from '../shared/api/client'
import WorkbenchShell from '../shell/WorkbenchShell.vue'
import WorkbenchHome from '../modules/home/WorkbenchHome.vue'
import { publicRoutes, shellRoutes } from './modules'

const localDevAuthBypass = import.meta.env.DEV && import.meta.env.VITE_DEV_AUTH_BYPASS === '1'

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
  if (localDevAuthBypass) return to.path === '/login' ? '/' : undefined
  if (to.meta.public) return
  if (!hasToken() && !(await ensureSession())) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  // 已登录但缺设备凭证（旧版本会话升级）时静默补绑；已绑定则立即返回
  void bindCurrentDevice()
  if (to.path === '/login' && hasToken()) return '/'
})
