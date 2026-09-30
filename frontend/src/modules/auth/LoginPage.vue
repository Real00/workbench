<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Eye, EyeOff, Globe, LockKeyhole, UserRound } from '@lucide/vue'
import { api, apiError, DEFAULT_TAURI_API_BASE, deviceLabel, ensureDeviceId, getApiBase, isTauriShell, setApiBase, setDeviceCredentials, setToken } from '../../shared/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const router = useRouter()
const route = useRoute()
const username = ref('')
const password = ref('')
const showPassword = ref(false)
const remember = ref(isTauriShell)
const loading = ref(false)
const error = ref('')
// Tauri 壳默认连云端；仍可改服务器地址。已保存的 localStorage 优先（见 getApiBase）
const server = ref(isTauriShell ? (getApiBase() || DEFAULT_TAURI_API_BASE) : getApiBase())
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
      <ul class="login-modules relative" aria-label="工作台包含的模块">
        <li>进度管理<span>任务、项目与成员节奏</span></li>
        <li>知识库<span>文档、条目与标签沉淀</span></li>
        <li>订阅<span>远程源定时解析为文章</span></li>
        <li>随手记<span>想法、资讯与上下文</span></li>
      </ul>
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
        <h2 class="mt-3 font-display text-3xl font-semibold text-text">进入工作台</h2>
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
            <Input v-model="server" class="!mt-0 pl-8" autocomplete="url" spellcheck="false" placeholder="https://workbench.reelab.cc" />
          </span>
        </label>
        <label class="field-label mt-4">密码
          <span class="relative mt-2 block">
            <LockKeyhole :size="16" class="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2" />
            <Input v-model="password" class="!mt-0 pr-10 pl-8" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" placeholder="输入密码" required />
            <button type="button" class="password-toggle" :aria-label="showPassword ? '隐藏密码' : '显示密码'" :aria-pressed="showPassword" :title="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword">
              <EyeOff v-if="showPassword" :size="15" /><Eye v-else :size="15" />
            </button>
          </span>
        </label>
        <div class="mt-4 text-xs">
          <label class="flex items-center gap-2 text-muted-foreground"><input v-model="remember" type="checkbox" class="accent-cyan" /> 保持登录</label>
          <p class="mt-1.5 text-[12px] leading-5 text-muted-foreground">勾选后记住此设备，下次打开无需重新登录；退出请用侧栏「退出登录」。</p>
        </div>
        <p v-if="error" class="error-box mt-4">{{ error }}</p>
        <Button type="submit" :disabled="loading" class="mt-7 w-full">{{ loading ? '登录中…' : '进入工作台' }} <ArrowRight :size="16" /></Button>
        <p class="mt-6 text-center text-[12px] text-muted-foreground">没有账号？联系管理员开通后再登录</p>
      </form>
    </section>
  </main>
</template>
