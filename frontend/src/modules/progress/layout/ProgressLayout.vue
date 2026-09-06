<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import MemberEditor from '../components/MemberEditor.vue'
import ProjectEditor from '../components/ProjectEditor.vue'
import TaskEditor from '../components/TaskEditor.vue'
import { useProgressStore } from '../store'

const store = useProgressStore()
const route = useRoute()
function openLinkedTask() {
  const item = store.tasks.find(task => task.id === route.query.task)
  if (item) store.openTask(item)
}
onMounted(async () => { await store.initialize(); openLinkedTask() })
watch(() => route.query.task, openLinkedTask)
// 兜底：SSE 断线期间子菜单切换也可能有旧数据，超过 10s 未同步就静默重拉
let lastSync = 0
watch(() => route.name, () => {
  if (!store.initialized || Date.now() - lastSync < 10_000) return
  lastSync = Date.now()
  void store.refreshAll()
})
</script>

<template>
  <p v-if="store.error" class="error-banner" role="alert">
    {{ store.error }} <button @click="store.initialize()">重试</button>
  </p>
  <div v-if="store.loading" class="loading-bar" aria-label="正在加载" />
  <RouterView />
  <TaskEditor />
  <MemberEditor />
  <ProjectEditor />
</template>
