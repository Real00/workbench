<script setup lang="ts">
import { computed, nextTick, watch } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import type { Node, NodeDragEvent, NodeMouseEvent } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import { useKnowledgeStore } from '../store'

import { Maximize, Minus, Plus } from '@lucide/vue'
import type { KnowledgeDocument } from '../types'

const props = defineProps<{ documents: KnowledgeDocument[]; searching: boolean }>()
const { fitView, zoomIn, zoomOut, viewport } = useVueFlow('knowledge-canvas')
const resetView = () => fitView({ padding: .2, maxZoom: 1 })
watch(() => props.documents.map(document => document.id).join(','), async () => { await nextTick(); void resetView() })
const store = useKnowledgeStore()

const nodes = computed<Node[]>(() => props.documents.map(document => ({
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
    <VueFlow id="knowledge-canvas" :nodes="nodes" :edges="[]" :min-zoom=".2" :max-zoom="1" fit-view-on-init :nodes-connectable="false" @node-drag-stop="onDragStop" @node-click="onNodeClick">
      <template #node-document="{ data }">
        <article v-if="data.document" class="knowledge-doc-node">
          <p class="font-display text-sm text-white">{{ data.document.title }}</p>
          <div class="mt-2 flex flex-wrap gap-1">
            <span v-for="tagId in data.document.tag_ids" :key="tagId" class="skill-chip">{{ tagName(tagId) }}</span>
          </div>
          <ul class="mt-3 space-y-1 text-[12px] text-slate-300">
            <li v-for="entryId in data.document.entry_ids.slice(0, 6)" :key="entryId">{{ entrySummary(entryId) }}</li>
            <li v-if="!data.document.entry_ids.length" class="text-muted">尚未关联条目</li>
          </ul>
        </article>
      </template>
    </VueFlow>
    <p v-if="!documents.length" class="absolute inset-0 grid place-items-center text-sm text-muted pointer-events-none">{{ searching ? '没有匹配的文档，请调整搜索关键词。' : '创建第一篇文档后，在这里整理知识。' }}</p>
    <div class="canvas-controls" role="group" aria-label="画布缩放">
      <button class="icon-btn" aria-label="缩小画布" @click="zoomOut()"><Minus :size="16" /></button>
      <span class="w-12 text-center text-xs text-muted">{{ Math.round(viewport.zoom * 100) }}%</span>
      <button class="icon-btn" aria-label="放大画布" @click="zoomIn()"><Plus :size="16" /></button>
      <button class="icon-btn" aria-label="显示全部节点" @click="resetView"><Maximize :size="16" /></button>
    </div>
  </div>
</template>
