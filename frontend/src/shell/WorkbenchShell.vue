<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { Boxes, ChevronLeft, House, LogOut, Menu } from '@lucide/vue'
import { moduleNavigation } from '../app/modules'
import AiDock from '../shared/AiDock.vue'
import { clearToken } from '../shared/api/client'

const router = useRouter()
const collapsed = ref(false)
const mobileOpen = ref(false)

function logout() {
  clearToken()
  router.replace('/login')
}
</script>

<template>
  <div class="min-h-screen bg-ink text-slate-200">
    <button class="mobile-menu" aria-label="打开导航" @click="mobileOpen = true"><Menu :size="19" /></button>
    <div v-if="mobileOpen" class="fixed inset-0 z-30 bg-black/60 lg:hidden" @click="mobileOpen = false" />
    <aside :class="['sidebar', collapsed && 'sidebar--collapsed', mobileOpen && 'sidebar--open']">
      <div class="flex h-16 items-center gap-3 border-b border-line px-4">
        <span class="grid size-8 place-items-center rounded-lg bg-cyan text-ink"><Boxes :size="17" /></span>
        <div v-if="!collapsed" class="leading-tight">
          <strong class="font-display tracking-wide text-white">个人工作台</strong>
          <p class="font-mono text-[9px] uppercase tracking-[.2em] text-muted">Personal workspace</p>
        </div>
      </div>
      <nav class="flex-1 overflow-y-auto p-2" aria-label="主导航">
        <RouterLink to="/" class="nav-link" active-class="" exact-active-class="router-link-active" @click="mobileOpen = false">
          <House :size="18" /><span v-if="!collapsed">工作台首页</span>
        </RouterLink>
        <section v-for="group in moduleNavigation" :key="group.id" class="mt-5">
          <p v-if="!collapsed" class="px-3 pb-2 font-mono text-[9px] uppercase tracking-[.18em] text-muted">{{ group.label }}</p>
          <RouterLink v-for="item in group.items" :key="item.to" :to="item.to" class="nav-link" active-class="" exact-active-class="router-link-active" @click="mobileOpen = false">
            <component :is="item.icon" :size="18" /><span v-if="!collapsed">{{ item.label }}</span>
          </RouterLink>
        </section>
      </nav>
      <div class="border-t border-line p-2">
        <button class="nav-link hidden w-full lg:flex" :aria-label="collapsed ? '展开侧栏' : '收起侧栏'" @click="collapsed = !collapsed">
          <ChevronLeft :class="collapsed && 'rotate-180'" :size="18" /><span v-if="!collapsed">收起侧栏</span>
        </button>
        <button class="nav-link mt-1 w-full" aria-label="退出登录" @click="logout">
          <LogOut :size="18" /><span v-if="!collapsed">退出登录</span>
        </button>
      </div>
    </aside>
    <main :class="['main-content', collapsed && 'main-content--wide']">
      <RouterView />
      <AiDock />
    </main>
  </div>
</template>
