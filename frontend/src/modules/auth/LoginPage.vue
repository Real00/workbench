<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Boxes, LockKeyhole, UserRound } from '@lucide/vue'
import { api, apiError, setToken } from '../../shared/api/client'

const router = useRouter()
const route = useRoute()
const username = ref('')
const password = ref('')
const remember = ref(false)
const loading = ref(false)
const error = ref('')

async function login() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.post<{ access_token: string }>('/auth/login', { username: username.value, password: password.value })
    setToken(data.access_token, remember.value)
    await router.replace(typeof route.query.redirect === 'string' ? route.query.redirect : '/')
  } catch (cause) {
    error.value = apiError(cause)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-grid min-h-screen bg-ink text-slate-200">
    <section class="relative hidden overflow-hidden border-r border-line p-12 lg:flex lg:flex-col lg:justify-between">
      <div class="absolute inset-0 pulse-field opacity-60" aria-hidden="true" />
      <div class="relative flex items-center gap-3">
        <span class="grid size-9 place-items-center rounded-lg bg-cyan text-ink"><Boxes :size="19" /></span>
        <strong class="font-display text-lg tracking-wider text-white">个人工作台</strong>
      </div>
      <div class="relative max-w-xl">
        <p class="eyebrow">Personal workspace</p>
        <h1 class="mt-5 font-display text-6xl font-semibold leading-[.98] text-white">汇聚日常工作<br><span class="text-cyan">专注每次行动。</span></h1>
        <div class="mt-12 pulse-track"><i style="left: 18%" /><i style="left: 51%" /><i style="left: 82%" /></div>
        <p class="mt-6 max-w-md text-sm leading-7 text-muted">在一个安全入口访问个人工作模块，让信息有序、操作直接。</p>
      </div>
      <p class="relative font-mono text-[10px] uppercase tracking-[.2em] text-muted">Authenticated personal workspace</p>
    </section>
    <section class="grid place-items-center px-6 py-12">
      <form class="w-full max-w-sm" @submit.prevent="login">
        <p class="eyebrow">Workspace access</p>
        <h2 class="mt-3 font-display text-3xl font-semibold text-white">进入控制台</h2>
        <p class="mt-2 text-sm text-muted">使用组织账号继续</p>
        <label class="field-label mt-8">用户名
          <span class="input-wrap"><UserRound :size="16" /><input v-model="username" autocomplete="username" required /></span>
        </label>
        <label class="field-label mt-4">密码
          <span class="input-wrap"><LockKeyhole :size="16" /><input v-model="password" type="password" autocomplete="current-password" required /></span>
        </label>
        <div class="mt-4 flex items-center justify-between text-xs">
          <label class="flex items-center gap-2 text-muted"><input v-model="remember" type="checkbox" class="accent-cyan" /> 保持登录</label>
        </div>
        <p v-if="error" class="error-box mt-4">{{ error }}</p>
        <button class="btn-primary mt-7 w-full" type="submit" :disabled="loading">{{ loading ? '登录中…' : '进入工作台' }} <ArrowRight :size="16" /></button>
        <p class="mt-6 text-center text-[11px] text-muted">访问令牌仅用于工作台 API 鉴权</p>
      </form>
    </section>
  </main>
</template>
