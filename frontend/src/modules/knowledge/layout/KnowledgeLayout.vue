<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import DocumentEditor from '../components/DocumentEditor.vue'
import EntryEditor from '../components/EntryEditor.vue'
import TagEditor from '../components/TagEditor.vue'
import { useKnowledgeStore } from '../store'

const store = useKnowledgeStore()
const route = useRoute()
function openLinkedKnowledge() {
  const document = store.documents.find(item => item.id === route.query.document)
  const entry = store.entries.find(item => item.id === route.query.entry)
  if (document) store.openDocument(document)
  else if (entry) store.openEntry(entry)
}
onMounted(async () => { await store.initialize(); openLinkedKnowledge() })
watch(() => [route.query.document, route.query.entry], openLinkedKnowledge)
// 兜底：SSE 断线期间子菜单切换也可能有旧数据，超过 10s 未同步就静默重拉
let lastSync = 0
watch(() => route.name, () => {
  if (!store.initialized || Date.now() - lastSync < 10_000) return
  lastSync = Date.now()
  void store.refresh()
})
</script>

<template>
  <p v-if="store.error" class="error-banner" role="alert">
    {{ store.error }} <button @click="store.initialize()">重试</button>
  </p>
  <div v-if="store.loading" class="loading-bar" aria-label="正在加载" />
  <RouterView />
  <DocumentEditor />
  <EntryEditor />
  <TagEditor />
</template>
