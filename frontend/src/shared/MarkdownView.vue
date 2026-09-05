<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdown } from './markdown'

const props = defineProps<{ source: string }>()
const html = computed(() => renderMarkdown(props.source))
</script>

<template>
  <!-- source 经 renderMarkdown 全量转义后才生成 HTML，无注入面 -->
  <div class="md-body" v-html="html" />
</template>
