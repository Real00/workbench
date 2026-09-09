<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Save, Trash2, X } from '@lucide/vue'
import { useProgressStore } from '../store'
import { entryKindMap, priorityMap, statusMap, type Priority, type ProgressEntryKind, type TaskInput, type TaskStatus } from '../types'
import AppSelect, { type AppSelectOption } from '../../../shared/AppSelect.vue'
import MarkdownView from '../../../shared/MarkdownView.vue'
import RichTextarea from '../../../shared/RichTextarea.vue'
import TaskResources from './TaskResources.vue'
import { confirmDialog } from '../../../shared/confirm'
import { useDialogFocus } from '../../../shared/useDialogFocus'

const store = useProgressStore()
const panel = ref<HTMLElement | null>(null)
useDialogFocus(panel, () => store.taskEditorOpen, () => { store.taskEditorOpen = false })
const blank = (): TaskInput => ({ title: '', description: '', status: 'todo', priority: 'medium', assignee_id: null, project_id: null, start_date: null, due_date: null, progress: 0, estimated_hours: null, tags: [] })
const form = reactive<TaskInput>(blank())
const tagsText = ref('')
const entryKind = ref<ProgressEntryKind>('update')
const entryContent = ref('')
const title = computed(() => store.editingTask ? '编辑任务' : '创建任务')
const entries = computed(() => [...(store.editingTask?.entries ?? [])].reverse())
const assignedToMe = computed(() => form.assignee_id === store.operatorMember?.id)
const assigneeOptions = computed<AppSelectOption[]>(() =>
  store.assignableMembers.map(member => ({
    value: member.id,
    label: member.operator ? `${member.name}（我）` : member.name,
    hint: member.skills.length ? member.skills.slice(0, 2).join(' / ') : undefined,
  })),
)
const projectOptions = computed<AppSelectOption[]>(() =>
  store.projects.map(project => ({ value: project.id, label: project.name })),
)
const statusOptions: AppSelectOption<TaskStatus>[] = Object.entries(statusMap).map(([value, label]) => ({ value: value as TaskStatus, label }))
const priorityOptions: AppSelectOption<Priority>[] = Object.entries(priorityMap).map(([value, label]) => ({ value: value as Priority, label }))
const entryKindOptions: AppSelectOption<ProgressEntryKind>[] = Object.entries(entryKindMap).map(([value, label]) => ({ value: value as ProgressEntryKind, label }))
const descriptionPreview = ref(false)

function assignToMe() {
  if (store.operatorMember) form.assignee_id = store.operatorMember.id
}

function dateValue(value: string | null | undefined) {
  return value ? value.slice(0, 10) : null
}

function formatTime(value: string) {
  return value.replace('T', ' ').slice(0, 16)
}

watch(() => store.taskEditorOpen, (open) => {
  if (!open) return
  const source = store.editingTask ?? blank()
  Object.assign(form, source, {
    start_date: dateValue(source.start_date),
    due_date: dateValue(source.due_date),
  })
  tagsText.value = source.tags.join(', ')
  entryKind.value = 'update'
  entryContent.value = ''
  descriptionPreview.value = false
})

async function submit() {
  await store.saveTask({ ...form, tags: tagsText.value.split(',').map(tag => tag.trim()).filter(Boolean) })
}

async function recordEntry() {
  if (!store.editingTask || !entryContent.value.trim()) return
  const ok = await store.addTaskEntry(store.editingTask.id, {
    kind: entryKind.value,
    content: entryContent.value.trim(),
  })
  if (ok) entryContent.value = ''
}
async function removeTask() {
  const task = store.editingTask
  if (!task) return
  const ok = await confirmDialog({ title: `删除任务「${task.title}」？`, message: '进度记录与相关资源会一并删除，操作无法恢复。', confirmText: '删除任务' })
  if (ok) await store.deleteTask(task.id)
}
</script>

