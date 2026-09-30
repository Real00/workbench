<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useMediaQuery } from '@vueuse/core'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import type { Node, NodeDragEvent, NodeMouseEvent } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import { useKnowledgeStore } from '../store'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

import { Maximize, Maximize2, Minus, Plus, X } from '@lucide/vue'
import type { KnowledgeDocument } from '../types'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

const props = defineProps<{ documents: KnowledgeDocument[]; searching: boolean }>()
const { fitView, zoomIn, zoomOut, viewport } = useVueFlow('knowledge-canvas')
const resetView = () => fitView({ padding: .2, maxZoom: 1 })
watch(() => props.documents.map(document => document.id).join(','), async () => { await nextTick(); void resetView() })
const store = useKnowledgeStore()
const isNarrow = useMediaQuery('(max-width: 768px)')
const fullscreen = ref(false)
const canDrag = computed(() => !isNarrow.value)

const nodes = computed<Node[]>(() => props.documents.map(document => ({
  id: document.id,
  type: 'document',
  position: { x: document.canvas_x, y: document.canvas_y },
  data: { document },
  connectable: false,
  draggable: canDrag.value,
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
  if (!canDrag.value) return
  await store.moveDocument(event.node.id, Math.round(event.node.position.x), Math.round(event.node.position.y))
}

function onNodeClick(event: NodeMouseEvent) {
  const document = store.documents.find(item => item.id === event.node.id)
  if (document) store.openDocument(document)
}

watch(fullscreen, async (open) => {
  if (!open) return
  await nextTick()
  void resetView()
})
</script>

<template>
  <div>
    <div v-if="isNarrow && !fullscreen" class="rounded-xl border border-line bg-panel p-4">
      <div class="mb-3 flex items-center justify-between gap-2">
        <p class="text-sm text-muted-foreground">手机默认用列表浏览；需要空间关系时再打开全屏画布。</p>
        <Button type="button" size="sm" variant="outline" :disabled="!documents.length" @click="fullscreen = true">
          <Maximize2 :size="14" />全屏画布
        </Button>
      </div>
      <ul v-if="documents.length" class="divide-y divide-line">
        <li v-for="document in documents" :key="document.id">
          <button type="button" class="flex w-full flex-col gap-1 py-3 text-left" @click="store.openDocument(document)">
            <b class="text-sm text-text">{{ document.title }}</b>
            <span class="text-[12px] text-muted-foreground">
              {{ document.tag_ids.map(tagName).filter(Boolean).join(' · ') || '无标签' }}
              · {{ document.entry_ids.length }} 条目
            </span>
          </button>
        </li>
      </ul>
      <p v-else class="empty-inline">{{ searching ? '没有匹配的文档，请调整搜索关键词。' : '创建第一篇文档后，在这里整理知识。' }}</p>
    </div>

    <div v-else class="knowledge-canvas rounded-xl border border-line bg-panel" :class="fullscreen && 'knowledge-canvas--fullscreen'">
      <header v-if="fullscreen" class="absolute inset-x-0 top-0 z-10 flex items-center justify-between border-b border-line bg-panel/95 px-4 py-3 backdrop-blur">
        <h2 class="font-display text-lg text-text">知识画布</h2>
        <Button aria-label="关闭全屏画布" variant="ghost" size="icon" @click="fullscreen = false"><X :size="18" /></Button>
      </header>
      <VueFlow
        id="knowledge-canvas"
        :nodes="nodes"
        :edges="[]"
        :min-zoom=".2"
        :max-zoom="1"
        fit-view-on-init
        :nodes-connectable="false"
        :nodes-draggable="canDrag"
        @node-drag-stop="onDragStop"
        @node-click="onNodeClick"
      >
        <template #node-document="{ data }">
          <article v-if="data.document" class="knowledge-doc-node">
            <p class="font-display text-sm text-text">{{ data.document.title }}</p>
            <div class="mt-2 flex flex-wrap gap-1">
              <Badge v-for="tagId in data.document.tag_ids" :key="tagId" variant="secondary">{{ tagName(tagId) }}</Badge>
            </div>
            <ul class="mt-3 space-y-1 text-[12px] text-text-secondary">
              <li v-for="entryId in data.document.entry_ids.slice(0, 6)" :key="entryId">{{ entrySummary(entryId) }}</li>
              <li v-if="!data.document.entry_ids.length" class="text-muted-foreground">尚未关联条目</li>
            </ul>
          </article>
        </template>
      </VueFlow>
      <p v-if="!documents.length" class="absolute inset-0 grid place-items-center text-sm text-muted-foreground pointer-events-none">{{ searching ? '没有匹配的文档，请调整搜索关键词。' : '创建第一篇文档后，在这里整理知识。' }}</p>
      <div class="canvas-controls" role="group" aria-label="画布缩放">
        <Tooltip>
          <TooltipTrigger as-child>
            <Button aria-label="缩小画布" variant="ghost" size="icon" @click="zoomOut()"><Minus :size="16" /></Button>
          </TooltipTrigger>
          <TooltipContent>缩小</TooltipContent>
        </Tooltip>
        <span class="w-12 text-center text-xs text-muted-foreground">{{ Math.round(viewport.zoom * 100) }}%</span>
        <Tooltip>
          <TooltipTrigger as-child>
            <Button aria-label="放大画布" variant="ghost" size="icon" @click="zoomIn()"><Plus :size="16" /></Button>
          </TooltipTrigger>
          <TooltipContent>放大</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger as-child>
            <Button aria-label="显示全部节点" variant="ghost" size="icon" @click="resetView"><Maximize :size="16" /></Button>
          </TooltipTrigger>
          <TooltipContent>显示全部</TooltipContent>
        </Tooltip>
      </div>
    </div>
  </div>
</template>
