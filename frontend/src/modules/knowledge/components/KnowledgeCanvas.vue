<script setup lang="ts">
import { computed } from 'vue'
import { VueFlow } from '@vue-flow/core'
import type { Node, NodeDragEvent, NodeMouseEvent } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import { useKnowledgeStore } from '../store'

const store = useKnowledgeStore()

const nodes = computed<Node[]>(() => store.documents.map(document => ({
  id: document.id,
  type: 'document',
  position: { x: document.canvas_x, y: document.canvas_y },
  data: { document },
  connectable: false,
  draggable: true,
})))

function tagName(id: string) {
  return store.tagMap.get(id)?.name ?? id
}

function entrySummary(id: string) {
  const entry = store.entryMap.get(id)
  if (!entry) return ''
  const value = entry.value.length > 48 ? `${entry.value.slice(0, 48)}…` : entry.value
  return `${entry.key}：${value}`
}

async function onDragStop(event: NodeDragEvent) {
  await store.moveDocument(event.node.id, Math.round(event.node.position.x), Math.round(event.node.position.y))
}

function onNodeClick(event: NodeMouseEvent) {
  const document = store.documents.find(item => item.id === event.node.id)
  if (document) store.openDocument(document)
}
</script>

<template>
  <div class="knowledge-canvas rounded-xl border border-line bg-panel">
    <VueFlow :nodes="nodes" :edges="[]" fit-view-on-init :nodes-connectable="false" @node-drag-stop="onDragStop" @node-click="onNodeClick">
      <template #node-document="{ data }">
        <article v-if="data.document" class="knowledge-doc-node">
          <p class="font-display text-sm text-white">{{ data.document.title }}</p>
          <div class="mt-2 flex flex-wrap gap-1">
            <span v-for="tagId in data.document.tag_ids" :key="tagId" class="skill-chip">{{ tagName(tagId) }}</span>
          </div>
          <ul class="mt-3 space-y-1 text-[11px] text-slate-300">
            <li v-for="entryId in data.document.entry_ids.slice(0, 6)" :key="entryId">{{ entrySummary(entryId) }}</li>
            <li v-if="!data.document.entry_ids.length" class="text-muted">尚未关联条目</li>
          </ul>
        </article>
      </template>
    </VueFlow>
  </div>
</template>
