import { describe, expect, it } from 'vitest'
import { moduleNavigation, modules, publicRoutes, shellRoutes } from './modules'

describe('module registry', () => {
  it('注册稳定且唯一的模块 id', () => {
    const ids = modules.map(module => module.id)
    expect(ids).toEqual(['auth', 'progress', 'knowledge', 'settings'])
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('从注册表组装分组导航', () => {
    expect(moduleNavigation.map(group => group.id)).toEqual(['progress', 'knowledge', 'platform'])
    expect(moduleNavigation.flatMap(group => group.items.map(item => item.to))).toEqual([
      '/progress',
      '/progress/tasks',
      '/progress/projects',
      '/progress/members',
      '/knowledge',
      '/settings',
    ])
  })

  it('按作用域组装登录和 shell 子路由', () => {
    expect(publicRoutes.map(route => route.path)).toEqual(['/login'])
    expect(shellRoutes.map(route => route.path)).toEqual(['progress', 'knowledge', 'settings'])
  })
})
