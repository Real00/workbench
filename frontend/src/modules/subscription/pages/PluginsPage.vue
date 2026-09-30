<script setup lang="ts">
import { computed, ref } from 'vue'
import { Plus, Trash2, Upload } from '@lucide/vue'
import { RouterLink } from 'vue-router'
import { confirmDialog } from '../../../shared/confirm'
import { useSubscriptionStore } from '../store'
import type { SubscriptionPlugin } from '../types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'

const store = useSubscriptionStore()
const editing = ref<SubscriptionPlugin | null>(null)
const creating = ref(false)
const trialBody = ref('')
const trialResult = ref('')
const saveError = ref('')
const form = ref({ name: '', description: '', script: '' })

const scriptGutter = ref<HTMLElement | null>(null)
const lineCount = computed(() => Math.max(1, form.value.script.split('\n').length))
const saveErrorLine = ref<number | null>(null)

const TEMPLATE = `from subscription.plugin_runtime.base import ParsePayload, ParsedArticle, SubscriptionParser

class MyParser(SubscriptionParser):
    def parse(self, payload: ParsePayload) -> list[ParsedArticle]:
        return [
            ParsedArticle(
                external_id="demo-1",
                title="示例标题",
                content=payload.body[:500],
                content_format="markdown",
            )
        ]
`

function openCreate() {
  creating.value = true
  editing.value = null
  trialResult.value = ''
  saveError.value = ''
  form.value = { name: '', description: '', script: TEMPLATE.trim() + '\n' }
}

function openEdit(plugin: SubscriptionPlugin) {
  creating.value = false
  editing.value = plugin
  trialResult.value = ''
  saveError.value = ''
  form.value = {
    name: plugin.name,
    description: plugin.description,
    script: plugin.script,
  }
}

function closeForm() {
  creating.value = false
  editing.value = null
  saveError.value = ''
}

async function save() {
  saveError.value = ''
  saveErrorLine.value = null
  const payload = { ...form.value }
  const ok = await store.savePlugin(payload, editing.value?.id)
  if (ok) closeForm()
  else {
    // 后端语法错误形如「插件脚本语法错误: xxx (line 3)」，换算为中文行号提示
    const match = /line (\d+)/.exec(store.error)
    saveErrorLine.value = match ? Number(match[1]) : null
    saveError.value = store.error.replace(/line (\d+)/, '第 $1 行')
  }
}

async function remove(plugin: SubscriptionPlugin) {
  if (plugin.builtin) return
  const ok = await confirmDialog({
    title: `删除插件「${plugin.name}」？`,
    message: '删除前请确认没有订阅源仍在使用它。',
    confirmText: '删除',
  })
  if (!ok) return
  await store.removePlugin(plugin.id)
}

async function onUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  form.value.script = await file.text()
  input.value = ''
}

function onScriptScroll(event: Event) {
  if (scriptGutter.value) {
    scriptGutter.value.scrollTop = (event.target as HTMLTextAreaElement).scrollTop
  }
}

async function trial() {
  if (!editing.value && !creating.value) return
  trialResult.value = ''
  const id = editing.value?.id
  if (!id) {
    trialResult.value = '请先保存插件后再试跑：试跑运行的是已保存版本的脚本。'
    return
  }
  try {
    const { subscriptionApi } = await import('../api')
    const result = await subscriptionApi.trialPlugin(id, { body: trialBody.value || '<rss></rss>' })
    trialResult.value = `解析出 ${result.count} 篇（试跑仅解析样例，不会保存文章）\n`
      + JSON.stringify(result.articles, null, 2)
  } catch (cause) {
    const { apiError } = await import('../../../shared/api/client')
    trialResult.value = apiError(cause)
  }
}
</script>

