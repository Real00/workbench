<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import DocumentEditor from '../components/DocumentEditor.vue'
import EntryEditor from '../components/EntryEditor.vue'
import TagEditor from '../components/TagEditor.vue'
import { useKnowledgeStore } from '../store'

const store = useKnowledgeStore()
onMounted(() => store.initialize())
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
