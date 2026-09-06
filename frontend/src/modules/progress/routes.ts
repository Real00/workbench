import type { RouteRecordRaw } from 'vue-router'
const ProgressLayout = () => import('./layout/ProgressLayout.vue')
const DashboardPage = () => import('./pages/DashboardPage.vue')
const MembersPage = () => import('./pages/MembersPage.vue')
const ProjectsPage = () => import('./pages/ProjectsPage.vue')
const TaskViewsPage = () => import('./pages/TaskViewsPage.vue')

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