<template>
  <div>
    <header class="page-header">
      <div>
        <p class="eyebrow">Plugins · 高级</p>
        <h1>解析插件</h1>
        <p>标准 RSS/Atom 订阅用内置解析即可，通常无需编写插件</p>
      </div>
      <Button @click="openCreate"><Plus :size="16" />新建插件</Button>
    </header>

    <div v-if="!creating && !editing" class="card mb-4 space-y-2 p-4 text-sm">
      <p class="font-medium">什么时候需要插件？</p>
      <p class="leading-6 text-muted-foreground">
        订阅博客、播客等提供 RSS/Atom
        地址的站点时，直接在「订阅源」里粘贴链接即可，平台会用内置的「RSS / Atom」解析器，
        不需要写任何代码。只有当网站没有标准订阅地址、需要自定义解析逻辑时，才需要这里的插件。
      </p>
      <div>
        <Button as-child variant="outline" size="sm">
          <RouterLink to="/subscription">前往添加订阅源</RouterLink>
        </Button>
      </div>
    </div>

    <div v-if="creating || editing" class="card mb-4 space-y-3 p-4">
      <h2 class="text-base font-semibold">{{ editing ? `编辑：${editing.name}` : '新建插件' }}</h2>
      <label class="block space-y-1 text-sm">
        <span class="text-muted-foreground">名称</span>
        <Input v-model="form.name" :disabled="editing?.builtin" maxlength="200" />
      </label>
      <label class="block space-y-1 text-sm">
        <span class="text-muted-foreground">说明</span>
        <Input v-model="form.description" maxlength="2000" />
      </label>
      <div class="flex items-center gap-2">
        <label class="text-sm text-muted-foreground">脚本</label>
        <label class="inline-flex cursor-pointer items-center gap-1 rounded-md border border-line px-2 py-1 text-sm hover:bg-panel-2">
          <Upload :size="14" />上传 .py
          <input
            type="file"
            accept=".py,text/x-python,text/plain"
            class="hidden"
            :disabled="editing?.builtin"
            @change="onUpload"
          />
        </label>
      </div>
      <div class="flex overflow-hidden rounded-md border border-line">
        <div
          ref="scriptGutter"
          aria-hidden="true"
          class="select-none overflow-hidden bg-panel-2 py-2 pl-3 pr-1 text-right font-mono text-xs leading-5 text-muted-foreground"
        >
          <div v-for="n in lineCount" :key="n">{{ n }}</div>
        </div>
        <Textarea
          v-model="form.script"
          :disabled="editing?.builtin"
          class="min-h-64 flex-1 rounded-none border-0 font-mono text-xs leading-5 shadow-none focus-visible:ring-0"
          spellcheck="false"
          @scroll="onScriptScroll"
        />
      </div>
      <p v-if="saveError" class="error-box" role="alert">
        {{ saveError }}
        <span v-if="saveErrorLine !== null">（请检查脚本第 {{ saveErrorLine }} 行附近）</span>
      </p>
      <p class="text-xs text-muted-foreground">
        编写规范见下方「插件编写规范」，或仓库 docs/subscription-plugin-spec.md。内置插件不可改脚本。
      </p>
      <div class="space-y-2 rounded-lg border border-line p-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <label class="text-sm font-medium">试跑</label>
          <span class="text-xs text-muted-foreground">试跑仅解析样例文本，不会保存任何文章</span>
        </div>
        <label class="block space-y-1 text-sm">
          <span class="text-muted-foreground">样例响应正文</span>
          <Textarea v-model="trialBody" class="min-h-24 font-mono text-xs" placeholder="粘贴一段源响应文本（如 RSS XML）" />
        </label>
        <p v-if="!editing" class="text-xs text-muted-foreground">
          新插件需先保存才能试跑：试跑运行的是已保存版本的脚本。
        </p>
        <div class="flex gap-2">
          <Button v-if="editing" size="sm" variant="outline" @click="trial">试跑</Button>
          <Button v-else size="sm" variant="outline" :disabled="store.saving" @click="save">
            {{ store.saving ? '保存中…' : '先保存' }}
          </Button>
        </div>
        <pre v-if="trialResult" class="max-h-48 overflow-auto rounded bg-panel-2 p-2 text-xs">{{ trialResult }}</pre>
      </div>
      <div class="flex gap-2">
        <Button :disabled="store.saving || editing?.builtin" @click="save">保存</Button>
        <Button variant="outline" @click="closeForm">取消</Button>
      </div>
    </div>

    <details class="card mb-4 p-4 text-sm">
      <summary class="cursor-pointer select-none font-medium">插件编写规范（开发者）</summary>
      <div class="mt-3 space-y-3 leading-6 text-muted-foreground">
        <p>平台负责 HTTP 拉取，插件只解析响应正文：平台把 <code>{ url, body, config }</code> 通过 stdin
          传给子进程脚本，脚本把 <code>{"{"} articles: [...] {"}"}</code> 写到 stdout，平台按
          （源, external_id）幂等入库。插件内不要发 HTTP、读写文件或访问网络。</p>
        <div class="overflow-x-auto">
          <table class="w-full min-w-125 text-left text-xs">
            <thead>
              <tr class="border-b border-line text-muted-foreground">
                <th class="py-1 pr-4 font-medium">ParsedArticle 字段</th>
                <th class="py-1 pr-4 font-medium">必填</th>
                <th class="py-1 font-medium">说明</th>
              </tr>
            </thead>
            <tbody>
              <tr><td class="py-1 pr-4 font-mono">external_id</td><td class="py-1 pr-4">是</td><td class="py-1">源内稳定 ID（guid / 链接 / 哈希）</td></tr>
              <tr><td class="py-1 pr-4 font-mono">title</td><td class="py-1 pr-4">是</td><td class="py-1">标题；空则显示「(无标题)」</td></tr>
              <tr><td class="py-1 pr-4 font-mono">content</td><td class="py-1 pr-4">否</td><td class="py-1">正文</td></tr>
              <tr><td class="py-1 pr-4 font-mono">content_format</td><td class="py-1 pr-4">否</td><td class="py-1">html（默认）或 markdown</td></tr>
              <tr><td class="py-1 pr-4 font-mono">published_at</td><td class="py-1 pr-4">否</td><td class="py-1">ISO8601 / RFC2822 时间字符串</td></tr>
              <tr><td class="py-1 pr-4 font-mono">author</td><td class="py-1 pr-4">否</td><td class="py-1">作者</td></tr>
              <tr><td class="py-1 pr-4 font-mono">cover_url</td><td class="py-1 pr-4">否</td><td class="py-1">封面图 http(s) 地址</td></tr>
              <tr><td class="py-1 pr-4 font-mono">url</td><td class="py-1 pr-4">否</td><td class="py-1">原文链接 http(s) 地址</td></tr>
            </tbody>
          </table>
        </div>
        <p>脚本中只能有一个继承 <code>SubscriptionParser</code> 的类；可用标准库，不保证第三方包。失败时以非
          0 退出并把错误写到 stderr，平台会记入订阅源状态。完整说明与示例见仓库
          docs/subscription-plugin-spec.md。</p>
      </div>
    </details>

    <div class="knowledge-table">
      <table class="data-table">
        <thead>
          <tr><th>名称</th><th>说明</th><th /></tr>
        </thead>
        <tbody>
          <tr v-for="plugin in store.plugins" :key="plugin.id">
            <td>
              <button type="button" class="font-medium hover:underline" @click="openEdit(plugin)">
                {{ plugin.name }}
              </button>
              <span v-if="plugin.builtin" class="ml-2 text-xs text-muted-foreground">内置</span>
            </td>
            <td class="max-w-md truncate text-muted-foreground">{{ plugin.description || '—' }}</td>
            <td>
              <Button
                v-if="!plugin.builtin"
                size="sm"
                variant="ghost"
                @click="remove(plugin)"
              >
                <Trash2 :size="14" />
              </Button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
