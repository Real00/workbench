import type { Component } from 'vue'
import type { RouteRecordRaw } from 'vue-router'

export interface ModuleNavItem {
  label: string
  to: string
  icon: Component
  order: number
}

export interface ModuleNavGroup {
  id: string
  label: string
  order: number
  items: ModuleNavItem[]
}

export interface ModuleHomeCard {
  to: string
  action: string
}

export interface WorkbenchModule {
  id: string
  title: string
  description: string
  icon: Component
  order: number
  homeCard: ModuleHomeCard | false
  workbench?: WorkbenchContribution
  nav: ModuleNavGroup[]
  routes: RouteRecordRaw[]
  routeScope: 'public' | 'shell'
}

/** A module owns its source data; the home only renders these projections. */
export interface WorkbenchItem {
  id: string
  title: string
  summary: string
  to: string
  occurredAt: string
  kind: 'attention' | 'activity'
}
export interface WorkbenchContribution {
  load: () => Promise<WorkbenchItem[]>
}
