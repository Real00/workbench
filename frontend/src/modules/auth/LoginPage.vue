<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Globe, LockKeyhole, UserRound } from '@lucide/vue'
import { api, apiError, deviceLabel, ensureDeviceId, getApiBase, isTauriShell, setApiBase, setDeviceCredentials, setToken } from '../../shared/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

function defaultTauriApiBase() {
  const saved = getApiBase()
  if (saved) return saved
  // Android 模拟器访问宿主机用 10.0.2.2；真机请填局域网 IP
  if (typeof navigator !== 'undefined' && /Android/i.test(navigator.userAgent)) {
    return 'http://10.0.2.2:8080'
  }
  return 'http://127.0.0.1:8080'
}

const router = useRouter()
const route = useRoute()
const username = ref('')
const password = ref('')
const remember = ref(isTauriShell)
const loading = ref(false)
const error = ref('')
// Tauri 壳没有同源后端：首次启动需要指定服务器地址
const server = ref(isTauriShell ? defaultTauriApiBase() : getApiBase())
const deviceName = deviceLabel()

async function login() {
  loading.value = true
  error.value = ''
  try {
    if (isTauriShell) setApiBase(server.value)
    const payload: Record<string, unknown> = { username: username.value, password: password.value }
    if (remember.value) {
      payload.device_id = ensureDeviceId()
      payload.device_name = deviceName
    }
    const { data } = await api.post<{ access_token: string; device_token?: string }>('/auth/login', payload)
    setToken(data.access_token, remember.value)
    // 勾选保持登录即绑定设备（颁发长效凭证）；取消勾选则清除旧绑定凭证
    setDeviceCredentials(remember.value ? data.device_token ?? null : null)
    await router.replace(typeof route.query.redirect === 'string' ? route.query.redirect : '/')
  } catch (cause) {
    error.value = apiError(cause)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-grid min-h-screen bg-ink text-text">
    <section class="relative hidden overflow-hidden border-r border-line p-12 lg:flex lg:flex-col lg:justify-between">
      <div class="absolute inset-0 pulse-field opacity-60" aria-hidden="true" />
      <div class="login-brand">
        <img src="/work-wordmark.png" class="login-brand__wordmark" alt="WORK · 个人工作台" />
      </div>
      <div class="relative max-w-xl">
        <p class="eyebrow">Personal workspace</p>
        <h1 class="mt-5 font-display text-6xl font-semibold leading-[.98] text-text">汇聚日常工作<br><span class="text-cyan">专注每次行动。</span></h1>
        <div class="mt-12 pulse-track"><i style="left: 18%" /><i style="left: 51%" /><i style="left: 82%" /></div>
        <p class="mt-6 max-w-md text-sm leading-7 text-muted-foreground">在一个安全入口访问个人工作模块，让信息有序、操作直接。</p>
      </div>
    </section>
    <section class="grid place-items-center px-6 py-12">
      <form class="w-full max-w-sm" @submit.prevent="login">
        <div class="login-brand mb-8 lg:hidden">
          <img src="/work-wordmark.png" class="login-brand__wordmark max-w-[180px]" alt="WORK · 个人工作台" />
        </div>
        <p class="eyebrow">Workspace access</p>
        <h2 class="mt-3 font-display text-3xl font-semibold text-text">进入控制台</h2>
        <p class="mt-2 text-sm text-muted-foreground">使用组织账号继续</p>
        <label class="field-label mt-8">用户名
          <span class="relative mt-2 block">
            <UserRound :size="16" class="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2" />
            <Input v-model="username" class="!mt-0 pl-8" autocomplete="username" placeholder="输入用户名" required />
          </span>
        </label>
        <label v-if="isTauriShell" class="field-label mt-8">服务器地址
          <span class="relative mt-2 block">
            <Globe :size="16" class="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2" />
            <Input v-model="server" class="!mt-0 pl-8" autocomplete="url" spellcheck="false" placeholder="https://你的云端域名或 http://127.0.0.1:8080" />
          </span>
        </label>
        <label class="field-label mt-4">密码
          <span class="relative mt-2 block">
            <LockKeyhole :size="16" class="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2" />
            <Input v-model="password" class="!mt-0 pl-8" type="password" autocomplete="current-password" placeholder="输入密码" required />
          </span>
        </label>
        <div class="mt-4 flex items-center justify-between text-xs">
          <label class="flex items-center gap-2 text-muted-foreground"><input v-model="remember" type="checkbox" class="accent-cyan" /> 保持登录</label>
        </div>
        <p v-if="error" class="error-box mt-4">{{ error }}</p>
        <Button type="submit" :disabled="loading" class="mt-7 w-full">{{ loading ? '登录中…' : '进入工作台' }} <ArrowRight :size="16" /></Button>
        <p class="mt-6 text-center text-[12px] text-muted-foreground">访问令牌仅用于工作台 API 鉴权</p>
      </form>
    </section>
  </main>
</template>
