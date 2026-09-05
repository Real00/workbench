import type { ModuleNavGroup, WorkbenchModule } from './module-types'
import { captureModule } from '../modules/capture'
import { authModule } from '../modules/auth'
import { knowledgeModule } from '../modules/knowledge'
import { progressModule } from '../modules/progress'
import { settingsModule } from '../modules/settings'

export const modules: WorkbenchModule[] = [
  authModule,
  captureModule,
  progressModule,
  knowledgeModule,
  settingsModule,
].sort((left, right) => left.order - right.order)

export const publicRoutes = modules
  .filter(module => module.routeScope === 'public')
  .flatMap(module => module.routes)

export const shellRoutes = modules
  .filter(module => module.routeScope === 'shell')
  .flatMap(module => module.routes)

export const homeModules = modules.filter(module => module.homeCard !== false)

export const moduleNavigation: ModuleNavGroup[] = modules
  .flatMap(module => module.nav)
  .sort((left, right) => left.order - right.order)
  .map(group => ({
    ...group,
    items: [...group.items].sort((left, right) => left.order - right.order),
  }))
