import { Settings } from '@lucide/vue'
import type { WorkbenchModule } from '../../app/module-types'
import SettingsPage from './SettingsPage.vue'

export const settingsModule: WorkbenchModule = {
  id: 'settings',
  title: '平台设置',
  description: '管理工作台的通用连接与偏好设置。',
  icon: Settings,
  order: 100,
  homeCard: { to: '/settings', action: '打开平台设置' },
  routeScope: 'shell',
  nav: [
    {
      id: 'platform',
      label: '平台',
      order: 100,
      items: [
        { label: '平台设置', to: '/settings', icon: Settings, order: 10 },
      ],
    },
  ],
  routes: [
    { path: 'settings', name: 'settings', component: SettingsPage },
  ],
}
