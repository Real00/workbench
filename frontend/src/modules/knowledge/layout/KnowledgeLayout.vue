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
