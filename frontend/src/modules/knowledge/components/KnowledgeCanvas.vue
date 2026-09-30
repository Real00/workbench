<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useMediaQuery } from '@vueuse/core'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import type { Node, NodeDragEvent, NodeMouseEvent } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import { apiError } from '../../../shared/api/client'
import { useKnowledgeStore } from '../store'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

import { LayoutGrid, Maximize, Maximize2, Minus, Plus, X } from '@lucide/vue'
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

// 卡片估尺寸，与 .knowledge-doc-node 的 280px 宽度对应，高度按常见内容估算。
// 只用于显示层避碰，不改动文档保存的坐标。
const NODE_WIDTH = 300
const NODE_HEIGHT = 170
const NODE_GAP = 20

type Spot = { x: number; y: number }

function spotsOverlap(a: Spot, b: Spot) {
  return a.x < b.x + NODE_WIDTH + NODE_GAP && b.x < a.x + NODE_WIDTH + NODE_GAP
    && a.y < b.y + NODE_HEIGHT + NODE_GAP && b.y < a.y + NODE_HEIGHT + NODE_GAP
}

function findFreeSpot(anchor: Spot, placed: Spot[]) {
  for (let step = 1; step <= 400; step++) {
    const candidate: Spot = {
      x: anchor.x + (step % 20) * (NODE_WIDTH + NODE_GAP),
      y: anchor.y + Math.floor(step / 20) * (NODE_HEIGHT + NODE_GAP),
    }
    if (!placed.some(spot => spotsOverlap(candidate, spot))) return candidate
  }
  return anchor
}

// 显示层避碰：保存的坐标不动，重叠的卡片依次向右下错开，保证每篇文档都可见、可选。
const nodes = computed<Node[]>(() => {
  const placed: Spot[] = []
  return props.documents.map(document => {
    const anchor: Spot = { x: document.canvas_x, y: document.canvas_y }
    const position = placed.some(spot => spotsOverlap(anchor, spot)) ? findFreeSpot(anchor, placed) : anchor
    placed.push(position)
    return {
      id: document.id,
      type: 'document',
      position,
      data: { document },
      connectable: false,
      draggable: canDrag.value,
    }
  })
})

const hasStackedCards = computed(() => {
  const spots = props.documents.map(document => ({ x: document.canvas_x, y: document.canvas_y }))
  for (let i = 0; i < spots.length; i++) {
    for (let j = i + 1; j < spots.length; j++) {
      const a = spots[i]
      const b = spots[j]
      if (a && b && spotsOverlap(a, b)) return true
    }
  }
  return false
})

const nodeSummary = computed(() => props.searching ? `命中 ${props.documents.length} 篇文档` : `${props.documents.length} 篇文档`)

/** 整理布局：显式操作，把全部卡片按网格重排并保存位置；与“显示全部”（仅缩放视野）语义不同 */
async function tidyLayout() {
  const columns = Math.max(1, Math.ceil(Math.sqrt(props.documents.length)))
  try {
    await Promise.all(props.documents.map((document, index) => store.moveDocument(
      document.id,
      80 + (index % columns) * (NODE_WIDTH + 48),
      80 + Math.floor(index / columns) * (NODE_HEIGHT + 40),
    )))
  } catch (cause) {
    store.error = apiError(cause)
    return
  }
  await nextTick()
  void resetView()
}

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
      <header v-if="fullscreen" class="absolute inset-x-0 top-0 z-10 flex items-center justify-between gap-3 border-b border-line bg-panel/95 px-4 py-3 backdrop-blur">
        <div class="flex min-w-0 items-baseline gap-3">
          <h2 class="font-display text-lg text-text">文档画布</h2>
          <p class="truncate text-xs text-muted-foreground">
            {{ nodeSummary }} · 仅文档，条目与标签请在列表视图查看
            <span v-if="hasStackedCards" class="text-amber-600">；有卡片坐标重叠，已自动错开显示</span>
          </p>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          <Tooltip>
            <TooltipTrigger as-child>
              <Button type="button" size="sm" variant="outline" :disabled="!documents.length || searching" @click="tidyLayout"><LayoutGrid :size="14" />整理布局</Button>
            </TooltipTrigger>
            <TooltipContent>把全部卡片按网格重新排列，并保存新位置</TooltipContent>
          </Tooltip>
          <Button aria-label="关闭全屏画布" variant="ghost" size="icon" @click="fullscreen = false"><X :size="18" /></Button>
        </div>
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
      <div v-if="!fullscreen" class="absolute right-3 top-3 z-10 flex max-w-[calc(100%-24px)] flex-wrap items-center justify-end gap-x-2 gap-y-1 rounded-lg border border-line bg-panel/95 px-3 py-2 text-xs text-muted-foreground backdrop-blur">
        <span>{{ nodeSummary }} · 仅文档，条目与标签请在列表视图查看</span>
        <span v-if="hasStackedCards" class="text-amber-600">有卡片坐标重叠，已自动错开显示</span>
        <Tooltip>
          <TooltipTrigger as-child>
            <Button type="button" size="sm" variant="outline" :disabled="!documents.length || searching" @click="tidyLayout"><LayoutGrid :size="14" />整理布局</Button>
          </TooltipTrigger>
          <TooltipContent>把全部卡片按网格重新排列，并保存新位置</TooltipContent>
        </Tooltip>
      </div>
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
