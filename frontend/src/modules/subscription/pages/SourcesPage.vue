<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronDown, ChevronUp, Plus, RefreshCw, Trash2, X } from '@lucide/vue'
import AppSelect, { type AppSelectOption } from '../../../shared/AppSelect.vue'
import { cleanText } from '../../../shared/cleanText'
import { confirmDialog } from '../../../shared/confirm'
import { useDialogFocus } from '../../../shared/useDialogFocus'
import { useSubscriptionStore } from '../store'
import type { SubscriptionSource } from '../types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const BUILTIN_RSS_PLUGIN_ID = 'builtin-rss-atom'

const store = useSubscriptionStore()
const editing = ref<SubscriptionSource | null>(null)
const creating = ref(false)
const panel = ref<HTMLElement | null>(null)
useDialogFocus(panel, () => creating.value || Boolean(editing.value), closeForm)
const advancedOpen = ref(false)
const saveError = ref('')
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
  advancedOpen.value = false
  saveError.value = ''
  // 默认使用内置 RSS/Atom 解析，普通订阅只需填名称和地址
  form.value = {
    name: '',
    url: '',
    plugin_id: store.plugins.find(item => item.id === BUILTIN_RSS_PLUGIN_ID)?.id
      ?? store.plugins[0]?.id
      ?? '',
    interval_minutes: 60,
    enabled: true,
  }
}

function openEdit(source: SubscriptionSource) {
  creating.value = false
  editing.value = source
  advancedOpen.value = false
  saveError.value = ''
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
  saveError.value = ''
}

