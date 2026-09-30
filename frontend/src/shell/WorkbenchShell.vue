<script setup lang="ts">
import { nextTick, ref, onMounted, onUnmounted, watch } from 'vue'
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { ChevronLeft, Command, House, LogOut, Menu, X } from '@lucide/vue'
import { moduleNavigation } from '../app/modules'
import AiDock from '../shared/AiDock.vue'
import CommandPalette from '../shared/CommandPalette.vue'
import ConfirmDialog from '../shared/ConfirmDialog.vue'
import CaptureComposer from '../modules/capture/CaptureComposer.vue'
import { useCaptureStore } from '../modules/capture/store'
import { useKnowledgeStore } from '../modules/knowledge/store'
import { useProgressStore } from '../modules/progress/store'
import { useSubscriptionStore } from '../modules/subscription/store'
import { subscribeEvents, type ChangeEvent } from '../shared/api/events'
import { clearToken } from '../shared/api/client'
import { setupDesktopBridge } from '../shared/tauri'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'

const captures = useCaptureStore()
const progress = useProgressStore()
const knowledge = useKnowledgeStore()
const subscription = useSubscriptionStore()

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
      scopes.add('progress'); scopes.add('knowledge'); scopes.add('capture'); scopes.add('subscription')
    }
    if (scopes.has('progress') && progress.initialized) void progress.refreshAll()
    if (scopes.has('knowledge') && knowledge.initialized) void knowledge.refresh()
    if (scopes.has('capture')) captures.revision++
    if (scopes.has('subscription') && subscription.initialized) void subscription.refresh()
    window.dispatchEvent(new Event('workbench-changed'))
  }, 300)
}
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
const router = useRouter()
const collapsed = ref(false)
const mobileOpen = ref(false)
const sidebarEl = ref<HTMLElement | null>(null)
// 手机抽屉打开时把当前项滚入可视区，长导航下也能一眼看到所在位置
watch(mobileOpen, async open => {
  if (!open) return
  await nextTick()
  sidebarEl.value?.querySelector('.router-link-active')?.scrollIntoView({ block: 'nearest' })
})
const assistantOpen = ref(false)
const assistantWide = ref(false)
const primaryNavigation = moduleNavigation.filter(group => group.id !== 'platform')
const platformNavigation = moduleNavigation.filter(group => group.id === 'platform')

function logout() {
  clearToken()
  router.replace('/login')
}
</script>

<template>
  <div class="min-h-screen bg-ink text-text">
    <Button :class="['mobile-menu', mobileOpen && 'mobile-menu--hidden']" variant="outline" size="icon" aria-label="打开导航" @click="mobileOpen = true"><Menu :size="19" /></Button>
    <div v-if="mobileOpen" class="fixed inset-0 z-30 bg-slate-900/30 lg:hidden" @click="mobileOpen = false" />
    <aside ref="sidebarEl" :class="['sidebar', collapsed && 'sidebar--collapsed', mobileOpen && 'sidebar--open']">
      <RouterLink to="/" class="sidebar-brand" aria-label="工作台首页" :title="collapsed ? '工作台首页' : undefined" @click="mobileOpen = false">
        <img v-if="collapsed" src="/work-mark.png" class="sidebar-brand__mark" alt="" />
        <img v-else src="/work-wordmark.png" class="sidebar-brand__wordmark" alt="" />
      </RouterLink>
      <Button class="nav-link m-2" variant="ghost" aria-label="随手记" title="随手记 · Ctrl / ⌘ + Shift + J" @click="captures.quickOpen = true; mobileOpen = false"><span aria-hidden="true">＋</span><span v-if="!collapsed">随手记</span></Button>
      <Button class="nav-link mx-2 mb-1 lg:hidden" variant="ghost" aria-label="打开命令面板" @click="paletteOpen = true; mobileOpen = false">
        <Command :size="18" /><span v-if="!collapsed">命令面板</span>
      </Button>
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
        <!-- 手机上「收起侧栏」是桌面操作：.nav-link 的 display:flex 会盖过工具类，
             必须用普通元素承载 hidden/lg:block 才能真正按断点切换 -->
        <div class="hidden lg:block">
          <Button class="nav-link w-full" variant="ghost" :aria-label="collapsed ? '展开侧栏' : '收起侧栏'" @click="collapsed = !collapsed">
            <ChevronLeft :class="collapsed && 'rotate-180'" :size="18" /><span v-if="!collapsed">收起侧栏</span>
          </Button>
        </div>
        <div class="lg:hidden">
          <Button class="nav-link mt-1 w-full" variant="ghost" aria-label="关闭导航" @click="mobileOpen = false">
            <X :size="16" /><span v-if="!collapsed">关闭导航</span>
          </Button>
        </div>
        <Button class="nav-link mt-1 w-full" variant="ghost" aria-label="退出登录" @click="logout">
          <LogOut :size="18" /><span v-if="!collapsed">退出登录</span>
        </Button>
      </div>
    </aside>
    <main :class="['main-content', collapsed && 'main-content--wide', assistantOpen && 'main-content--assistant', assistantOpen && assistantWide && 'main-content--assistant-wide']">
      <RouterView />
      <AiDock @open-change="assistantOpen = $event" @wide-change="assistantWide = $event" />
      <Dialog :open="captures.quickOpen" @update:open="captures.quickOpen = $event">
        <DialogContent class="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>随手记</DialogTitle>
            <DialogDescription>快速记一条，保存到「随手记」列表。</DialogDescription>
          </DialogHeader>
          <CaptureComposer v-if="captures.quickOpen" autofocus />
        </DialogContent>
      </Dialog>
    </main>
    <ConfirmDialog />
    <CommandPalette :open="paletteOpen" @close="paletteOpen = false" />
  </div>
</template>
