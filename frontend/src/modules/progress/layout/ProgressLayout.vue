<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import MemberEditor from '../components/MemberEditor.vue'
import ProjectEditor from '../components/ProjectEditor.vue'
import TaskEditor from '../components/TaskEditor.vue'
import { useProgressStore } from '../store'

const store = useProgressStore()
onMounted(() => store.initialize())
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
