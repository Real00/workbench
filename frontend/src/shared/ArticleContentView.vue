<script setup lang="ts">
import { computed } from 'vue'
import { sanitizeHtml } from './html'
import { renderMarkdown } from './markdown'

const props = defineProps<{
  content: string
  format: 'markdown' | 'html'
}>()

const html = computed(() =>
  props.format === 'markdown' ? renderMarkdown(props.content) : sanitizeHtml(props.content),
)
</script>

<template>
  <div class="md-body article-content" v-html="html" />
</template>
