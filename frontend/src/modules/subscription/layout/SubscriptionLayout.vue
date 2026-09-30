<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { useSubscriptionStore } from '../store'
import { Button } from '@/components/ui/button'

const store = useSubscriptionStore()
const route = useRoute()

onMounted(() => { void store.initialize() })

let lastSync = 0
watch(() => route.name, () => {
  if (!store.initialized || Date.now() - lastSync < 10_000) return
  lastSync = Date.now()
  void store.refresh()
})
</script>

<template>
  <div class="page-wrap">
    <p v-if="store.error" class="error-banner" role="alert">
      {{ store.error }}
      <Button variant="link" class="h-auto px-0 text-inherit" @click="store.initialize()">重试</Button>
    </p>
    <div v-if="store.loading" class="loading-bar" aria-label="正在加载" />
    <div class="content-tabs mb-4 flex gap-2 overflow-x-auto pb-1">
      <RouterLink
        v-for="item in [
          { to: '/subscription', label: '订阅源' },
          { to: '/subscription/plugins', label: '插件' },
          { to: '/subscription/articles', label: '文章' },
        ]"
        :key="item.to"
        :to="item.to"
        class="shrink-0 rounded-lg px-3 py-1.5 text-sm text-muted-foreground hover:bg-panel-2"
        active-class="!bg-panel-2 !text-text font-medium"
      >
        {{ item.label }}
      </RouterLink>
    </div>
    <RouterView />
  </div>
</template>
