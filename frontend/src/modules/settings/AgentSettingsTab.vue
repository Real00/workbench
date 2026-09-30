<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { CheckCircle2, LoaderCircle, Save, SlidersHorizontal, Network } from '@lucide/vue'
import { api, apiError } from '../../shared/api/client'
import McpServersSection from './McpServersSection.vue'
import SkillsSection from './SkillsSection.vue'
import { Button } from '@/components/ui/button'

interface AgentOptions { parallel_tool_calls: boolean; scout_enabled: boolean }

const options = ref<AgentOptions>({ parallel_tool_calls: true, scout_enabled: true })
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const saved = ref(false)

onMounted(async () => {
  try {
    const { data } = await api.get<{ agent?: AgentOptions }>('/ai-settings')
    if (data.agent) options.value = data.agent
  } catch (cause) { error.value = apiError(cause) }
  finally { loading.value = false }
})

async function save() {
  saving.value = true; error.value = ''; saved.value = false
  try {
    // 增量保存：只提交 agent 字段，不影响连接与 MCP 配置
    const { data } = await api.put<{ agent: AgentOptions }>('/ai-settings', { agent: options.value })
    options.value = data.agent
    saved.value = true
    window.setTimeout(() => { saved.value = false }, 2500)
  } catch (cause) { error.value = apiError(cause) }
  finally { saving.value = false }
}
</script>

<template>
  <div class="space-y-5">
    <section class="card p-5">
      <div class="card-head">
        <div>
          <p class="eyebrow">Runtime</p>
          <h2>运行开关</h2>
          <p class="mt-2 text-xs text-muted-foreground">控制 Pulse 对话中的工具调用方式与子代理行为，即时生效于下一轮对话。</p>
        </div>
        <SlidersHorizontal :size="17" class="text-cyan" />
      </div>
      <p v-if="loading" class="empty-inline mt-5">正在读取智能体配置…</p>
      <div v-else class="mt-5 space-y-4">
        <div class="field-label">
          并行工具调用
          <span class="mt-2 flex flex-wrap gap-1.5">
            <Button type="button" variant="ghost" :class="['kind-option', { 'kind-option--active': options.parallel_tool_calls }]" :aria-pressed="options.parallel_tool_calls" @click="options.parallel_tool_calls = true">允许</Button>
            <Button type="button" variant="ghost" :class="['kind-option', { 'kind-option--active': !options.parallel_tool_calls }]" :aria-pressed="!options.parallel_tool_calls" @click="options.parallel_tool_calls = false">每轮一个</Button>
          </span>
          <small>允许时模型可在一轮内并行发出多个工具调用，速度更快；改为「每轮一个」可降低多工具交织带来的误操作，行为更可预期。</small>
        </div>
        <div class="field-label">
          只读侦察子代理
          <span class="mt-2 flex flex-wrap gap-1.5">
            <Button type="button" variant="ghost" :class="['kind-option', { 'kind-option--active': options.scout_enabled }]" :aria-pressed="options.scout_enabled" @click="options.scout_enabled = true">启用</Button>
            <Button type="button" variant="ghost" :class="['kind-option', { 'kind-option--active': !options.scout_enabled }]" :aria-pressed="!options.scout_enabled" @click="options.scout_enabled = false">停用</Button>
          </span>
          <small>需要大量查阅任务、成员、项目或知识库时，Pulse 可派出一个只挂载读取工具的子代理代为收集事实，主对话保持简洁。子代理没有任何写入工具，不会产生变更。</small>
        </div>
        <p v-if="error" class="error-box" role="alert">{{ error }}</p>
        <p v-if="saved" class="success-box"><CheckCircle2 :size="14" />运行开关已保存</p>
        <footer class="flex flex-wrap justify-end gap-2 border-t border-line pt-5">
          <Button :disabled="saving || loading" @click="save"><LoaderCircle v-if="saving" :size="15" class="animate-spin" /><Save v-else :size="15" />{{ saving ? '保存中…' : '保存运行开关' }}</Button>
        </footer>
      </div>
    </section>

    <McpServersSection />
    <SkillsSection />

    <p class="flex items-start gap-2 px-1 text-[12px] leading-5 text-muted-foreground" role="note">
      <Network :size="14" class="mt-0.5 shrink-0 text-warning" />
      出站 MCP 与技能脚本在工作台服务端执行：MCP 结果与脚本输出都只是给模型的数据；写入类操作仍走站内排队确认。
    </p>
  </div>
</template>
