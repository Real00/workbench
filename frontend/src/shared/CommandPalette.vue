<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { House } from '@lucide/vue'
import { useRouter } from 'vue-router'
import { useCaptureStore, captureApi, type Capture } from '../modules/capture/store'
import { useKnowledgeStore } from '../modules/knowledge/store'
import { useProgressStore } from '../modules/progress/store'
import { moduleNavigation } from '../app/modules'
import { useDialogFocus } from './useDialogFocus'
import { buildCommands, filterCommands, type CommandItem } from './command-index'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const progress = useProgressStore()
const knowledge = useKnowledgeStore()
const captures = useCaptureStore()
const router = useRouter()

const query = ref('')
const active = ref(0)
const recentCaptures = ref<Capture[]>([])
const panel = ref<HTMLElement | null>(null)
useDialogFocus(panel, () => props.open, () => emit('close'))

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
const items = computed(() => filterCommands(commands.value, query.value))

watch(() => props.open, async open => {
  if (!open) return
  query.value = ''
  active.value = 0
  await Promise.allSettled([
    !progress.initialized ? progress.initialize() : Promise.resolve(),
    !knowledge.initialized ? knowledge.initialize() : Promise.resolve(),
    captureApi.list('', false, 0).then(list => { recentCaptures.value = list.slice(0, 50) }).catch(() => {}),
  ])
})

watch(items, list => { if (active.value >= list.length) active.value = Math.max(list.length - 1, 0) })

function move(step: number) {
  if (!items.value.length) return
  active.value = (active.value + step + items.value.length) % items.value.length
  scrollActiveIntoView()
}

function scrollActiveIntoView() {
  requestAnimationFrame(() => {
    panel.value?.querySelector<HTMLElement>('.command-item--active')?.scrollIntoView({ block: 'nearest' })
  })
}

function execute(item?: CommandItem) {
  if (!item) return
  emit('close')
  item.run()
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="command-overlay" @click.self="emit('close')">
      <div ref="panel" class="command-palette" role="dialog" aria-modal="true" aria-label="命令面板">
        <input
          v-model="query"
          class="command-input"
          placeholder="搜索任务、文档、速记，或执行命令…"
          aria-label="搜索命令"
          @keydown.down.prevent="move(1)"
          @keydown.up.prevent="move(-1)"
          @keydown.enter.prevent="execute(items[active])"
        >
        <div class="command-list" role="listbox" aria-label="匹配结果">
          <button
            v-for="(item, index) in items"
            :key="item.id"
            class="command-item"
            :class="{ 'command-item--active': index === active }"
            role="option"
            :aria-selected="index === active"
            @click="execute(item)"
            @mousemove="active = index"
          >
            <component :is="item.icon" v-if="item.icon" :size="15" class="shrink-0 text-cyan" />
            <span class="command-item__label">{{ item.label }}</span>
            <span v-if="item.hint" class="command-item__hint">{{ item.hint }}</span>
          </button>
          <p v-if="!items.length" class="empty-inline">没有匹配的结果</p>
        </div>
        <footer class="command-foot"><span>↑↓ 选择</span><span>Enter 打开</span><span>Esc 关闭</span></footer>
      </div>
    </div>
  </Teleport>
</template>
