import { LogIn } from '@lucide/vue'
import type { WorkbenchModule } from '../../app/module-types'
import LoginPage from './LoginPage.vue'

export const authModule: WorkbenchModule = {
  id: 'auth',
  title: '账号登录',
  description: '工作台身份认证',
  icon: LogIn,
  order: 0,
  homeCard: false,
  nav: [],
  routeScope: 'public',
  routes: [
    { path: '/login', name: 'login', component: LoginPage, meta: { public: true } },
  ],
}