<template>
  <Teleport to="body">
    <div v-if="store.taskEditorOpen" class="fixed inset-0 z-50 bg-slate-900/30" @click.self="store.taskEditorOpen = false">
      <aside ref="panel" tabindex="-1" class="editor-panel" role="dialog" aria-modal="true" :aria-label="title">
        <header class="flex items-center justify-between border-b border-line px-5 py-4"><div><p class="eyebrow">{{ store.editingTask?.id ?? 'NEW TASK' }}</p><h2 class="mt-1 font-display text-xl text-text">{{ title }}</h2></div><button class="icon-btn" aria-label="关闭" @click="store.taskEditorOpen = false"><X :size="18" /></button></header>
        <form class="task-editor-form" @submit.prevent="submit">
          <div class="task-editor-fields space-y-5">
          <label class="field-label">任务名称<input v-model="form.title" autofocus class="input" required maxlength="200" /></label>
          <div class="field-label">
            <span class="flex items-center justify-between gap-3">描述
              <span class="flex gap-1">
                <button type="button" :class="['kind-option', !descriptionPreview && 'kind-option--active']" @click="descriptionPreview = false">编辑</button>
                <button type="button" :class="['kind-option', descriptionPreview && 'kind-option--active']" @click="descriptionPreview = true">预览</button>
              </span>
            </span>
            <RichTextarea v-if="!descriptionPreview" v-model="form.description" :min-height="112" :max-height="320" placeholder="支持 Markdown：## 标题、**加粗**、- 列表、换行" />
            <div v-else class="mt-2 min-h-[112px] rounded-lg border border-line bg-ink p-4">
              <MarkdownView :source="form.description" />
            </div>
          </div>
          <label class="field-label">
            <span class="flex items-center justify-between gap-3">负责人<button v-if="store.operatorMember && !assignedToMe" type="button" class="text-[12px] font-semibold text-cyan" @click="assignToMe">分配给我</button></span>
            <AppSelect v-model="form.assignee_id" :options="assigneeOptions" placeholder="未分配" />
          </label>
          <label class="field-label">所属项目<AppSelect v-model="form.project_id" :options="projectOptions" placeholder="不关联项目" /></label>
          <div class="grid grid-cols-2 gap-3">
            <label class="field-label">状态<AppSelect v-model="form.status" :options="statusOptions" /></label>
            <label class="field-label">优先级<AppSelect v-model="form.priority" :options="priorityOptions" /></label>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <label class="field-label">开始日期<input v-model="form.start_date" type="date" class="input" /></label>
            <label class="field-label">截止日期<input v-model="form.due_date" type="date" class="input" /></label>
          </div>
          <div class="grid grid-cols-2 gap-3"><label class="field-label">预估工时<input v-model.number="form.estimated_hours" type="number" min="0" step=".5" class="input" /></label><label class="field-label">标签<input v-model="tagsText" class="input" placeholder="逗号分隔" /></label></div>
          <label class="field-label">完成进度 <span class="float-right font-mono text-cyan">{{ form.progress }}%</span><input v-model.number="form.progress" type="range" min="0" max="100" class="mt-3 w-full accent-cyan" /></label>
          <section v-if="store.editingTask" class="rounded-xl border border-line bg-panel-2 p-4">
            <p class="eyebrow">进度记录</p>
            <p class="mt-1 text-[12px] text-muted">记录阻塞、额外处理和推进过程，不要为此另开任务。</p>
            <div class="mt-3 grid gap-2">
              <label class="field-label">类型<AppSelect v-model="entryKind" :options="entryKindOptions" /></label>
              <label class="field-label">发生了什么<RichTextarea v-model="entryContent" :min-height="84" :maxlength="2000" placeholder="例如：验证码超时，先切备用通道才能继续" /></label>
            </div>
            <button type="button" class="btn-secondary mt-3" :disabled="store.saving || !entryContent.trim()" @click="recordEntry">记录进度</button>
            <ol v-if="entries.length" class="entry-timeline mt-4">
              <li v-for="entry in entries" :key="entry.id" class="entry-item">
                <span :class="['entry-kind', `entry-kind--${entry.kind}`]">{{ entryKindMap[entry.kind] }}</span>
                <p>{{ entry.content }}</p>
                <time>{{ formatTime(entry.created_at) }}</time>
              </li>
            </ol>
            <p v-else class="empty-inline !py-4">还没有进度记录</p>
          </section>
          <TaskResources v-if="store.editingTask" />
          <p v-else class="empty-inline !py-2">保存任务后可以上传图片、文档或添加外链。</p>
          <p v-if="store.error" class="error-box">{{ store.error }}</p>
          </div>
          <footer class="editor-actions"><button v-if="store.editingTask" type="button" class="btn-danger mr-auto" :disabled="store.saving" @click="removeTask"><Trash2 :size="14" />删除</button><button type="button" class="btn-secondary" @click="store.taskEditorOpen = false"><X :size="14" />取消</button><button class="btn-primary" type="submit" :disabled="store.saving"><Save :size="14" />{{ store.saving ? '保存中…' : '保存任务' }}</button></footer>
        </form>
      </aside>
    </div>
  </Teleport>
</template>
