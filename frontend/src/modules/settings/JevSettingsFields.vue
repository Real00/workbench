<script setup lang="ts">
import { ref } from 'vue'
import { LoaderCircle, PlugZap } from '@lucide/vue'
import { api, apiError } from '../../shared/api/client'

export interface JevSettings {
  enabled: boolean
  base_url: string
  model: string
  threshold: number
  timeout_seconds: number
  api_key_masked: string
}

const settings = defineModel<JevSettings>({ required: true })
const apiKey = defineModel<string>('apiKey', { required: true })
defineProps<{ disabled: boolean }>()
const testing = ref(false)
const result = ref('')
const error = ref('')
async function test() {
  testing.value = true; result.value = ''; error.value = ''
  try {
    const { api_key_masked: _masked, ...options } = settings.value
    await api.post('/ai-settings/jev/test', { ...options, api_key: apiKey.value || undefined }, { timeout: 20_000 })
    result.value = 'Jev 判断接口连接正常（未保存）'
  } catch (cause) { error.value = apiError(cause) }
  finally { testing.value = false }
}
</script>

<template>
  <fieldset class="space-y-4 rounded-xl border border-line p-4" :disabled="disabled || testing">
    <legend class="px-2 text-sm font-semibold">Jev 工具选择（可选）</legend>
    <p class="text-xs leading-5 text-muted">使用 TypeSafe Jev 预选相关工具，主模型继续负责参数与回复。启用后，当前请求、最近的对话文本和工具描述会发送至配置的 Jev 服务。失败或未选中时自动使用原有工具发现流程。</p>
    <label class="flex items-center gap-2 text-sm"><input v-model="settings.enabled" type="checkbox" />启用 Jev 工具预选</label>
    <label class="field-label">Jev Base URL<input v-model="settings.base_url" class="input font-mono" type="url" required /><small>TypeSafe API 基础地址，默认 https://api.typesafe.ai/v1</small></label>
    <label class="field-label">Jev 模型<input v-model="settings.model" class="input font-mono" required placeholder="jev-latest" /></label>
    <label class="field-label">TypeSafe API Key<input v-model="apiKey" class="input font-mono" type="password" autocomplete="new-password" :required="settings.enabled && !settings.api_key_masked" :placeholder="settings.api_key_masked || '填写独立的 TypeSafe 密钥'" /><small>单独加密保存；留空保留已有密钥。与上方主模型密钥相互独立。</small></label>
    <div class="grid gap-4 sm:grid-cols-2">
      <label class="field-label">预选概率阈值<input v-model.number="settings.threshold" class="input" type="number" min="0.5" max="1" step="0.05" required /><small>只预加载超过阈值的工具，最多 5 个。</small></label>
      <label class="field-label">超时（秒）<input v-model.number="settings.timeout_seconds" class="input" type="number" min="0.1" max="5" step="0.1" required /><small>单次最多 5 秒。连续超时 3 次后暂停 Jev 60 秒，使用默认工具发现流程；冷却后自动尝试恢复。</small></label>
    </div>
    <p v-if="error" class="error-box" role="alert">{{ error }}</p>
    <p v-if="result" class="success-box" role="status">{{ result }}</p>
    <button type="button" class="btn-secondary" @click="test"><LoaderCircle v-if="testing" :size="15" class="animate-spin" /><PlugZap v-else :size="15" />{{ testing ? '测试 Jev 中…' : '测试 Jev 连接' }}</button>
  </fieldset>
</template>
