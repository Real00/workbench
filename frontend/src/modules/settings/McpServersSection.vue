<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  CheckCircle2,
  CircleAlert,
  FlaskConical,
  LoaderCircle,
  Network,
  Plus,
  Save,
  Trash2,
} from '@lucide/vue'
import { api, apiError } from '../../shared/api/client'
import { confirmDialog } from '../../shared/confirm'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

/** 服务器公开形态（后端 _public：密钥打码，headers 展开为对象） */
interface McpServerPublic {
  name: string
  url: string
  enabled: boolean
  headers: Record<string, string>
  api_key_masked: string
}

interface HeaderEntry { key: string; value: string }

/** 编辑行：密钥输入留空 = 保留已保存密钥 */
interface McpServerRow {
  name: string
  url: string
  enabled: boolean
  headers: HeaderEntry[]
  apiKey: string
  apiKeyMasked: string
}

const MAX_SERVERS = 8
const NAME_PATTERN = /^[a-z][a-z0-9_-]{0,31}$/

const rows = ref<McpServerRow[]>([])
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const savedAt = ref('')
const testingIndex = ref(-1)
const testResult = ref<{ index: number; ok: boolean; text: string } | null>(null)
const showHeaders = ref(-1)

const canAdd = computed(() => rows.value.length < MAX_SERVERS)

onMounted(load)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get<{ mcp_servers?: McpServerPublic[] }>('/ai-settings')
    rows.value = (data.mcp_servers ?? []).map(server => ({
      name: server.name,
      url: server.url,
      enabled: server.enabled,
      headers: Object.entries(server.headers ?? {}).map(([key, value]) => ({ key, value })),
      apiKey: '',
      apiKeyMasked: server.api_key_masked || '',
    }))
  } catch (cause) { error.value = apiError(cause) }
  finally { loading.value = false }
}

function addRow() {
  if (!canAdd.value) return
  rows.value.push({ name: '', url: '', enabled: true, headers: [], apiKey: '', apiKeyMasked: '' })
  showHeaders.value = rows.value.length - 1
}

function removeRow(index: number) {
  rows.value.splice(index, 1)
  if (showHeaders.value === index) showHeaders.value = -1
  else if (showHeaders.value > index) showHeaders.value -= 1
  testResult.value = null
}

function addHeader(index: number) {
  const row = rows.value[index]
  if (row.headers.length >= 8) return
  row.headers.push({ key: '', value: '' })
}

function payload() {
  return {
    mcp_servers: rows.value.map(row => {
      const headers = Object.fromEntries(
        row.headers.filter(entry => entry.key.trim()).map(entry => [entry.key.trim(), entry.value]),
      )
      const server: Record<string, unknown> = {
        name: row.name.trim(),
        url: row.url.trim(),
        enabled: row.enabled,
        headers,
      }
      if (row.apiKey) server.api_key = row.apiKey
      return server
    }),
  }
}

function rowIssues(): string | null {
  const seen = new Set<string>()
  for (const row of rows.value) {
    const name = row.name.trim()
    if (!NAME_PATTERN.test(name)) return '服务器名称需以小写字母开头，仅含小写字母 / 数字 / - / _（不超过 32 字符）'
    if (seen.has(name)) return `服务器名称重复：${name}`
    seen.add(name)
    const url = row.url.trim()
    if (!/^https?:\/\/.+/.test(url)) return `「${name}」的地址必须是 http(s) Streamable HTTP 端点`
  }
  return null
}

async function save() {
  const issue = rowIssues()
  if (issue) { error.value = issue; return }
  saving.value = true
  error.value = ''
  testResult.value = null
  try {
    // 增量保存：只提交 mcp_servers 字段；同名且未填新密钥时后端保留旧密钥
    const { data } = await api.put<{ mcp_servers?: McpServerPublic[] }>('/ai-settings', payload())
    if (data.mcp_servers) {
      rows.value = data.mcp_servers.map(server => ({
        name: server.name,
        url: server.url,
        enabled: server.enabled,
        headers: Object.entries(server.headers ?? {}).map(([key, value]) => ({ key, value })),
        apiKey: '',
        apiKeyMasked: server.api_key_masked || '',
      }))
    }
    savedAt.value = new Date().toLocaleTimeString()
  } catch (cause) { error.value = apiError(cause) }
  finally { saving.value = false }
}