async function save() {
  saveError.value = ''
  const payload = { ...form.value }
  const ok = await store.saveSource(payload, editing.value?.id)
  if (ok) closeForm()
  else saveError.value = store.error
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

// —— 源健康状态（A40：由上次结果 + 频率推算下次拉取；区分失败与空结果）——
function nextFetchText(source: SubscriptionSource) {
  if (!source.enabled || !source.last_fetched_at) return ''
  try {
    const next = new Date(source.last_fetched_at).getTime() + source.interval_minutes * 60_000
    if (Number.isNaN(next)) return ''
    return new Date(next).toLocaleString()
  } catch {
    return ''
  }
}

function statusHint(source: SubscriptionSource) {
  if (!source.enabled) return '已停用，不会自动刷新'
  switch (source.last_status) {
    case 'running':
      return '正在拉取…'
    case 'error':
      return '上次拉取失败，可点击刷新重试'
    case 'ok': {
      const next = nextFetchText(source)
      return next ? `下次拉取约在 ${next}` : '上次拉取成功'
    }
    default:
      return source.last_fetched_at ? '等待下次调度' : '尚未拉取，点「刷新」立即获取'
  }
}

function refreshFeedback(source: SubscriptionSource) {
  const result = store.refreshResults[source.id]
  if (!result) return ''
  if (result.status === 'error') return '手动刷新失败'
  if (result.upserted > 0) return `手动刷新新增或更新 ${result.upserted} 篇`
  return '手动刷新完成，未发现新文章'
}
</script>

<template>
  <div>
    <header class="page-header">
      <div>
        <p class="eyebrow">Subscription</p>
        <h1>订阅源</h1>
        <p>{{ store.sources.length }} 个源 · 按设定频率自动更新文章</p>
      </div>
      <Button @click="openCreate"><Plus :size="16" />新建订阅源</Button>
    </header>

    <div v-if="!store.sources.length" class="empty-state">
      <h2>尚无订阅源</h2>
      <p>粘贴网站的 RSS/Atom 地址即可定时拉取文章，大多数博客和播客都支持。</p>
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
            <td class="whitespace-normal">
              <button type="button" class="text-left font-medium hover:underline" @click="openEdit(source)">
                {{ source.name }}
              </button>
              <div class="max-w-xs truncate text-xs text-muted-foreground">{{ source.url }}</div>
              <p
                v-if="source.last_error"
                class="mt-1 line-clamp-2 max-w-xs text-xs text-danger"
                :title="cleanText(source.last_error)"
              >
                失败原因：{{ cleanText(source.last_error) }}
              </p>
            </td>
            <td>{{ store.pluginMap.get(source.plugin_id)?.name ?? source.plugin_id }}</td>
            <td class="whitespace-normal">
              <Badge :variant="source.last_status === 'error' ? 'destructive' : 'secondary'">
                {{ statusLabel[source.last_status] ?? source.last_status }}
              </Badge>
              <p class="mt-1 max-w-52 text-xs text-muted-foreground">{{ statusHint(source) }}</p>
              <p v-if="refreshFeedback(source)" class="mt-0.5 max-w-52 text-xs text-text-secondary">
                {{ refreshFeedback(source) }}
              </p>
            </td>
            <td>{{ source.interval_minutes }} 分</td>
            <td>{{ formatTime(source.last_fetched_at) }}</td>
            <td>
              <div class="flex justify-end gap-1">
                <Button
                  size="sm"
                  variant="outline"
                  :disabled="store.refreshing === source.id"
                  :aria-label="store.refreshing === source.id ? '刷新中' : '刷新'"
                  @click="store.refreshSource(source.id)"
                >
                  <RefreshCw :size="15" :class="store.refreshing === source.id && 'animate-spin'" />
                  <span class="hidden sm:inline">刷新</span>
                </Button>
                <Button size="sm" variant="destructive" aria-label="删除" @click="remove(source)">
                  <Trash2 :size="15" />
                </Button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <Teleport to="body">
      <div v-if="creating || editing" class="fixed inset-0 z-50 bg-slate-900/30" @click.self="closeForm">
        <aside ref="panel" class="editor-panel" role="dialog" aria-modal="true" aria-label="编辑订阅源">
          <header class="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
            <div class="min-w-0">
              <p class="eyebrow">Subscription source</p>
              <h2 class="mt-1 truncate font-display text-xl text-text">
                {{ editing ? '编辑订阅源' : '新建订阅源' }}
              </h2>
            </div>
            <Button aria-label="关闭" variant="ghost" size="icon" @click="closeForm">
              <X :size="16" />
            </Button>
          </header>
          <form class="editor-form" @submit.prevent="save">
            <div class="editor-fields space-y-5">
              <p v-if="!editing" class="text-sm leading-6 text-muted-foreground">
                只需两步：粘贴订阅地址、起个名字。大多数博客、播客和新闻站都提供 RSS/Atom
                地址，保存后平台会定时拉取并解析成文章。
              </p>
              <section class="space-y-4">
                <label class="field-label">名称
                  <Input v-model="form.name" required maxlength="200" placeholder="例如：阮一峰的博客" />
                </label>
                <label class="field-label">订阅地址（RSS / Atom）
                  <Input
                    v-model="form.url"
                    required
                    maxlength="2000"
                    placeholder="https://example.com/feed.xml"
                  />
                  <small>
                    通常能在网站的「RSS」或「订阅」入口找到，以 http(s) 开头，
                    例如 https://example.com/rss.xml
                  </small>
                </label>
                <label class="flex items-center gap-3 text-xs text-text-secondary">
                  <input v-model="form.enabled" type="checkbox" class="accent-cyan" />启用定时刷新
                </label>
              </section>
              <section class="space-y-3 border-t border-line pt-4">
                <button
                  type="button"
                  class="flex w-full items-center justify-between gap-2 text-sm font-medium text-text"
                  :aria-expanded="advancedOpen"
                  @click="advancedOpen = !advancedOpen"
                >
                  高级设置
                  <span class="flex items-center gap-1 text-xs font-normal text-muted-foreground">
                    解析插件与刷新频率
                    <ChevronDown v-if="!advancedOpen" :size="16" />
                    <ChevronUp v-else :size="16" />
                  </span>
                </button>
                <p class="text-xs text-muted-foreground">
                  标准 RSS/Atom 地址使用内置解析即可，无需编写插件。
                </p>
                <div v-show="advancedOpen" class="space-y-4">
                  <label class="field-label">解析插件
                    <AppSelect v-model="form.plugin_id" :options="pluginOptions" placeholder="选择插件" />
                    <small>只有非标准页面才需要自定义插件，可在「插件」页编写。</small>
                  </label>
                  <label class="field-label">刷新间隔（分钟）
                    <Input v-model.number="form.interval_minutes" type="number" min="5" max="10080" />
                    <small>平台每隔该时间自动拉取一次，最短 5 分钟。</small>
                  </label>
                </div>
              </section>
              <p v-if="saveError" class="error-box" role="alert">{{ saveError }}</p>
            </div>
            <footer class="editor-actions">
              <Button type="button" variant="outline" @click="closeForm">取消</Button>
              <Button type="submit" :disabled="store.saving">
                {{ store.saving ? '保存中…' : '保存' }}
              </Button>
            </footer>
          </form>
        </aside>
      </div>
    </Teleport>
  </div>
</template>
