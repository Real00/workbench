import { loadProgressWorkbench } from './workbench'
import { ChartNoAxesCombined, CheckSquare2, FolderKanban, Gauge, Users } from '@lucide/vue'
import type { WorkbenchModule } from '../../app/module-types'
import { progressRoutes } from './routes'

export const progressModule: WorkbenchModule = {
  id: 'progress',
  title: '进度管理',
  description: '集中查看任务节奏、团队容量与交付风险。',
  icon: Gauge,
  order: 10,
  homeCard: { to: '/progress', action: '进入进度管理' },
  workbench: { load: loadProgressWorkbench },
  routeScope: 'shell',
  nav: [
    {
      id: 'progress',
      label: '进度管理',
      order: 10,
      items: [
        { label: '进度总览', to: '/progress', icon: ChartNoAxesCombined, order: 10 },
        { label: '任务视图', to: '/progress/tasks', icon: CheckSquare2, order: 20 },
        { label: '项目管理', to: '/progress/projects', icon: FolderKanban, order: 25 },
        { label: '成员管理', to: '/progress/members', icon: Users, order: 30 },
      ],
    },
  ],
  routes: progressRoutes,
}