async function test(index: number) {
  const row = rows.value[index]
  const issue = rowIssues()
  const url = row.url.trim()
  if (!/^https?:\/\/.+/.test(url)) {
    testResult.value = { index, ok: false, text: '先填写合法的 http(s) 地址' }
    return
  }
  if (issue && !issue.includes(row.name.trim())) {
    testResult.value = { index, ok: false, text: issue }
    return
  }
  testingIndex.value = index
  testResult.value = null
  try {
    const body: Record<string, unknown> = { url }
    if (row.apiKey) body.api_key = row.apiKey
    const headers = Object.fromEntries(
      row.headers.filter(entry => entry.key.trim()).map(entry => [entry.key.trim(), entry.value]),
    )
    if (Object.keys(headers).length) body.headers = headers
    const { data } = await api.post<{ tools: string[] }>('/ai-settings/mcp/test', body, { timeout: 30_000 })
    testResult.value = {
      index,
      ok: true,
      text: `连接正常，发现 ${data.tools.length} 个工具${data.tools.length ? `：${data.tools.slice(0, 5).join('、')}${data.tools.length > 5 ? ' 等' : ''}` : ''}`,
    }
  } catch (cause) {
    testResult.value = { index, ok: false, text: apiError(cause) }
  } finally {
    testingIndex.value = -1
  }
}

async function clearAll() {
  if (!rows.value.length) return
  const ok = await confirmDialog({
    title: '清空全部 MCP 服务器？',
    message: '将删除所有出站 MCP 配置（含已保存的密钥），保存后生效。',
    confirmText: '清空',
    danger: true,
  })
  if (!ok) return
  rows.value = []
  showHeaders.value = -1
  testResult.value = null
}
</script>

