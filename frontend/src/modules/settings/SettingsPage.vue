<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { CheckCircle2, Eye, EyeOff, LoaderCircle, MonitorSmartphone, PlugZap, RefreshCw, Save, Trash2, Wrench } from '@lucide/vue'
import { api, apiError, getDeviceId, setDeviceCredentials } from '../../shared/api/client'

interface Settings { base_url: string; model: string; api_key_masked: string }
interface Secret { api_key: string }
interface AiToolParam { name: string; type: string; required: boolean; default: string | null; values: string[] }
interface AiTool { name: string; description: string; parameters: AiToolParam[] }
interface AiModuleTools { id: string; instructions: string; tools: AiTool[] }
interface DeviceBindingInfo { id: string; device_id: string; device_name: string; created_at: string; last_active_at: string }

const tab = ref<'connection' | 'tools' | 'devices'>('connection')
const baseUrl = ref('')
const model = ref('')
const apiKey = ref('')
const maskedKey = ref('')
const revealedKey = ref('')
const loading = ref(true)
const revealing = ref(false)
const saving = ref(false)
const testing = ref(false)
const error = ref('')
const saveResult = ref('')
const testResult = ref('')
const toolModules = ref<AiModuleTools[]>([])
const toolsLoading = ref(false)
const toolsError = ref('')
const devices = ref<DeviceBindingInfo[]>([])
const devicesLoading = ref(false)
const devicesError = ref('')
const unbindingId = ref('')

const moduleLabels: Record<string, string> = { progress: '进度模块', knowledge: '知识库' }

