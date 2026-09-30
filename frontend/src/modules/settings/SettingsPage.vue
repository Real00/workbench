<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { CheckCircle2, CircleAlert, Copy, Check, Eye, EyeOff, LoaderCircle, MonitorSmartphone, PlugZap, RefreshCw, Save, Trash2, Wrench, Cable, Package, XCircle } from '@lucide/vue'
import JevSettingsFields, { type JevSettings } from './JevSettingsFields.vue'
import { api, apiError, getApiBase, getDeviceId, getDeviceToken, isDesktopShell, setDeviceCredentials } from '../../shared/api/client'
import { confirmDialog } from '../../shared/confirm'
import { downloadAndOpenDesktopDmg, getDesktopAppVersion } from '../../shared/tauri'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface Settings { base_url: string; model: string; api_key_masked: string; jev?: JevSettings }
interface Secret { api_key: string }
interface AiToolParam { name: string; type: string; required: boolean; default: string | null; values: string[] }
interface AiTool { name: string; description: string; parameters: AiToolParam[] }
interface AiModuleTools { id: string; instructions: string; tools: AiTool[] }
interface DeviceBindingInfo { id: string; device_id: string; device_name: string; created_at: string; last_active_at: string }
interface SystemVersion {
  git_sha: string
  git_sha_short: string
  built_at: string
  update_enabled: boolean
  github_repo: string
  release_tag: string
}
interface UpdateCheck {
  current_sha: string
  current_sha_short: string
  latest_sha: string
  latest_sha_short: string
  update_available: boolean
  github_repo: string
  release_tag: string
}
type UpdateState = 'idle' | 'queued' | 'downloading' | 'preparing' | 'restarting' | 'verifying' | 'succeeded' | 'failed'
interface UpdateStatus {
  id: string
  state: UpdateState
  message: string
  finished_at: string | null
  phase?: string
}
type UpdateStepId = 'submit' | 'queued' | 'downloading' | 'preparing' | 'restarting' | 'verify'
interface UpdateStep {
  id: UpdateStepId
  label: string
}
interface DesktopUpdateInfo {
  current_version: string
  latest_version: string
  update_available: boolean
  download_path: string
  asset_name: string
  tag: string
  published_at: string
  target_commitish: string
  github_repo: string
}

const tab = ref<'connection' | 'tools' | 'devices' | 'mcp' | 'updates'>('connection')
const desktopShell = isDesktopShell
const desktopVersion = ref('')
const desktopUpdate = ref<DesktopUpdateInfo | null>(null)
const desktopChecking = ref(false)
const desktopDownloading = ref(false)
const desktopError = ref('')
const desktopMessage = ref('')
const baseUrl = ref('')
const model = ref('')
const apiKey = ref('')
const maskedKey = ref('')
const revealedKey = ref('')
const jevApiKey = ref('')
const jev = ref<JevSettings>({ enabled: false, base_url: 'https://api.typesafe.ai/v1', model: 'jev-latest', threshold: 0.8, timeout_seconds: 3, api_key_masked: '' })
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
const versionInfo = ref<SystemVersion | null>(null)
const versionLoading = ref(false)
const versionError = ref('')
const updateCheck = ref<UpdateCheck | null>(null)
const checkingUpdate = ref(false)
const applyingUpdate = ref(false)
const updateStatus = ref<UpdateStatus | null>(null)
const updateMessage = ref('')
const updateRequestId = ref('')
const updateStartedAt = ref<number | null>(null)
const updateElapsedSec = ref(0)
const updatePhase = ref<UpdateStepId | 'done' | 'failed' | null>(null)
let updatePollTimer: number | undefined
let updateElapsedTimer: number | undefined

const UPDATE_STEPS: UpdateStep[] = [
  { id: 'submit', label: '提交更新请求' },
  { id: 'queued', label: '等待开始' },
  { id: 'downloading', label: '下载版本包' },
  { id: 'preparing', label: '校验并准备依赖' },
  { id: 'restarting', label: '重启服务' },
  { id: 'verify', label: '确认新版本' },
]

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
onUnmounted(() => {
  stopUpdateTimers()
})

function stopUpdateTimers() {
  if (updatePollTimer !== undefined) {
    window.clearInterval(updatePollTimer)
    updatePollTimer = undefined
  }
  if (updateElapsedTimer !== undefined) {
    window.clearInterval(updateElapsedTimer)
    updateElapsedTimer = undefined
  }
}

