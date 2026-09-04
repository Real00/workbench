import type { RouteRecordRaw } from 'vue-router'
import ProgressLayout from './layout/ProgressLayout.vue'
import DashboardPage from './pages/DashboardPage.vue'
import MembersPage from './pages/MembersPage.vue'
import ProjectsPage from './pages/ProjectsPage.vue'
import TaskViewsPage from './pages/TaskViewsPage.vue'

export const progressRoutes: RouteRecordRaw[] = [
  {
    path: 'progress',
    component: ProgressLayout,
    children: [
      { path: '', name: 'progress-dashboard', component: DashboardPage },
      { path: 'tasks', name: 'progress-tasks', component: TaskViewsPage },
      { path: 'projects', name: 'progress-projects', component: ProjectsPage },
      { path: 'members', name: 'progress-members', component: MembersPage },
    ],
  },
]
