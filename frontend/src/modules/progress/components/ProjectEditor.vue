<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { Save, Trash2, X } from '@lucide/vue'
import { useProgressStore } from '../store'
import { memberPixelUri } from '../pixel-avatar'
import { projectStatusMap, type ProjectInput, type ProjectStatus } from '../types'
import AppSelect, { type AppSelectOption } from '../../../shared/AppSelect.vue'
import RichTextarea from '../../../shared/RichTextarea.vue'
import { confirmDialog } from '../../../shared/confirm'

const coverPresets = ['#36d9e9', '#5ce0ae', '#fcd34d', '#f87171', '#a78bfa', '#f472b6', '#38bdf8', '#94a3b8']

const store = useProgressStore()
const title = computed(() => store.editingProject ? '编辑项目' : '新增项目')
const form = reactive({
  name: '',
  description: '',
  background: '',
  started_at: '',
  member_ids: [] as string[],
  status: 'planning' as ProjectStatus,
  cover_color: '',
})

const linkedTasks = computed(() =>
  store.editingProject ? store.tasks.filter(task => task.project_id === store.editingProject?.id) : [],
)
const statusOptions: AppSelectOption<ProjectStatus>[] = Object.entries(projectStatusMap).map(
  ([value, label]) => ({ value: value as ProjectStatus, label }),
)

function toggleMember(memberId: string) {
  const index = form.member_ids.indexOf(memberId)
  if (index >= 0) form.member_ids.splice(index, 1)
  else form.member_ids.push(memberId)
}

watch(() => store.projectEditorOpen, (open) => {
  if (!open) return
  const source = store.editingProject
  Object.assign(form, {
    name: source?.name ?? '',
    description: source?.description ?? '',
    background: source?.background ?? '',
    started_at: source?.started_at ? source.started_at.slice(0, 10) : '',
    member_ids: [...(source?.member_ids ?? [])],
    status: source?.status ?? 'planning',
    cover_color: source?.cover_color ?? '',
  })
})

async function submit() {
  const payload: ProjectInput = {
    name: form.name,
    description: form.description,
    background: form.background,
    started_at: form.started_at || null,
    member_ids: [...form.member_ids],
    status: form.status,
    cover_color: form.cover_color || null,
  }
  await store.saveProject(payload)
}
async function removeProject() {
  const project = store.editingProject
  if (!project) return
  const ok = await confirmDialog({ title: `删除项目「${project.name}」？`, message: '项目下的任务会自动解除关联，任务本身不受影响。', confirmText: '删除项目' })
  if (ok) await store.deleteProject(project.id)
}
</script>

<template>
  <Teleport to="body">
    <div v-if="store.projectEditorOpen" class="fixed inset-0 z-50 bg-slate-900/30" @click.self="store.projectEditorOpen = false">
      <aside class="editor-panel" role="dialog" aria-modal="true" :aria-label="title">
        <header class="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
          <div class="min-w-0">
            <p class="eyebrow">Project</p>
            <h2 class="mt-1 truncate font-display text-xl text-text">{{ title }}</h2>
          </div>
          <button class="icon-btn" aria-label="关闭" @click="store.projectEditorOpen = false"><X :size="18" /></button>
        </header>
        <form class="space-y-5 overflow-y-auto p-5" @submit.prevent="submit">
          <section class="space-y-4">
            <p class="eyebrow">基本信息</p>
            <div class="grid grid-cols-2 gap-3">
              <label class="field-label">项目名称<input v-model="form.name" class="input" required maxlength="200" placeholder="例如：MYAI 工单平台" /></label>
              <label class="field-label">项目状态<AppSelect v-model="form.status" :options="statusOptions" /></label>
            </div>
            <label class="field-label">立项时间<input v-model="form.started_at" type="date" class="input" /></label>
            <div class="field-label">封面色
              <small>用于项目卡片顶部的封面横幅，也可以在下方自定义</small>
              <span class="mt-2 flex flex-wrap items-center gap-2">
                <button v-for="color in coverPresets" :key="color" type="button" :class="['cover-swatch', { 'cover-swatch--active': form.cover_color === color }]" :style="{ backgroundColor: color }" :aria-label="`封面色 ${color}`" @click="form.cover_color = color" />
                <input v-model="form.cover_color" type="color" class="h-8 w-10 cursor-pointer rounded border border-line bg-transparent p-1" aria-label="自定义封面色" />
                <input v-model="form.cover_color" class="input !mt-0 w-28 font-mono" maxlength="7" placeholder="#36d9e9" />
              </span>
            </div>
            <label class="field-label">项目描述
              <small>这个项目做什么、当前处于什么阶段</small>
              <RichTextarea v-model="form.description" :min-height="104" :maxlength="5000" counter placeholder="例如：工单系统二期，目标是打通 MYAI 与 IT 审批流，当前处于联调阶段。" />
            </label>
            <label class="field-label">项目背景
              <small>为什么立项、有哪些前置依赖或历史沿革</small>
              <RichTextarea v-model="form.background" :min-height="88" :maxlength="2000" counter placeholder="例如：一期工单系统仅覆盖 IT 内部，二期扩展到 HR 与行政流程。" />
            </label>
          </section>
          <section class="space-y-3 border-t border-line pt-5">
            <p class="eyebrow">关联人</p>
            <p class="text-[12px] text-muted">从团队成员中选择与该项目相关的人，便于说明分工与查找。</p>
            <div class="flex flex-wrap gap-1.5">
              <button v-for="member in store.members" :key="member.id" type="button" :class="['kind-option', 'flex items-center gap-1.5', { 'kind-option--active': form.member_ids.includes(member.id) }]" :aria-pressed="form.member_ids.includes(member.id)" @click="toggleMember(member.id)">
                <img :src="memberPixelUri(member.id, member.color)" alt="" width="14" height="14" class="rounded" />{{ member.name }}<span v-if="member.operator" class="text-[12px] text-muted">（我）</span>
              </button>
            </div>
            <p v-if="!store.members.length" class="empty-inline !py-2">还没有团队成员，先到成员管理中添加。</p>
          </section>
          <section v-if="store.editingProject" class="space-y-2 border-t border-line pt-5">
            <p class="eyebrow">关联任务</p>
            <p class="text-xs text-muted">{{ linkedTasks.length ? `${linkedTasks.length} 个任务挂在项目下，可在任务编辑中调整归属。` : '尚无任务关联此项目；任务可以不属于任何项目。' }}</p>
            <ul v-if="linkedTasks.length" class="space-y-1">
              <li v-for="task in linkedTasks.slice(0, 8)" :key="task.id" class="flex items-center justify-between gap-2 rounded-lg border border-line bg-panel-2 px-3 py-2 text-xs">
                <span class="truncate text-text">{{ task.title }}</span>
                <span class="shrink-0 font-mono text-[12px] text-muted">{{ task.progress }}%</span>
              </li>
            </ul>
          </section>
          <p v-if="store.error" class="error-box">{{ store.error }}</p>
          <footer class="flex justify-end gap-2 border-t border-line pt-5"><button v-if="store.editingProject" type="button" class="btn-danger mr-auto" :disabled="store.saving" @click="removeProject"><Trash2 :size="14" />删除</button><button type="button" class="btn-secondary" @click="store.projectEditorOpen = false"><X :size="14" />取消</button><button class="btn-primary" :disabled="store.saving"><Save :size="14" />{{ store.saving ? '保存中…' : '保存项目' }}</button></footer>
        </form>
      </aside>
    </div>
  </Teleport>
</template>