function formatElapsed(seconds: number) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m} 分 ${s} 秒` : `${s} 秒`
}

function failedStepFromStatus(status: UpdateStatus | null): UpdateStepId {
  if (!status) return 'submit'
  const phase = status.phase || status.state || 'queued'
  if (phase === 'downloading' || phase === 'preparing') return phase
  if (phase === 'restarting') return 'restarting'
  if (phase === 'verify' || phase === 'verifying' || phase === 'succeeded') return 'verify'
  if (phase === 'submit') return 'submit'
  return 'queued'
}

function stepTone(stepId: UpdateStepId): 'done' | 'active' | 'pending' | 'failed' {
  const phase = updatePhase.value
  if (!phase) return 'pending'
  const order = UPDATE_STEPS.map(step => step.id)
  const index = order.indexOf(stepId)
  if (phase === 'done') return 'done'
  if (phase === 'failed') {
    const failedIndex = order.indexOf(failedStepFromStatus(updateStatus.value))
    if (index < failedIndex) return 'done'
    if (index === failedIndex) return 'failed'
    return 'pending'
  }
  const currentIndex = order.indexOf(phase)
  if (index < currentIndex) return 'done'
  if (index === currentIndex) return 'active'
  return 'pending'
}

const updateProgressVisible = computed(
  () => applyingUpdate.value || updatePhase.value === 'done' || updatePhase.value === 'failed',
)

const updateStuckQueued = computed(
  () => applyingUpdate.value && updatePhase.value === 'queued' && updateElapsedSec.value >= 20,
)
async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get<Settings | null>('/ai-settings')
    if (data) { baseUrl.value = data.base_url; model.value = data.model; maskedKey.value = data.api_key_masked; if (data.jev) jev.value = data.jev }
  } catch (cause) { error.value = apiError(cause) }
  finally { loading.value = false }
}
async function save() {
  saving.value = true; error.value = ''; saveResult.value = ''
  try {
    const { api_key_masked: _masked, ...jevOptions } = jev.value
    const payload = { base_url: baseUrl.value, model: model.value, api_key: apiKey.value || undefined, jev: { ...jevOptions, api_key: jevApiKey.value || undefined } }
    if (apiKey.value) payload.api_key = apiKey.value
    const { data } = await api.put<Settings>('/ai-settings', payload)
    if (data.jev) jev.value = data.jev
    jevApiKey.value = ''
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

async function showUpdates() {
  tab.value = 'updates'
  if (!versionInfo.value && !versionLoading.value) await loadVersion()
  if (desktopShell && !desktopVersion.value) await loadDesktopVersion()
}
async function loadDesktopVersion() {
  if (!desktopShell) return
  try {
    desktopVersion.value = await getDesktopAppVersion()
  } catch (cause) {
    desktopError.value = cause instanceof Error ? cause.message : '无法读取桌面端版本'
  }
}
async function checkDesktopUpdate() {
  if (!desktopShell) return
  desktopChecking.value = true
  desktopError.value = ''
  desktopMessage.value = ''
  try {
    if (!desktopVersion.value) await loadDesktopVersion()
    // 服务端需请求 GitHub；默认 15s 在弱网/墙内易被 WKWebView 收成 Network Error
    const { data } = await api.get<DesktopUpdateInfo>('/system/desktop/update', {
      params: { current: desktopVersion.value || 'unknown' },
      timeout: 60_000,
    })
    desktopUpdate.value = data
    desktopMessage.value = data.update_available
      ? `发现新客户端 ${data.latest_version}（当前 ${data.current_version}）`
      : `客户端已是最新（${data.latest_version}）`
  } catch (cause) {
    desktopError.value = apiError(cause)
  } finally {
    desktopChecking.value = false
  }
}
async function downloadDesktopUpdate() {
  if (!desktopShell) return
  desktopError.value = ''
  desktopMessage.value = ''
  // 下载走 Rust→API 代理，不依赖检查接口；检查失败仍可直接拉 DMG
  if (!desktopUpdate.value) {
    try {
      if (!desktopVersion.value) await loadDesktopVersion()
      const { data } = await api.get<DesktopUpdateInfo>('/system/desktop/update', {
        params: { current: desktopVersion.value || 'unknown' },
        timeout: 60_000,
      })
      desktopUpdate.value = data
    } catch {
      /* 仍用默认 download_path */
    }
  }
  const ok = await confirmDialog({
    title: '下载最新桌面端？',
    message: '将下载 DMG 并用系统打开；请把 Workbench.app 拖进「应用程序」后重新启动。服务器镜像不会因此更新。',
    confirmText: '下载并打开',
    danger: false,
  })
  if (!ok) return
  desktopDownloading.value = true
  desktopMessage.value = '正在下载 DMG，请稍候…'
  try {
    const path = await downloadAndOpenDesktopDmg(
      desktopUpdate.value?.download_path || '/system/desktop/dmg',
    )
    desktopMessage.value = `已打开安装包：${path}。拖进「应用程序」后请退出并重新打开工作台。`
  } catch (cause) {
    desktopError.value = apiError(cause)
    desktopMessage.value = ''
  } finally {
    desktopDownloading.value = false
  }
}
async function loadVersion() {
  versionLoading.value = true
  versionError.value = ''
  try {
    const { data } = await api.get<SystemVersion>('/system/version')
    versionInfo.value = data
    if (!applyingUpdate.value) {
      const status = (await api.get<UpdateStatus>('/system/updates/status')).data
      if (status.id && !['idle', 'succeeded', 'failed'].includes(status.state)) {
        updateRequestId.value = status.id
        updateStatus.value = status
        applyingUpdate.value = true
        updateStartedAt.value = Date.now()
        startUpdatePolling()
      } else if (status.state === 'failed') {
        updateStatus.value = status
        updatePhase.value = 'failed'
        versionError.value = status.message
      }
    }
  } catch (cause) { versionError.value = apiError(cause) }
  finally { versionLoading.value = false }
}
async function checkForUpdate() {
  checkingUpdate.value = true
  versionError.value = ''
  updateMessage.value = ''
  try {
    const { data } = await api.post<UpdateCheck>('/system/updates/check', undefined, {
      timeout: 60_000,
    })
    updateCheck.value = data
    updateMessage.value = data.update_available
      ? `发现新版本 ${data.latest_sha_short}（当前 ${data.current_sha_short}）`
      : `已是最新（${data.latest_sha_short}）`
  } catch (cause) { versionError.value = apiError(cause) }
  finally { checkingUpdate.value = false }
}
async function applyUpdate() {
  versionError.value = ''
  updateMessage.value = ''
  if (!versionInfo.value?.update_enabled) {
    versionError.value =
      '当前环境不支持在线更新，请使用支持自更新的 Docker 镜像部署'
    return
  }
  const ok = await confirmDialog({
    title: '更新到最新版本？',
    message: '将下载新版并准备依赖，然后重启服务。重启期间会短暂不可用；新版启动失败将自动回退。',
    confirmText: '开始更新',
    danger: false,
  })
  if (!ok) return
  applyingUpdate.value = true
  updatePhase.value = 'submit'
  updateStatus.value = null
  updateRequestId.value = ''
  updateStartedAt.value = Date.now()
  updateElapsedSec.value = 0
  updateMessage.value = '正在提交更新请求…'
  stopUpdateTimers()
  updateElapsedTimer = window.setInterval(() => {
    if (updateStartedAt.value) {
      updateElapsedSec.value = Math.floor((Date.now() - updateStartedAt.value) / 1000)
    }
  }, 1000)
  try {
    const { data } = await api.post<{ accepted: boolean; request_id: string; message: string }>('/system/updates/apply')
    updateRequestId.value = data.request_id
    updatePhase.value = 'queued'
    updateStatus.value = {
      id: data.request_id,
      state: 'queued',
      message: data.message,
      finished_at: null,
      phase: 'queued',
    }
    updateMessage.value = data.message || '更新请求已提交，等待开始'
    startUpdatePolling()
  } catch (cause) {
    versionError.value = apiError(cause)
    updatePhase.value = 'failed'
    applyingUpdate.value = false
    stopUpdateTimers()
  }
}
async function pollUpdateOnce() {
  try {
    const statusRes = await api.get<UpdateStatus>('/system/updates/status')
    // 忽略上一轮残留状态，只认当前 request
    if (updateRequestId.value && statusRes.data.id && statusRes.data.id !== updateRequestId.value) {
      updateMessage.value = '等待当前更新开始…'
      return 'continue' as const
    }
    updateStatus.value = statusRes.data
    if (statusRes.data.state === 'failed') {
      versionError.value = statusRes.data.message || '更新失败'
      updateMessage.value = ''
      updatePhase.value = 'failed'
      applyingUpdate.value = false
      stopUpdateTimers()
      return 'stop' as const
    }
    if (statusRes.data.state === 'queued') {
      updatePhase.value = 'queued'
      updateMessage.value = statusRes.data.message || '等待更新开始'
    } else if (statusRes.data.state === 'downloading' || statusRes.data.state === 'preparing') {
      updatePhase.value = statusRes.data.state
      updateMessage.value = statusRes.data.message || '正在下载并准备新版…'
    } else if (statusRes.data.state === 'restarting') {
      updatePhase.value = 'restarting'
      updateMessage.value = statusRes.data.message || '正在重启服务…'
    } else if (statusRes.data.state === 'succeeded' || statusRes.data.state === 'verifying') {
      updatePhase.value = 'verify'
      updateMessage.value = statusRes.data.message || '服务已重启，正在确认新版本…'
    }

    const versionRes = await api.get<SystemVersion>('/system/version')
    versionInfo.value = versionRes.data
    if (statusRes.data.state === 'succeeded' && versionRes.data.git_sha !== 'unknown') {
      updateMessage.value = desktopShell
        ? `服务器已更新至 ${versionRes.data.git_sha_short}，客户端界面请单独更新`
        : `更新完成：${versionRes.data.git_sha_short}，正在刷新页面…`
      updateCheck.value = null
      updatePhase.value = 'done'
      if (!desktopShell) window.setTimeout(() => window.location.reload(), 1500)
      applyingUpdate.value = false
      stopUpdateTimers()
      return 'stop' as const
    }
    if (statusRes.data.state === 'succeeded') {
      updateMessage.value = '服务已重启，正在确认新版本…'
    }
  } catch {
    // 重启期间 API 短暂不可用是预期行为
    if (updatePhase.value === 'restarting' || updatePhase.value === 'verify' || updatePhase.value === 'downloading' || updatePhase.value === 'preparing') {
      updatePhase.value = 'verify'
      updateMessage.value = '服务重启中，正在等待恢复…'
    } else {
      updateMessage.value = '暂时无法连接服务，将继续重试…'
    }
  }
  return 'continue' as const
}
function startUpdatePolling() {
  stopUpdateTimers()
  updateElapsedTimer = window.setInterval(() => {
    if (updateStartedAt.value) {
      updateElapsedSec.value = Math.floor((Date.now() - updateStartedAt.value) / 1000)
    }
  }, 1000)
  let attempts = 0
  let inFlight = false
  const tick = async () => {
    if (inFlight) return
    inFlight = true
    try {
      attempts += 1
      const result = await pollUpdateOnce()
      if (result === 'stop') return
      if (attempts >= 600) {
        versionError.value = '等待超时：后台更新可能仍在继续，请稍后刷新查看结果，或检查容器日志'
        updatePhase.value = 'failed'
        applyingUpdate.value = false
        stopUpdateTimers()
      }
    } finally {
      inFlight = false
    }
  }
  void tick()
  updatePollTimer = window.setInterval(() => { void tick() }, 2000)
}

const mcpUrl = `${getApiBase() || window.location.origin}/mcp`
const curlLoginBase = (getApiBase() || window.location.origin).replace(/\/+$/, '')
// 登录/补绑定后凭证才出现，必须响应式读取而非模块期常量
const deviceCredentialsReady = computed(() => Boolean(getDeviceToken() && getDeviceId()))
const copied = ref('')

function copyConfig(kind: 'url' | 'device' | 'jwt') {
  const text = kind === 'url'
    ? mcpUrl
    : JSON.stringify(
        kind === 'device'
          ? {
              mcpServers: {
                workbench: {
                  type: 'http',
                  url: mcpUrl,
                  headers: { 'X-Device-Id': getDeviceId() ?? '', 'X-Device-Token': getDeviceToken() ?? '' },
                },
              },
            }
          : {
              mcpServers: {
                workbench: {
                  type: 'http',
                  url: mcpUrl,
                  headers: { Authorization: 'Bearer <登录后的 access_token，1 天有效>' },
                },
              },
            },
        null,
        2,
      )
  copied.value = kind
  void navigator.clipboard?.writeText(text).catch(() => { /* 剪贴板不可用时忽略 */ })
  window.setTimeout(() => { copied.value = '' }, 1600)
}
</script>

<template>
  <div class="page-wrap max-w-5xl">
    <header class="page-header"><div><p class="eyebrow">System preferences</p><h1>系统设置</h1><p>由后端加密保存模型连接信息</p></div></header>
    <div class="grid gap-5 lg:grid-cols-[220px_1fr]">
      <nav class="card flex gap-1 overflow-x-auto p-2 lg:h-fit lg:flex-col" aria-label="设置分类">
        <Button type="button" variant="ghost" :class="['nav-link', 'shrink-0', 'lg:w-full', { 'nav-link--active': tab === 'connection' }]" @click="tab = 'connection'"><PlugZap :size="17" /><span>模型连接</span></Button>
        <Button type="button" variant="ghost" :class="['nav-link', 'shrink-0', 'lg:w-full', { 'nav-link--active': tab === 'tools' }]" @click="showTools"><Wrench :size="17" /><span>AI 工具</span></Button>
        <Button type="button" variant="ghost" :class="['nav-link', 'shrink-0', 'lg:w-full', { 'nav-link--active': tab === 'devices' }]" @click="showDevices"><MonitorSmartphone :size="17" /><span>设备</span></Button>
        <Button type="button" variant="ghost" :class="['nav-link', 'shrink-0', 'lg:w-full', { 'nav-link--active': tab === 'mcp' }]" @click="tab = 'mcp'"><Cable :size="17" /><span>MCP</span></Button>
        <Button type="button" variant="ghost" :class="['nav-link', 'shrink-0', 'lg:w-full', { 'nav-link--active': tab === 'updates' }]" @click="showUpdates"><Package :size="17" /><span>更新</span></Button>
      </nav>
      <section v-if="tab === 'connection'" class="card">
        <div class="card-head"><div><p class="eyebrow">OpenAI compatible</p><h2>模型连接</h2><p class="mt-2 text-xs text-muted-foreground">浏览器仅调用工作台后端，不直接连接模型服务</p></div><Badge variant="outline"><span class="size-1.5 rounded-full bg-cyan" /> ENCRYPTED</Badge></div>
        <p v-if="loading" class="empty-inline">正在读取设置…</p>
        <form v-else class="mt-7 space-y-5" @submit.prevent="save">
          <div class="field-label">厂商预设
            <small>点击自动填充连接信息；OpenAI 走 Responses 协议，其余厂商走 Chat Completions 兼容协议，Pulse 的工具调用能力保持不变</small>
            <span class="mt-2 flex flex-wrap gap-1.5">
              <Button v-for="preset in providerPresets" :key="preset.label" type="button" variant="ghost" :class="['kind-option', { 'kind-option--active': baseUrl === preset.base_url }]" @click="baseUrl = preset.base_url; model = preset.model">{{ preset.label }}</Button>
            </span>
          </div>
          <label class="field-label">Base URL<Input v-model="baseUrl" type="url" required autocomplete="url" placeholder="https://api.example.com/v1" class="font-mono" /><small>填写服务商的 API 基础地址，包含要求的路径（如 /v1 或 /api/paas/v4）；网站首页地址可能无法调用模型。</small></label>
          <label class="field-label">模型名称<Input v-model="model" required autocomplete="off" class="font-mono" /></label>
          <div v-if="maskedKey" class="field-label">
            已保存 API Key
            <div class="flex gap-2">
              <Input type="text" readonly :model-value="revealedKey || maskedKey" class="min-w-0 flex-1 font-mono" />
              <Button v-if="revealedKey" type="button" class="shrink-0" @click="revealedKey = ''" variant="outline"><EyeOff :size="15" /><span class="hidden sm:inline">隐藏</span></Button>
              <Button v-else type="button" class="shrink-0" :disabled="revealing" @click="revealSecret" variant="outline"><LoaderCircle v-if="revealing" :size="15" class="animate-spin" /><Eye v-else :size="15" /><span class="hidden sm:inline">{{ revealing ? '查看中…' : '查看' }}</span></Button>
            </div>
          </div>
          <label class="field-label">API Key<Input v-model="apiKey" type="password" autocomplete="new-password" placeholder="sk-..." :required="!maskedKey" class="font-mono" /><small>{{ maskedKey ? '输入新密钥可替换，留空则保留现有密钥。' : '密钥提交至后端加密保存，不写入浏览器存储。' }}</small></label>
          <JevSettingsFields v-model="jev" v-model:api-key="jevApiKey" :disabled="saving || testing" />
          <p v-if="error" class="error-box" role="alert">{{ error }}</p>
          <p v-if="saveResult" class="success-box"><CheckCircle2 :size="14" />{{ saveResult }}</p>
          <p v-if="testResult" :class="testResult === '模型流式输出正常' ? 'success-box' : 'error-box'">{{ testResult }}</p>
          <footer class="flex flex-wrap justify-end gap-2 border-t border-line pt-5">
            <Button type="button" :disabled="testing || saving" @click="test" variant="outline"><LoaderCircle v-if="testing" :size="15" class="animate-spin" /><PlugZap v-else :size="15" />{{ testing ? '验证模型输出中…' : '测试模型连接' }}</Button>
            <Button :disabled="saving || testing"><LoaderCircle v-if="saving" :size="15" class="animate-spin" /><Save v-else :size="15" />{{ saving ? '保存中…' : '保存设置' }}</Button>
          </footer>
        </form>
      </section>
      <section v-else-if="tab === 'tools'">
        <div class="mb-4 flex items-center justify-between gap-3">
          <p class="text-xs text-muted-foreground">各模块向 Pulse 注册的 AI 工具与参数能力，只读。</p>
          <Button type="button" :disabled="toolsLoading" @click="loadTools" class="shrink-0" variant="outline"><LoaderCircle v-if="toolsLoading" :size="15" class="animate-spin" /><RefreshCw v-else :size="15" />刷新</Button>
        </div>
        <p v-if="toolsError" class="error-box" role="alert">{{ toolsError }}</p>
        <p v-else-if="toolsLoading && !toolModules.length" class="empty-inline">正在读取工具注册表…</p>
        <p v-else-if="!toolModules.length" class="empty-inline">暂无已注册的 AI 工具</p>
        <div v-else class="space-y-5">
          <article v-for="module in toolModules" :key="module.id" class="card">
            <div class="card-head"><div><p class="eyebrow">{{ module.id }}</p><h2>{{ moduleLabel(module.id) }} · {{ module.tools.length }} 个工具</h2></div><Wrench :size="17" class="text-cyan" /></div>
            <details class="mt-3">
              <summary class="cursor-pointer select-none text-[12px] text-muted-foreground">模块指令（注入给模型的提示）</summary>
              <p class="mt-2 whitespace-pre-wrap text-[12px] leading-5 text-muted-foreground">{{ module.instructions }}</p>
            </details>
            <div class="mt-4 space-y-3">
              <div v-for="tool in module.tools" :key="tool.name" class="rounded-lg border border-line bg-panel-2 p-3">
                <header class="flex items-center justify-between gap-2"><b class="font-mono text-xs text-cyan">{{ tool.name }}</b><span class="font-mono text-[12px] text-muted-foreground">{{ tool.parameters.length ? `${tool.parameters.length} 参数` : '无参数' }}</span></header>
                <p class="mt-1.5 text-[12px] leading-5 text-text-secondary">{{ tool.description || '—' }}</p>
                <ul v-if="tool.parameters.length" class="mt-2 space-y-1">
                  <li v-for="param in tool.parameters" :key="param.name" class="flex flex-wrap items-center gap-2 font-mono text-[12px]">
                    <span class="text-text">{{ param.name }}</span>
                    <span class="text-muted-foreground">{{ param.type }}</span>
                    <span :class="param.required ? 'text-danger' : 'text-muted-foreground'">{{ param.required ? '必填' : '可选' }}</span>
                    <span v-if="param.values.length" class="text-warning">{{ param.values.join(' / ') }}</span>
                    <span v-if="param.default" class="text-muted-foreground">默认 {{ param.default }}</span>
                  </li>
                </ul>
              </div>
            </div>
          </article>
        </div>
      </section>
      <section v-else-if="tab === 'devices'">
        <div class="mb-4 flex items-center justify-between gap-3">
          <p class="text-xs text-muted-foreground">勾选「保持登录」的设备可静默续登；在这里解绑后该设备需重新输入密码。</p>
          <Button type="button" :disabled="devicesLoading" @click="loadDevices" class="shrink-0" variant="outline"><LoaderCircle v-if="devicesLoading" :size="15" class="animate-spin" /><RefreshCw v-else :size="15" />刷新</Button>
        </div>
        <p v-if="devicesError" class="error-box" role="alert">{{ devicesError }}</p>
        <p v-else-if="devicesLoading && !devices.length" class="empty-inline">正在读取绑定设备…</p>
        <p v-else-if="!devices.length" class="empty-inline">还没有绑定的设备；在登录页勾选「保持登录」即可绑定。</p>
        <div v-else class="space-y-3">
          <article v-for="device in devices" :key="device.id" class="card flex flex-wrap items-center justify-between gap-3 p-4">
            <div class="min-w-0">
              <b class="flex items-center gap-2 text-sm text-text">
                {{ device.device_name }}
                <Badge v-if="device.device_id === getDeviceId()" variant="secondary">当前设备</Badge>
              </b>
              <p class="mt-1 font-mono text-[12px] text-muted-foreground">绑定 {{ formatStamp(device.created_at) }} · 最近活跃 {{ formatStamp(device.last_active_at) }}</p>
            </div>
            <Button type="button" :disabled="unbindingId === device.id" @click="unbindDevice(device)" class="shrink-0" variant="outline"><LoaderCircle v-if="unbindingId === device.id" :size="14" class="animate-spin" /><Trash2 v-else :size="14" />解绑</Button>
          </article>
        </div>
      </section>
      <section v-else-if="tab === 'updates'" class="space-y-5">
        <div v-if="desktopShell" class="card p-5">
          <div class="card-head">
            <div>
              <p class="eyebrow">Desktop client</p>
              <h2>客户端更新</h2>
              <p class="mt-2 text-xs text-muted-foreground">桌面端内嵌前端。服务器镜像更新不会刷新本机 UI；需要下载新的 DMG 并替换 Applications 中的应用。</p>
            </div>
            <MonitorSmartphone :size="17" class="text-cyan" />
          </div>
          <div class="mt-5 space-y-4">
            <div class="grid gap-3 sm:grid-cols-2">
              <div class="rounded-lg border border-line bg-panel-2 p-3">
                <p class="text-[12px] text-muted-foreground">当前客户端</p>
                <p class="mt-1 font-mono text-sm text-text">{{ desktopVersion || '—' }}</p>
              </div>
              <div class="rounded-lg border border-line bg-panel-2 p-3">
                <p class="text-[12px] text-muted-foreground">远端客户端</p>
                <p class="mt-1 font-mono text-sm text-text">{{ desktopUpdate?.latest_version || '—' }}</p>
                <p class="mt-1 font-mono text-[12px] text-muted-foreground">{{ desktopUpdate?.tag || 'desktop-latest' }} · {{ desktopUpdate?.asset_name || 'Workbench-macos-aarch64.dmg' }}</p>
              </div>
            </div>
            <p v-if="desktopUpdate" class="rounded-lg border border-line bg-panel-2 p-3 font-mono text-[12px] text-muted-foreground">
              {{ desktopUpdate.github_repo }} @ {{ desktopUpdate.tag }}
              · {{ desktopUpdate.update_available ? '有可用客户端更新' : '已是最新客户端' }}
              <template v-if="desktopUpdate.published_at"> · {{ formatStamp(desktopUpdate.published_at) }}</template>
            </p>
            <p v-if="desktopError" class="error-box whitespace-pre-wrap break-words" role="alert">{{ desktopError }}</p>
            <p v-else-if="desktopMessage" class="success-box"><CheckCircle2 :size="14" />{{ desktopMessage }}</p>
            <footer class="flex flex-wrap justify-end gap-2 border-t border-line pt-5">
              <Button type="button" :disabled="desktopChecking || desktopDownloading" @click="checkDesktopUpdate" variant="outline">
                <LoaderCircle v-if="desktopChecking" :size="15" class="animate-spin" /><RefreshCw v-else :size="15" />
                {{ desktopChecking ? '检查中…' : '检查客户端更新' }}
              </Button>
              <Button type="button" :disabled="desktopChecking || desktopDownloading" @click="downloadDesktopUpdate">
                <LoaderCircle v-if="desktopDownloading" :size="15" class="animate-spin" /><Package v-else :size="15" />
                {{ desktopDownloading ? '下载中…' : '下载并打开 DMG' }}
              </Button>
            </footer>
          </div>
        </div>
        <div class="card p-5">
          <div class="card-head">
            <div>
              <p class="eyebrow">Release channel</p>
              <h2>服务器更新</h2>
              <p class="mt-2 text-xs text-muted-foreground">在线下载新版、准备依赖并重启，启动失败自动回退。服务器更新后，桌面客户端仍需单独更新。</p>
            </div>
            <Package :size="17" class="text-cyan" />
          </div>
          <p v-if="versionLoading && !versionInfo" class="empty-inline mt-5">正在读取版本信息…</p>
          <div v-else class="mt-5 space-y-4">
            <div class="grid gap-3 sm:grid-cols-2">
              <div class="rounded-lg border border-line bg-panel-2 p-3">
                <p class="text-[12px] text-muted-foreground">当前版本</p>
                <p class="mt-1 font-mono text-sm text-text">{{ versionInfo?.git_sha_short || '—' }}</p>
                <p class="mt-1 text-[12px] text-muted-foreground">构建 {{ versionInfo?.built_at ? formatStamp(versionInfo.built_at) : '—' }}</p>
              </div>
              <div class="rounded-lg border border-line bg-panel-2 p-3">
                <p class="text-[12px] text-muted-foreground">更新通道</p>
                <p class="mt-1 text-sm text-text">
                  <Badge :variant="versionInfo?.update_enabled ? 'secondary' : 'outline'">
                    {{ versionInfo?.update_enabled ? '在线更新可用' : '在线更新不可用' }}
                  </Badge>
                </p>
                <p class="mt-1 font-mono text-[12px] text-muted-foreground">{{ versionInfo?.github_repo || '—' }}@{{ versionInfo?.release_tag || '—' }}</p>
              </div>
            </div>
            <p v-if="!versionInfo?.update_enabled" class="error-box" role="status">
              当前环境不支持在线更新。服务器首次需部署支持自更新的镜像，之后即可在此更新。
            </p>
            <p v-if="updateCheck" class="rounded-lg border border-line bg-panel-2 p-3 font-mono text-[12px] text-muted-foreground">
              远端 {{ updateCheck.github_repo }}@{{ updateCheck.release_tag }} → {{ updateCheck.latest_sha_short }}
              · {{ updateCheck.update_available ? '有可用更新' : '已是最新' }}
            </p>
            <div v-if="updateProgressVisible" class="rounded-lg border border-line bg-panel-2 p-4" role="status" aria-live="polite">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <p class="text-sm font-medium text-text">
                  <template v-if="updatePhase === 'done'">更新完成</template>
                  <template v-else-if="updatePhase === 'failed'">更新失败</template>
                  <template v-else>正在更新</template>
                </p>
                <p class="font-mono text-[12px] text-muted-foreground">已用时 {{ formatElapsed(updateElapsedSec) }}</p>
              </div>
              <ol class="mt-3 space-y-2">
                <li
                  v-for="step in UPDATE_STEPS"
                  :key="step.id"
                  class="flex items-center gap-2 text-[13px]"
                  :class="{
                    'text-muted-foreground': stepTone(step.id) === 'pending',
                    'text-text': stepTone(step.id) === 'active' || stepTone(step.id) === 'done',
                    'text-danger': stepTone(step.id) === 'failed',
                  }"
                >
                  <LoaderCircle v-if="stepTone(step.id) === 'active'" :size="14" class="shrink-0 animate-spin text-cyan" />
                  <CheckCircle2 v-else-if="stepTone(step.id) === 'done'" :size="14" class="shrink-0 text-success" />
                  <XCircle v-else-if="stepTone(step.id) === 'failed'" :size="14" class="shrink-0 text-danger" />
                  <span v-else class="inline-block size-3.5 shrink-0 rounded-full border border-line" />
                  <span>{{ step.label }}</span>
                </li>
              </ol>
              <p v-if="updateMessage && updatePhase !== 'failed'" class="mt-3 text-[12px] leading-5 text-muted-foreground">{{ updateMessage }}</p>
              <p v-if="updateStuckQueued" class="mt-3 flex items-start gap-2 text-[12px] leading-5 text-warning">
                <CircleAlert :size="14" class="mt-0.5 shrink-0" />
                等待时间较长，请检查服务器容器日志；刷新页面可恢复更新进度。
              </p>
            </div>
            <p v-if="versionError" class="error-box whitespace-pre-wrap break-words" role="alert">{{ versionError }}</p>
            <p v-else-if="updatePhase === 'done' && updateMessage" class="success-box"><CheckCircle2 :size="14" />{{ updateMessage }}</p>
            <p v-else-if="!updateProgressVisible && updateMessage" class="success-box"><CheckCircle2 :size="14" />{{ updateMessage }}</p>
            <footer class="flex flex-wrap justify-end gap-2 border-t border-line pt-5">
              <Button type="button" :disabled="versionLoading || applyingUpdate" @click="loadVersion" variant="outline"><LoaderCircle v-if="versionLoading" :size="15" class="animate-spin" /><RefreshCw v-else :size="15" />刷新版本</Button>
              <Button type="button" :disabled="checkingUpdate || applyingUpdate" @click="checkForUpdate" variant="outline"><LoaderCircle v-if="checkingUpdate" :size="15" class="animate-spin" /><RefreshCw v-else :size="15" />{{ checkingUpdate ? '检查中…' : '检查更新' }}</Button>
              <Button type="button" :disabled="applyingUpdate || checkingUpdate" :title="versionInfo?.update_enabled ? undefined : '当前环境不支持在线更新'" @click="applyUpdate"><LoaderCircle v-if="applyingUpdate" :size="15" class="animate-spin" /><Package v-else :size="15" />{{ applyingUpdate ? '更新中…' : '更新到最新' }}</Button>
            </footer>
          </div>
        </div>
      </section>
      <section v-else-if="tab === 'mcp'">
        <div class="card p-5">
          <div class="card-head"><div><p class="eyebrow">Model Context Protocol</p><h2>MCP 接入</h2><p class="mt-2 text-xs text-muted-foreground">把工作台的 19 个工具（任务/成员/项目/评价/知识库）开放给任意支持 MCP 的客户端（Claude、Codex、Cursor 等）。协议版本 2025-11-25，Streamable HTTP 传输。注意：MCP 调用立即生效，没有站内 AI 的排队确认环节。</p></div><Cable :size="17" class="text-cyan" /></div>
          <div class="mt-5 space-y-4">
            <div class="field-label">接入地址
              <div class="mt-1 flex items-center gap-2">
                <code class="min-w-0 flex-1 rounded-lg border border-line bg-ink px-3 py-2 font-mono text-[12px] text-cyan">{{ mcpUrl }}</code>
                <Button type="button" @click="copyConfig('url')" class="shrink-0" variant="outline"><Check v-if="copied === 'url'" :size="14" /><Copy v-else :size="14" />{{ copied === 'url' ? '已复制' : '复制' }}</Button>
              </div>
            </div>
            <div class="field-label">
              <span class="flex items-center justify-between gap-3">认证方式一：设备凭证（推荐，长期有效，可在「绑定设备」随时吊销）
                <Button type="button" variant="link" class="h-auto px-0 text-[12px] font-semibold" @click="copyConfig('device')">{{ copied === 'device' ? '已复制配置' : '复制客户端配置' }}</Button>
              </span>
              <template v-if="deviceCredentialsReady">
                <pre class="mt-2 overflow-x-auto rounded-lg border border-line bg-ink p-3 font-mono text-[12px] leading-5 text-text-secondary">{{ JSON.stringify({
                  mcpServers: { workbench: { type: 'http', url: mcpUrl, headers: { 'X-Device-Id': getDeviceId(), 'X-Device-Token': getDeviceToken() } } }
                }, null, 2) }}</pre>
                <small>以上为本机已绑定的设备凭证，可直接粘贴到 MCP 客户端配置中。</small>
              </template>
              <template v-else>
                <small class="!mt-2">本设备还没有绑定凭证：在登录页勾选「保持登录」登录一次即可生成，然后回到本页复制配置。也可以用下方命令手动获取（返回体中的 device_token 字段）：</small>
                <pre class="mt-2 overflow-x-auto rounded-lg border border-line bg-ink p-3 font-mono text-[12px] leading-5 text-text-secondary">curl -X POST {{ curlLoginBase }}/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"你的账号","password":"你的密码","device_id":"my-mcp-client","device_name":"MCP 客户端"}'</pre>
              </template>
            </div>
            <div class="field-label">
              <span class="flex items-center justify-between gap-3">认证方式二：登录令牌（短期，1 天有效）
                <Button type="button" variant="link" class="h-auto px-0 text-[12px] font-semibold" @click="copyConfig('jwt')">{{ copied === 'jwt' ? '已复制配置' : '复制客户端配置' }}</Button>
              </span>
              <pre class="mt-2 overflow-x-auto rounded-lg border border-line bg-ink p-3 font-mono text-[12px] leading-5 text-text-secondary">{{ JSON.stringify({
                mcpServers: { workbench: { type: 'http', url: mcpUrl, headers: { Authorization: 'Bearer <access_token>' } } }
              }, null, 2) }}</pre>
            </div>
            <p class="text-[12px] leading-5 text-muted-foreground">安全说明：设备凭证与服务端绑定记录一一对应，可在「绑定设备」页解绑使其立即失效；令牌与凭证请勿写入公开仓库。</p>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
