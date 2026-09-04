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
  nav: ModuleNavGroup[]
  routes: RouteRecordRaw[]
  routeScope: 'public' | 'shell'
}
