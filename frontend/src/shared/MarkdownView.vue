<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdown } from './markdown'

const props = defineProps<{ source: string }>()
const html = computed(() => renderMarkdown(props.source))
</script>

<template>
  <!-- marked 出 HTML 后经 DOMPurify 消毒，再 v-html -->
  <div class="md-body" v-html="html" />
</template>
