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
  await Promise.allSettled([
    !progress.initialized ? progress.initialize() : Promise.resolve(),
    !knowledge.initialized ? knowledge.initialize() : Promise.resolve(),
    captureApi.list('', false, 0).then(list => { recentCaptures.value = list.slice(0, 50) }).catch(() => {}),
  ])
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
    description="搜索任务、文档、速记，或执行命令"
    @update:open="onOpenChange"
  >
    <CommandInput placeholder="搜索任务、文档、速记，或执行命令…" />
    <CommandPaletteList :commands="commands" @execute="execute" />
  </CommandDialog>
</template>