<template>
  <section class="card p-5">
    <div class="card-head">
      <div>
        <p class="eyebrow">Outbound MCP</p>
        <h2>出站 MCP 服务器</h2>
        <p class="mt-2 text-xs text-muted-foreground">把远程 MCP 服务器的工具接入 Pulse 对话；工具名会加「名称__」前缀。仅支持远程 Streamable HTTP 端点，连接失败的服务器当轮自动跳过。</p>
      </div>
      <div class="flex items-center gap-2">
        <Badge variant="outline">最多 {{ MAX_SERVERS }} 台</Badge>
        <Network :size="17" class="text-cyan" />
      </div>
    </div>

    <p v-if="loading" class="empty-inline mt-5">正在读取 MCP 配置…</p>
    <template v-else>
      <div v-if="!rows.length" class="empty-state mt-5 gap-2 p-8">
        <Network :size="22" class="text-muted-foreground" />
        <p class="text-sm font-medium text-text">还没有配置出站 MCP 服务器</p>
        <p class="max-w-md text-[12px] leading-5">添加远程 Streamable HTTP 端点后，它的工具会出现在 Pulse 对话中（带服务器名前缀），结果作为证据供模型参考。</p>
      </div>

      <div v-else class="mt-5 space-y-3">
        <article v-for="(row, index) in rows" :key="index" class="rounded-lg border border-line bg-panel-2 p-3">
          <div class="grid gap-3 sm:grid-cols-[minmax(0,180px)_1fr]">
            <label class="field-label">名称
              <Input v-model="row.name" placeholder="github" autocomplete="off" class="font-mono" :aria-label="`服务器 ${index + 1} 名称`" />
            </label>
            <label class="field-label">Streamable HTTP 地址
              <Input v-model="row.url" type="url" placeholder="https://mcp.example.com/mcp" autocomplete="off" class="font-mono" :aria-label="`服务器 ${index + 1} 地址`" />
            </label>
          </div>
          <div class="mt-3 grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
            <label class="field-label">API Key（可选）
              <Input v-model="row.apiKey" type="password" autocomplete="new-password" :placeholder="row.apiKeyMasked || '未配置；填写即设置 Bearer 鉴权'" class="font-mono" />
              <small>{{ row.apiKeyMasked ? `已保存 ${row.apiKeyMasked}；留空保留，填写替换。` : '将以 Bearer 令牌发送；也可在下方 Headers 里自定义 Authorization。' }}</small>
            </label>
            <Button type="button" variant="outline" :aria-expanded="showHeaders === index" @click="showHeaders = showHeaders === index ? -1 : index">
              自定义 Headers（{{ row.headers.length }}）
            </Button>
          </div>
          <div v-if="showHeaders === index" class="mt-3 space-y-2 rounded-lg border border-line p-3">
            <p class="text-[12px] leading-5 text-muted-foreground">附加请求头（最多 8 个）；不能覆盖 Content-Type / Content-Length。</p>
            <div v-for="(entry, headerIndex) in row.headers" :key="headerIndex" class="flex gap-2">
              <Input v-model="entry.key" placeholder="Header" autocomplete="off" class="font-mono" :aria-label="`服务器 ${index + 1} Header ${headerIndex + 1} 名`" />
              <Input v-model="entry.value" placeholder="值" autocomplete="off" class="font-mono" :aria-label="`服务器 ${index + 1} Header ${headerIndex + 1} 值`" />
              <Button type="button" variant="ghost" size="icon" aria-label="删除此 Header" @click="row.headers.splice(headerIndex, 1)"><Trash2 :size="15" /></Button>
            </div>
            <Button v-if="row.headers.length < 8" type="button" variant="outline" @click="addHeader(index)"><Plus :size="15" />添加 Header</Button>
          </div>
          <footer class="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
            <Button type="button" variant="ghost" :class="['kind-option', { 'kind-option--active': row.enabled }]" :aria-pressed="row.enabled" @click="row.enabled = !row.enabled">
              {{ row.enabled ? '已启用' : '已停用' }}
            </Button>
            <span class="flex-1" />
            <Button type="button" variant="outline" :disabled="testingIndex === index" @click="test(index)">
              <LoaderCircle v-if="testingIndex === index" :size="15" class="animate-spin" /><FlaskConical v-else :size="15" />
              {{ testingIndex === index ? '测试中…' : '测试连接' }}
            </Button>
            <Button type="button" variant="ghost" size="icon" :aria-label="`删除服务器 ${row.name || index + 1}`" @click="removeRow(index)"><Trash2 :size="15" /></Button>
          </footer>
          <p v-if="testResult && testResult.index === index" :class="testResult.ok ? 'success-box mt-3' : 'error-box mt-3'" :role="testResult.ok ? 'status' : 'alert'">
            <CheckCircle2 v-if="testResult.ok" :size="14" />
            <CircleAlert v-else :size="14" />
            {{ testResult.text }}
          </p>
        </article>
      </div>

      <p v-if="error" class="error-box mt-4" role="alert">{{ error }}</p>
      <p v-else-if="savedAt" class="success-box mt-4"><CheckCircle2 :size="14" />MCP 配置已保存（{{ savedAt }}）</p>

      <footer class="mt-4 flex flex-wrap justify-between gap-2 border-t border-line pt-5">
        <div class="flex flex-wrap gap-2">
          <Button v-if="canAdd" type="button" variant="outline" @click="addRow"><Plus :size="15" />添加服务器</Button>
          <Button v-if="rows.length" type="button" variant="ghost" @click="clearAll">清空全部</Button>
        </div>
        <Button :disabled="saving" @click="save"><LoaderCircle v-if="saving" :size="15" class="animate-spin" /><Save v-else :size="15" />{{ saving ? '保存中…' : '保存 MCP 配置' }}</Button>
      </footer>
    </template>
  </section>
</template>
