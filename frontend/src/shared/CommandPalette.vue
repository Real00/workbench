<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { House } from '@lucide/vue'
import { useRouter } from 'vue-router'
import { CommandDialog, CommandInput } from '@/components/ui/command'
import { useCaptureStore, captureApi, type Capture } from '../modules/capture/store'
import { useKnowledgeStore } from '../modules/knowledge/store'
import { useProgressStore } from '../modules/progress/store'
import { moduleNavigation } from '../app/modules'
import { buildCommands, type CommandItem } from './command-index'
import CommandPaletteList from './CommandPaletteList.vue'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const progress = useProgressStore()
const knowledge = useKnowledgeStore()
const captures = useCaptureStore()
const router = useRouter()
const recentCaptures = ref<Capture[]>([])
// 打开时可能仍在加载任务/知识/随手记数据，列表据此区分「加载中」与「确实无命中」
const preparing = ref(false)

const commands = computed(() => buildCommands({
  router,
  tasks: progress.tasks,
  members: progress.members,
  projects: progress.projects,
  entries: knowledge.entries,
  documents: knowledge.documents,
  captures: recentCaptures.value,
  navItems: [
    { label: '工作台首页', to: '/', icon: House },
    ...moduleNavigation.flatMap(group => group.items.map(item => ({ label: item.label, to: item.to, icon: item.icon }))),
  ],
  createTask: () => {
    progress.openTask()
    void router.push('/progress/tasks')
  },
  quickCapture: () => { captures.quickOpen = true },
  askAi: () => window.dispatchEvent(new CustomEvent('pulse-compose', { detail: '' })),
}))

watch(() => props.open, async open => {
  if (!open) return
  preparing.value = true
  await Promise.allSettled([
    !progress.initialized ? progress.initialize() : Promise.resolve(),
    !knowledge.initialized ? knowledge.initialize() : Promise.resolve(),
    captureApi.list('', false, 0).then(list => { recentCaptures.value = list.slice(0, 50) }).catch(() => {}),
  ])
  preparing.value = false
})

function execute(item?: CommandItem) {
  if (!item) return
  emit('close')
  item.run()
}

function onOpenChange(open: boolean) {
  if (!open) emit('close')
}
</script>

<template>
  <CommandDialog
    :open="open"
    title="命令面板"
    description="搜索任务、文档、随手记，或执行命令"
    class="sm:max-w-[600px]"
    @update:open="onOpenChange"
  >
    <CommandInput placeholder="搜索任务、文档、随手记，或执行命令…" />
    <CommandPaletteList :commands="commands" :loading="preparing" @execute="execute" />
    <div class="hidden items-center justify-end gap-4 border-t border-line px-3 py-2 text-[11px] text-muted-foreground sm:flex">
      <span class="flex items-center gap-1"><kbd class="rounded border border-line bg-panel-2 px-1 font-mono text-[10px] text-text">↑↓</kbd>选择</span>
      <span class="flex items-center gap-1"><kbd class="rounded border border-line bg-panel-2 px-1 font-mono text-[10px] text-text">Enter</kbd>打开</span>
      <span class="flex items-center gap-1"><kbd class="rounded border border-line bg-panel-2 px-1 font-mono text-[10px] text-text">Esc</kbd>关闭</span>
    </div>
  </CommandDialog>
</template>
