<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { FileText, Link2, Paperclip, Trash2, Upload } from '@lucide/vue'
import { progressApi } from '../api'
import { useProgressStore } from '../store'
import { formatBytes, resourceAccept, resourceKindMap, type TaskResource } from '../types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const store = useProgressStore()
const fileInput = ref<HTMLInputElement | null>(null)
const linkName = ref('')
const linkUrl = ref('')
const previews = ref<Record<string, string>>({})
const resources = computed(() => [...(store.editingTask?.resources ?? [])].reverse())

function revokePreviews() {
  Object.values(previews.value).forEach(url => URL.revokeObjectURL(url))
  previews.value = {}
}

watch(() => [store.editingTask?.id, store.editingTask?.resources.map(item => item.id).join(',')], async () => {
  revokePreviews()
  const task = store.editingTask
  if (!task) return
  const next: Record<string, string> = {}
  for (const resource of task.resources) {
    if (resource.kind !== 'image') continue
    try {
      const blob = await progressApi.downloadResource(task.id, resource.id)
      next[resource.id] = URL.createObjectURL(blob)
    } catch {
      /* preview is optional */
    }
  }
  previews.value = next
}, { immediate: true })

onUnmounted(revokePreviews)

async function onFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !store.editingTask) return
  const ok = await store.uploadTaskResource(store.editingTask.id, file)
  if (ok) flashSaved()
}

/** 资源与记录一样是独立提交：成功就地反馈，且不算主表单的未保存改动（审计 A23） */
const savedFlash = ref(false)
let flashTimer: ReturnType<typeof setTimeout> | undefined
function flashSaved() {
  savedFlash.value = true
  clearTimeout(flashTimer)
  flashTimer = setTimeout(() => { savedFlash.value = false }, 2000)
}

async function addLink() {
  if (!store.editingTask || !linkUrl.value.trim()) return
  const ok = await store.addTaskLink(store.editingTask.id, {
    name: linkName.value.trim(),
    url: linkUrl.value.trim(),
  })
  if (ok) {
    linkName.value = ''
    linkUrl.value = ''
    flashSaved()
  }
}

async function openResource(resource: TaskResource) {
  if (resource.kind === 'link' && resource.url) {
    window.open(resource.url, '_blank', 'noopener')
    return
  }
  if (!store.editingTask) return
  const blob = await progressApi.downloadResource(store.editingTask.id, resource.id)
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = resource.name
  if (resource.kind === 'image') anchor.target = '_blank'
  anchor.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <section class="rounded-xl border border-line bg-panel-2 p-4">
    <p class="eyebrow">资源</p>
    <p class="mt-1 text-[12px] text-muted-foreground">图片、文档或外链，单文件不超过 20MB。上传与保存链接都是立即写入，不受底部「取消」影响。</p>
    <div class="mt-3 flex flex-wrap items-center gap-2">
      <input ref="fileInput" class="sr-only" type="file" :accept="resourceAccept" @change="onFile" />
      <Button type="button" :disabled="store.saving" @click="fileInput?.click()" variant="outline"><Upload :size="14" />上传并保存</Button>
      <span v-if="savedFlash" class="saved-flash" role="status">已保存</span>
    </div>
    <div class="mt-3 grid gap-2">
      <label class="field-label">外链名称<Input v-model="linkName" maxlength="200" placeholder="可选" /></label>
      <label class="field-label">链接地址<Input v-model="linkUrl" maxlength="2000" placeholder="https://" /></label>
    </div>
    <Button type="button" :disabled="store.saving || !linkUrl.trim()" @click="addLink" class="mt-3" variant="outline"><Link2 :size="14" />保存链接</Button>
    <ul v-if="resources.length" class="mt-4 grid gap-2">
      <li v-for="resource in resources" :key="resource.id" class="resource-item">
        <button type="button" class="resource-main" @click="openResource(resource)">
          <img v-if="previews[resource.id]" :src="previews[resource.id]" :alt="resource.name" width="42" height="42" class="resource-thumb" />
          <span v-else class="resource-icon">
            <FileText v-if="resource.kind === 'document'" :size="16" />
            <Link2 v-else-if="resource.kind === 'link'" :size="16" />
            <Paperclip v-else :size="16" />
          </span>
          <span class="min-w-0 flex-1 text-left">
            <b>{{ resource.name }}</b>
            <small>{{ resourceKindMap[resource.kind] }}<template v-if="resource.size_bytes"> · {{ formatBytes(resource.size_bytes) }}</template></small>
          </span>
        </button>
        <Button type="button" aria-label="删除资源" :disabled="store.saving" @click="store.deleteTaskResource(store.editingTask!.id, resource.id)" variant="ghost" size="icon"><Trash2 :size="14" /></Button>
      </li>
    </ul>
    <p v-else class="empty-inline !py-4">还没有相关资源</p>
  </section>
</template>

<style scoped>
/* 审计 A23：独立提交成功的就地反馈 */
.saved-flash { font-size: 12px; font-weight: 500; color: var(--color-success); }
</style>
