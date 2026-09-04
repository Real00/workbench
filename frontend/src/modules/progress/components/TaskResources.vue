<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { FileText, Link2, Paperclip, Trash2, Upload } from '@lucide/vue'
import { progressApi } from '../api'
import { useProgressStore } from '../store'
import { formatBytes, resourceAccept, resourceKindMap, type TaskResource } from '../types'

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
  await store.uploadTaskResource(store.editingTask.id, file)
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
    <p class="eyebrow">相关资源</p>
    <p class="mt-1 text-[11px] text-muted">图片、文档或外链。单文件不超过 20MB。</p>
    <div class="mt-3 flex flex-wrap gap-2">
      <input ref="fileInput" class="sr-only" type="file" :accept="resourceAccept" @change="onFile" />
      <button type="button" class="btn-secondary" :disabled="store.saving" @click="fileInput?.click()"><Upload :size="14" />上传文件</button>
    </div>
    <div class="mt-3 grid gap-2">
      <label class="field-label">外链名称<input v-model="linkName" class="input" maxlength="200" placeholder="可选" /></label>
      <label class="field-label">链接地址<input v-model="linkUrl" class="input" maxlength="2000" placeholder="https://" /></label>
    </div>
    <button type="button" class="btn-secondary mt-3" :disabled="store.saving || !linkUrl.trim()" @click="addLink"><Link2 :size="14" />添加链接</button>
    <ul v-if="resources.length" class="mt-4 grid gap-2">
      <li v-for="resource in resources" :key="resource.id" class="resource-item">
        <button type="button" class="resource-main" @click="openResource(resource)">
          <img v-if="previews[resource.id]" :src="previews[resource.id]" :alt="resource.name" class="resource-thumb" />
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
        <button type="button" class="icon-btn" aria-label="删除资源" :disabled="store.saving" @click="store.deleteTaskResource(store.editingTask!.id, resource.id)"><Trash2 :size="14" /></button>
      </li>
    </ul>
    <p v-else class="empty-inline !py-4">还没有相关资源</p>
  </section>
</template>
