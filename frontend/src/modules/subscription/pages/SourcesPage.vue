<script setup lang="ts">
import { computed, ref } from 'vue'
import { Plus, RefreshCw, Trash2 } from '@lucide/vue'
import AppSelect, { type AppSelectOption } from '../../../shared/AppSelect.vue'
import { confirmDialog } from '../../../shared/confirm'
import { useSubscriptionStore } from '../store'
import type { SubscriptionSource } from '../types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const store = useSubscriptionStore()
const editing = ref<SubscriptionSource | null>(null)
const creating = ref(false)
const form = ref({
  name: '',
  url: '',
  plugin_id: '',
  interval_minutes: 60,
  enabled: true,
})

const pluginOptions = computed<AppSelectOption[]>(() =>
  store.plugins.map(item => ({ value: item.id, label: item.name })),
)

const statusLabel: Record<string, string> = {
  idle: '未刷新',
  ok: '正常',
  error: '失败',
  running: '刷新中',
}

function openCreate() {
  creating.value = true
  editing.value = null
  form.value = {
    name: '',
    url: '',
    plugin_id: store.plugins[0]?.id ?? '',
    interval_minutes: 60,
    enabled: true,
  }
}

function openEdit(source: SubscriptionSource) {
  creating.value = false
  editing.value = source
  form.value = {
    name: source.name,
    url: source.url,
    plugin_id: source.plugin_id,
    interval_minutes: source.interval_minutes,
    enabled: source.enabled,
  }
}

function closeForm() {
  creating.value = false
  editing.value = null
}

async function save() {
  const payload = { ...form.value }
  const ok = await store.saveSource(payload, editing.value?.id)
  if (ok) closeForm()
}

async function remove(source: SubscriptionSource) {
  const ok = await confirmDialog({
    title: `删除订阅源「${source.name}」？`,
    message: '该源下已拉取的文章会一并删除。',
    confirmText: '删除',
  })
  if (!ok) return
  await store.removeSource(source.id)
}

function formatTime(value: string | null) {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}
</script>

<template>
  <div class="page-wrap">
    <header class="page-header">
      <div>
        <p class="eyebrow">Subscription</p>
        <h1>订阅源</h1>
        <p>{{ store.sources.length }} 个源 · 定时拉取后由插件解析为文章</p>
      </div>
      <Button @click="openCreate"><Plus :size="16" />新建订阅源</Button>
    </header>

    <div v-if="creating || editing" class="card mb-4 space-y-3 p-4">
      <h2 class="text-base font-semibold">{{ editing ? '编辑订阅源' : '新建订阅源' }}</h2>
      <label class="block space-y-1 text-sm">
        <span class="text-muted-foreground">名称</span>
        <Input v-model="form.name" maxlength="200" />
      </label>
      <label class="block space-y-1 text-sm">
        <span class="text-muted-foreground">URL</span>
        <Input v-model="form.url" maxlength="2000" placeholder="https://" />
      </label>
      <label class="block space-y-1 text-sm">
        <span class="text-muted-foreground">解析插件</span>
        <AppSelect v-model="form.plugin_id" :options="pluginOptions" placeholder="选择插件" />
      </label>
      <label class="block space-y-1 text-sm">
        <span class="text-muted-foreground">刷新间隔（分钟）</span>
        <Input v-model.number="form.interval_minutes" type="number" min="5" max="10080" />
      </label>
      <label class="flex items-center gap-2 text-sm">
        <input v-model="form.enabled" type="checkbox" class="size-4" />
        启用定时刷新
      </label>
      <div class="flex gap-2">
        <Button :disabled="store.saving" @click="save">保存</Button>
        <Button variant="outline" @click="closeForm">取消</Button>
      </div>
    </div>

    <div v-if="!store.sources.length" class="empty-state">
      <h2>尚无订阅源</h2>
      <p>添加远程 URL，选择解析插件，即可定时拉取文章。</p>
      <Button @click="openCreate">新建订阅源</Button>
    </div>
    <div v-else class="knowledge-table">
      <table class="data-table">
        <thead>
          <tr>
            <th>名称</th>
            <th>插件</th>
            <th>状态</th>
            <th>间隔</th>
            <th>上次刷新</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="source in store.sources" :key="source.id">
            <td>
              <button type="button" class="text-left font-medium hover:underline" @click="openEdit(source)">
                {{ source.name }}
              </button>
              <div class="max-w-xs truncate text-xs text-muted-foreground">{{ source.url }}</div>
              <p v-if="source.last_error" class="mt-1 text-xs text-danger">{{ source.last_error }}</p>
            </td>
            <td>{{ store.pluginMap.get(source.plugin_id)?.name ?? source.plugin_id }}</td>
            <td>
              <Badge :variant="source.last_status === 'error' ? 'destructive' : 'secondary'">
                {{ statusLabel[source.last_status] ?? source.last_status }}
              </Badge>
              <span v-if="!source.enabled" class="ml-1 text-xs text-muted-foreground">已停用</span>
            </td>
            <td>{{ source.interval_minutes }} 分</td>
            <td>{{ formatTime(source.last_fetched_at) }}</td>
            <td>
              <div class="flex justify-end gap-1">
                <Button
                  size="sm"
                  variant="outline"
                  :disabled="store.refreshing === source.id"
                  @click="store.refreshSource(source.id)"
                >
                  <RefreshCw :size="14" :class="store.refreshing === source.id && 'animate-spin'" />
                  刷新
                </Button>
                <Button size="sm" variant="ghost" @click="remove(source)">
                  <Trash2 :size="14" />
                </Button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
