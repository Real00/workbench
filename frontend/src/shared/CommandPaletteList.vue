<script setup lang="ts">
import { computed } from 'vue'
import {
  CommandGroup,
  CommandItem,
  CommandList,
  useCommand,
} from '@/components/ui/command'
import { Button } from '@/components/ui/button'
import { type CommandItem as PaletteItem, type CommandKind } from './command-index'

const KIND_HEADING: Record<CommandKind, string> = {
  action: '命令',
  nav: '页面',
  task: '任务',
  member: '成员',
  project: '项目',
  entry: '条目',
  document: '文档',
  capture: '随手记',
}

const SEARCH_SCOPE = '已搜索：任务、成员、项目、知识条目与文档、随手记，以及页面和命令；数据在面板打开时自动加载'

const props = defineProps<{ commands: PaletteItem[]; loading?: boolean }>()
const emit = defineEmits<{ execute: [item: PaletteItem] }>()
const { filterState } = useCommand()

const items = computed(() => {
  if (!filterState.search.trim()) return props.commands.filter(item => item.default)
  return props.commands
})

const groups = computed(() => {
  const buckets = new Map<CommandKind, PaletteItem[]>()
  for (const item of items.value) {
    const list = buckets.get(item.kind) ?? []
    list.push(item)
    buckets.set(item.kind, list)
  }
  return [...buckets.entries()].map(([kind, groupItems]) => ({
    kind,
    heading: KIND_HEADING[kind],
    items: groupItems,
  }))
})

const searching = computed(() => filterState.search.trim().length > 0)
const showLoading = computed(() => searching.value && Boolean(props.loading))
const showEmpty = computed(() => searching.value && !props.loading && filterState.filtered.count === 0)

function clearSearch() {
  filterState.search = ''
  // 按钮随空态一起卸载，把焦点交还搜索框，便于继续输入
  document.querySelector<HTMLInputElement>('[data-slot="command-input"]')?.focus()
}
</script>

<template>
  <CommandList>
    <div v-if="showLoading" class="py-6 text-center text-sm text-muted-foreground">
      正在加载可搜索内容…
    </div>
    <div v-else-if="showEmpty" class="flex flex-col items-center gap-1.5 px-6 py-6 text-center text-sm">
      <p class="text-text">没有匹配「{{ filterState.search.trim() }}」的结果</p>
      <p class="text-xs leading-relaxed text-muted-foreground">{{ SEARCH_SCOPE }}</p>
      <Button class="mt-2" variant="outline" size="sm" @click="clearSearch">清除搜索词，返回全部</Button>
    </div>
    <CommandGroup v-for="group in groups" :key="group.kind" :heading="group.heading">
      <CommandItem
        v-for="item in group.items"
        :key="item.id"
        :value="[item.label, item.hint, ...(item.keywords ?? [])].join(' ')"
        :title="[item.label, item.hint].filter(Boolean).join(' · ')"
        @select="emit('execute', item)"
      >
        <component :is="item.icon" v-if="item.icon" class="text-cyan" />
        <span class="min-w-0 flex-1 truncate">{{ item.label }}</span>
        <span class="sr-only">{{ (item.keywords ?? []).join(' ') }}</span>
        <span v-if="item.hint" class="text-muted-foreground max-w-[45%] truncate text-xs">{{ item.hint }}</span>
      </CommandItem>
    </CommandGroup>
  </CommandList>
</template>
