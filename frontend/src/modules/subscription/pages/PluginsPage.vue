<script setup lang="ts">
import { ref } from 'vue'
import { Plus, Trash2, Upload } from '@lucide/vue'
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
const form = ref({ name: '', description: '', script: '' })

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
  form.value = { name: '', description: '', script: TEMPLATE.trim() + '\n' }
}

function openEdit(plugin: SubscriptionPlugin) {
  creating.value = false
  editing.value = plugin
  trialResult.value = ''
  form.value = {
    name: plugin.name,
    description: plugin.description,
    script: plugin.script,
  }
}

function closeForm() {
  creating.value = false
  editing.value = null
}

async function save() {
  const payload = { ...form.value }
  const ok = await store.savePlugin(payload, editing.value?.id)
  if (ok) closeForm()
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

async function trial() {
  if (!editing.value && !creating.value) return
  trialResult.value = ''
  const id = editing.value?.id
  if (!id) {
    trialResult.value = '请先保存插件后再试跑'
    return
  }
  try {
    const { subscriptionApi } = await import('../api')
    const result = await subscriptionApi.trialPlugin(id, { body: trialBody.value || '<rss></rss>' })
    trialResult.value = `解析出 ${result.count} 篇\n` + JSON.stringify(result.articles, null, 2)
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
        <p class="eyebrow">Plugins</p>
        <h1>解析插件</h1>
        <p>Python 脚本继承 SubscriptionParser，由平台拉取、子进程解析</p>
      </div>
      <Button @click="openCreate"><Plus :size="16" />新建插件</Button>
    </header>

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
      <Textarea
        v-model="form.script"
        :disabled="editing?.builtin"
        class="min-h-64 font-mono text-xs"
        spellcheck="false"
      />
      <p class="text-xs text-muted-foreground">
        编写规范见仓库 docs/subscription-plugin-spec.md。内置插件不可改脚本。
      </p>
      <div v-if="editing" class="space-y-2 rounded-lg border border-line p-3">
        <label class="block space-y-1 text-sm">
          <span class="text-muted-foreground">试跑样例 body</span>
          <Textarea v-model="trialBody" class="min-h-24 font-mono text-xs" placeholder="粘贴一段源响应文本" />
        </label>
        <Button size="sm" variant="outline" @click="trial">试跑</Button>
        <pre v-if="trialResult" class="max-h-48 overflow-auto rounded bg-panel-2 p-2 text-xs">{{ trialResult }}</pre>
      </div>
      <div class="flex gap-2">
        <Button :disabled="store.saving || editing?.builtin" @click="save">保存</Button>
        <Button variant="outline" @click="closeForm">取消</Button>
      </div>
    </div>

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
