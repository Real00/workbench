<script setup lang="ts">
import { computed } from 'vue'
import {
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList,
  useCommand,
} from '@/components/ui/command'
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

const props = defineProps<{ commands: PaletteItem[] }>()
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
</script>

<template>
  <CommandList>
    <CommandEmpty>没有匹配的结果</CommandEmpty>
    <CommandGroup v-for="group in groups" :key="group.kind" :heading="group.heading">
      <CommandItem
        v-for="item in group.items"
        :key="item.id"
        :value="[item.label, item.hint, ...(item.keywords ?? [])].join(' ')"
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
