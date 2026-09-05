import { NotebookPen } from '@lucide/vue'
import type { WorkbenchModule } from '../../app/module-types'
export const captureModule: WorkbenchModule = {
  id: 'capture', title: '随手记', description: '保存想法、资讯与工作上下文。', icon: NotebookPen,
  order: 5, homeCard: false, routeScope: 'shell',
  nav: [{ id: 'capture', label: '个人空间', order: 5, items: [{ label: '随手记', to: '/captures', icon: NotebookPen, order: 1 }] }],
  routes: [{ path: '/captures', component: () => import('./CapturePage.vue') }],
}