const providerPresets = [
  { label: 'DeepSeek', base_url: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  { label: 'Kimi', base_url: 'https://api.moonshot.cn/v1', model: 'kimi-k2-0905-preview' },
  { label: 'GLM', base_url: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4.6' },
  { label: 'Qwen', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-max' },
  { label: 'OpenRouter', base_url: 'https://openrouter.ai/api/v1', model: 'inflection/inflection-3-pi' },
  { label: 'OpenAI', base_url: 'https://api.openai.com/v1', model: 'gpt-4.1' },
]

function moduleLabel(id: string) {
  return moduleLabels[id] ?? id
}

function formatStamp(value: string | null) {
  return value ? value.slice(0, 16) : '—'
}

onMounted(load)
async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get<Settings | null>('/ai-settings')
    if (data) { baseUrl.value = data.base_url; model.value = data.model; maskedKey.value = data.api_key_masked }
  } catch (cause) { error.value = apiError(cause) }
  finally { loading.value = false }
}
async function save() {
  saving.value = true; error.value = ''; saveResult.value = ''
  try {
    const payload: { base_url: string; model: string; api_key?: string } = { base_url: baseUrl.value, model: model.value }
    if (apiKey.value) payload.api_key = apiKey.value
    const { data } = await api.put<Settings>('/ai-settings', payload)
    maskedKey.value = data.api_key_masked; apiKey.value = ''; revealedKey.value = ''; saveResult.value = '设置已安全保存'
  } catch (cause) { error.value = apiError(cause) }
  finally { saving.value = false }
}
async function revealSecret() {
  revealing.value = true; error.value = ''
  try {
    const { data } = await api.get<Secret>('/ai-settings/secret')
    revealedKey.value = data.api_key
  } catch (cause) { revealedKey.value = ''; error.value = apiError(cause) }
  finally { revealing.value = false }
}
async function test() {
  testing.value = true; error.value = ''; testResult.value = ''
  try {
    const payload: Record<string, string> = { base_url: baseUrl.value, model: model.value }
    if (apiKey.value) payload.api_key = apiKey.value
    await api.post('/ai-settings/test', payload, { timeout: 60_000 })
    testResult.value = '模型流式输出正常'
  } catch (cause) { error.value = apiError(cause); testResult.value = '连接失败' }
  finally { testing.value = false }
}
async function showTools() {
  tab.value = 'tools'
  if (!toolModules.value.length && !toolsLoading.value) await loadTools()
}
async function loadTools() {
  toolsLoading.value = true
  toolsError.value = ''
  try {
    const { data } = await api.get<{ modules: AiModuleTools[] }>('/ai-settings/tools')
    toolModules.value = data.modules
  } catch (cause) { toolsError.value = apiError(cause) }
  finally { toolsLoading.value = false }
}
async function showDevices() {
  tab.value = 'devices'
  if (!devices.value.length && !devicesLoading.value) await loadDevices()
}
async function loadDevices() {
  devicesLoading.value = true
  devicesError.value = ''
  try {
    const { data } = await api.get<DeviceBindingInfo[]>('/auth/devices')
    devices.value = data
  } catch (cause) { devicesError.value = apiError(cause) }
  finally { devicesLoading.value = false }
}
async function unbindDevice(binding: DeviceBindingInfo) {
  unbindingId.value = binding.id
  devicesError.value = ''
  try {
    await api.delete(`/auth/devices/${binding.id}`)
    if (binding.device_id === getDeviceId()) {
      // 解绑当前设备：清除本地凭证，会话令牌到期后需要重新登录
      setDeviceCredentials(null)
    }
    await loadDevices()
  } catch (cause) { devicesError.value = apiError(cause) }
  finally { unbindingId.value = '' }
}
</script>

<template>
  <div class="page-wrap max-w-5xl">
    <header class="page-header"><div><p class="eyebrow">System preferences</p><h1>系统设置</h1><p>由后端加密保存模型连接信息</p></div></header>
    <div class="grid gap-5 lg:grid-cols-[220px_1fr]">
      <nav class="card h-fit p-2" aria-label="设置分类">
        <button type="button" :class="['nav-link', 'w-full', { 'nav-link--active': tab === 'connection' }]" @click="tab = 'connection'"><PlugZap :size="17" />模型连接</button>
        <button type="button" :class="['nav-link', 'w-full', { 'nav-link--active': tab === 'tools' }]" @click="showTools"><Wrench :size="17" />AI 工具注册</button>
        <button type="button" :class="['nav-link', 'w-full', { 'nav-link--active': tab === 'devices' }]" @click="showDevices"><MonitorSmartphone :size="17" />绑定设备</button>
      </nav>
      <section v-if="tab === 'connection'" class="card">
        <div class="card-head"><div><p class="eyebrow">OpenAI compatible</p><h2>模型连接</h2><p class="mt-2 text-xs text-muted">浏览器仅调用工作台后端，不直接连接模型服务</p></div><span class="status-live"><span class="size-1.5 rounded-full bg-cyan" /> ENCRYPTED</span></div>
        <p v-if="loading" class="empty-inline">正在读取设置…</p>
        <form v-else class="mt-7 space-y-5" @submit.prevent="save">
          <div class="field-label">厂商预设
            <small>点击自动填充连接信息；OpenAI 走 Responses 协议，其余厂商走 Chat Completions 兼容协议，Pulse 的工具调用能力保持不变</small>
            <span class="mt-2 flex flex-wrap gap-1.5">
              <button v-for="preset in providerPresets" :key="preset.label" type="button" :class="['kind-option', { 'kind-option--active': baseUrl === preset.base_url }]" @click="baseUrl = preset.base_url; model = preset.model">{{ preset.label }}</button>
            </span>
          </div>
          <label class="field-label">Base URL<input v-model="baseUrl" class="input font-mono" type="url" required placeholder="https://api.example.com/v1" /><small>填写服务商的 API 基础地址，包含要求的路径（如 /v1 或 /api/paas/v4）；网站首页地址可能无法调用模型。</small></label>
          <label class="field-label">模型名称<input v-model="model" class="input font-mono" required /></label>
          <div v-if="maskedKey" class="field-label">
            已保存 API Key
            <div class="flex gap-2">
              <input class="input min-w-0 flex-1 font-mono" type="text" readonly :value="revealedKey || maskedKey" />
              <button v-if="revealedKey" type="button" class="btn-secondary" @click="revealedKey = ''"><EyeOff :size="15" />隐藏</button>
              <button v-else type="button" class="btn-secondary" :disabled="revealing" @click="revealSecret"><LoaderCircle v-if="revealing" :size="15" class="animate-spin" /><Eye v-else :size="15" />{{ revealing ? '查看中…' : '查看' }}</button>
            </div>
          </div>
          <label class="field-label">API Key<input v-model="apiKey" class="input font-mono" type="password" autocomplete="new-password" placeholder="sk-..." :required="!maskedKey" /><small>{{ maskedKey ? '输入新密钥可替换，留空则保留现有密钥。' : '密钥提交至后端加密保存，不写入浏览器存储。' }}</small></label>
          <p v-if="error" class="error-box" role="alert">{{ error }}</p>
          <p v-if="saveResult" class="success-box"><CheckCircle2 :size="14" />{{ saveResult }}</p>
          <p v-if="testResult" :class="testResult === '模型流式输出正常' ? 'success-box' : 'error-box'">{{ testResult }}</p>
          <footer class="flex flex-wrap justify-end gap-2 border-t border-line pt-5">
            <button type="button" class="btn-secondary" :disabled="testing || saving" @click="test"><LoaderCircle v-if="testing" :size="15" class="animate-spin" /><PlugZap v-else :size="15" />{{ testing ? '验证模型输出中…' : '测试模型连接' }}</button>
            <button class="btn-primary" :disabled="saving || testing"><LoaderCircle v-if="saving" :size="15" class="animate-spin" /><Save v-else :size="15" />{{ saving ? '保存中…' : '保存设置' }}</button>
          </footer>
        </form>
      </section>
      <section v-else-if="tab === 'tools'">
        <div class="mb-4 flex items-center justify-between gap-3">
          <p class="text-xs text-muted">各模块向 Pulse 注册的 AI 工具与参数能力，只读。</p>
          <button type="button" class="btn-secondary shrink-0" :disabled="toolsLoading" @click="loadTools"><LoaderCircle v-if="toolsLoading" :size="15" class="animate-spin" /><RefreshCw v-else :size="15" />刷新</button>
        </div>
        <p v-if="toolsError" class="error-box" role="alert">{{ toolsError }}</p>
        <p v-else-if="toolsLoading && !toolModules.length" class="empty-inline">正在读取工具注册表…</p>
        <p v-else-if="!toolModules.length" class="empty-inline">暂无已注册的 AI 工具</p>
        <div v-else class="space-y-5">
          <article v-for="module in toolModules" :key="module.id" class="card">
            <div class="card-head"><div><p class="eyebrow">{{ module.id }}</p><h2>{{ moduleLabel(module.id) }} · {{ module.tools.length }} 个工具</h2></div><Wrench :size="17" class="text-cyan" /></div>
            <details class="mt-3">
              <summary class="cursor-pointer select-none text-[11px] text-muted">模块指令（注入给模型的提示）</summary>
              <p class="mt-2 whitespace-pre-wrap text-[11px] leading-5 text-muted">{{ module.instructions }}</p>
            </details>
            <div class="mt-4 space-y-3">
              <div v-for="tool in module.tools" :key="tool.name" class="rounded-lg border border-line bg-panel-2 p-3">
                <header class="flex items-center justify-between gap-2"><b class="font-mono text-xs text-cyan">{{ tool.name }}</b><span class="font-mono text-[9px] text-muted">{{ tool.parameters.length ? `${tool.parameters.length} 参数` : '无参数' }}</span></header>
                <p class="mt-1.5 text-[11px] leading-5 text-slate-300">{{ tool.description || '—' }}</p>
                <ul v-if="tool.parameters.length" class="mt-2 space-y-1">
                  <li v-for="param in tool.parameters" :key="param.name" class="flex flex-wrap items-center gap-2 font-mono text-[10px]">
                    <span class="text-white">{{ param.name }}</span>
                    <span class="text-muted">{{ param.type }}</span>
                    <span :class="param.required ? 'text-[#fca5a5]' : 'text-muted'">{{ param.required ? '必填' : '可选' }}</span>
                    <span v-if="param.values.length" class="text-[#fcd34d]">{{ param.values.join(' / ') }}</span>
                    <span v-if="param.default" class="text-muted">默认 {{ param.default }}</span>
                  </li>
                </ul>
              </div>
            </div>
          </article>
        </div>
      </section>
      <section v-else-if="tab === 'devices'">
        <div class="mb-4 flex items-center justify-between gap-3">
          <p class="text-xs text-muted">勾选「保持登录」的设备可静默续登；在这里解绑后该设备需重新输入密码。</p>
          <button type="button" class="btn-secondary shrink-0" :disabled="devicesLoading" @click="loadDevices"><LoaderCircle v-if="devicesLoading" :size="15" class="animate-spin" /><RefreshCw v-else :size="15" />刷新</button>
        </div>
        <p v-if="devicesError" class="error-box" role="alert">{{ devicesError }}</p>
        <p v-else-if="devicesLoading && !devices.length" class="empty-inline">正在读取绑定设备…</p>
        <p v-else-if="!devices.length" class="empty-inline">还没有绑定的设备；在登录页勾选「保持登录」即可绑定。</p>
        <div v-else class="space-y-3">
          <article v-for="device in devices" :key="device.id" class="card flex flex-wrap items-center justify-between gap-3 p-4">
            <div class="min-w-0">
              <b class="flex items-center gap-2 text-sm text-white">
                {{ device.device_name }}
                <span v-if="device.device_id === getDeviceId()" class="status-chip">当前设备</span>
              </b>
              <p class="mt-1 font-mono text-[10px] text-muted">绑定 {{ formatStamp(device.created_at) }} · 最近活跃 {{ formatStamp(device.last_active_at) }}</p>
            </div>
            <button type="button" class="btn-secondary shrink-0" :disabled="unbindingId === device.id" @click="unbindDevice(device)"><LoaderCircle v-if="unbindingId === device.id" :size="14" class="animate-spin" /><Trash2 v-else :size="14" />解绑</button>
          </article>
        </div>
      </section>
    </div>
  </div>
</template>
