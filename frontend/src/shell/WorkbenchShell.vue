<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { Boxes, ChevronLeft, House, LogOut, Menu } from '@lucide/vue'
import { moduleNavigation } from '../app/modules'
import AiDock from '../shared/AiDock.vue'
import CommandPalette from '../shared/CommandPalette.vue'
import ConfirmDialog from '../shared/ConfirmDialog.vue'
import CaptureComposer from '../modules/capture/CaptureComposer.vue'
import { useCaptureStore } from '../modules/capture/store'
import { useKnowledgeStore } from '../modules/knowledge/store'
import { useProgressStore } from '../modules/progress/store'
import { subscribeEvents, type ChangeEvent } from '../shared/api/events'
import { clearToken } from '../shared/api/client'
import { setupDesktopBridge } from '../shared/tauri'

const captures = useCaptureStore()
const progress = useProgressStore()
const knowledge = useKnowledgeStore()

// 全局数据变更总线：任何来源（本端/其他设备/MCP/AI）的写操作都会推事件，
// 300ms 合并后静默刷新已初始化的模块，桌面端无需刷新按钮
let stopEvents: (() => void) | undefined
let coalesceTimer: ReturnType<typeof setTimeout> | undefined
const pendingScopes = new Set<ChangeEvent['scope']>()
function handleChange(event: ChangeEvent) {
  pendingScopes.add(event.scope)
  if (coalesceTimer) return
  coalesceTimer = setTimeout(() => {
    coalesceTimer = undefined
    const scopes = new Set(pendingScopes)
    pendingScopes.clear()
    if (scopes.has('all')) {
      scopes.add('progress'); scopes.add('knowledge'); scopes.add('capture')
    }
    if (scopes.has('progress') && progress.initialized) void progress.refreshAll()
    if (scopes.has('knowledge') && knowledge.initialized) void knowledge.refresh()
    if (scopes.has('capture')) captures.revision++
    window.dispatchEvent(new Event('workbench-changed'))
  }, 300)
}
const captureDialog = ref<HTMLDialogElement | null>(null)
const paletteOpen = ref(false)
function quickKey(event: KeyboardEvent) {
  if (event.isComposing) return
  const cmd = event.metaKey || event.ctrlKey
  if (cmd && event.shiftKey && event.key.toLowerCase() === 'j') {
    event.preventDefault(); captures.quickOpen = !captures.quickOpen
  } else if (cmd && !event.shiftKey && !event.altKey && event.key.toLowerCase() === 'k') {
    // 命令面板；AI 助手已让位改用 Ctrl/⌘+I
    event.preventDefault(); paletteOpen.value = !paletteOpen.value
  }
}
let stopDesktopBridge: (() => void) | undefined
onMounted(() => {
  captures.initialize()
  window.addEventListener('keydown', quickKey)
  stopEvents = subscribeEvents(handleChange)
  stopDesktopBridge = setupDesktopBridge({ quickCapture: () => { captures.quickOpen = true } })
})
onUnmounted(() => {
  window.removeEventListener('keydown', quickKey)
  stopEvents?.()
  stopDesktopBridge?.()
  if (coalesceTimer) clearTimeout(coalesceTimer)
  captures.reset()
})
watch(() => captures.quickOpen, open => { if (open) captureDialog.value?.showModal(); else captureDialog.value?.close() })
const router = useRouter()
const collapsed = ref(false)
const mobileOpen = ref(false)
const assistantOpen = ref(false)
const primaryNavigation = moduleNavigation.filter(group => group.id !== 'platform')
const platformNavigation = moduleNavigation.filter(group => group.id === 'platform')

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
          <p class="font-mono text-[10px] uppercase tracking-[.2em] text-muted">Personal workspace</p>
        </div>
      </div>
      <button class="nav-link m-2" aria-label="快速记录" title="随手记 · Ctrl / ⌘ + Shift + J" @click="captures.quickOpen = true"><span aria-hidden="true">＋</span><span v-if="!collapsed">随手记</span></button>
      <nav class="flex-1 overflow-y-auto p-2" aria-label="主导航">
        <RouterLink to="/" aria-label="工作台首页" title="工作台首页" class="nav-link" active-class="" exact-active-class="router-link-active" @click="mobileOpen = false">
          <House :size="18" /><span v-if="!collapsed">工作台首页</span>
        </RouterLink>
        <section v-for="group in primaryNavigation" :key="group.id" class="nav-group">
          <p v-if="!collapsed" class="nav-group-label">{{ group.label }}</p>
          <RouterLink v-for="item in group.items" :key="item.to" :to="item.to" :aria-label="item.label" :title="collapsed ? item.label : undefined" class="nav-link" active-class="" exact-active-class="router-link-active" @click="mobileOpen = false">
            <component :is="item.icon" :size="18" /><span v-if="!collapsed">{{ item.label }}</span>
          </RouterLink>
        </section>
      </nav>
      <div class="border-t border-line p-2">
        <template v-for="group in platformNavigation" :key="group.id">
          <RouterLink v-for="item in group.items" :key="item.to" :to="item.to" :aria-label="item.label" :title="collapsed ? item.label : undefined" class="nav-link" @click="mobileOpen = false"><component :is="item.icon" :size="18" /><span v-if="!collapsed">{{ item.label }}</span></RouterLink>
        </template>
        <button class="nav-link hidden w-full lg:flex" :aria-label="collapsed ? '展开侧栏' : '收起侧栏'" @click="collapsed = !collapsed">
          <ChevronLeft :class="collapsed && 'rotate-180'" :size="18" /><span v-if="!collapsed">收起侧栏</span>
        </button>
        <button class="nav-link mt-1 w-full" aria-label="退出登录" @click="logout">
          <LogOut :size="18" /><span v-if="!collapsed">退出登录</span>
        </button>
      </div>
    </aside>
    <main :class="['main-content', collapsed && 'main-content--wide', assistantOpen && 'main-content--assistant']">
      <RouterView />
      <AiDock @open-change="assistantOpen = $event" />
      <dialog ref="captureDialog" class="quick-capture-dialog" aria-label="快速记录" @close="captures.quickOpen = false">
        <div class="mb-4 flex justify-between"><h2>快速记录</h2><button class="icon-btn" aria-label="关闭快记" @click="captures.quickOpen = false">×</button></div>
        <CaptureComposer v-if="captures.quickOpen" autofocus />
      </dialog>
    </main>
    <ConfirmDialog />
    <CommandPalette :open="paletteOpen" @close="paletteOpen = false" />
  </div>
</template>
