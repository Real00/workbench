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
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { kindBadgeVariant } from '../../../shared/kind-badge'

const store = useProgressStore()
const panel = ref<HTMLElement | null>(null)
useDialogFocus(panel, () => store.taskEditorOpen, () => { store.closeTask() })
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
    <div v-if="store.taskEditorOpen" class="fixed inset-0 z-50 bg-slate-900/30" @click.self="store.closeTask()">
      <aside ref="panel" tabindex="-1" class="editor-panel" role="dialog" aria-modal="true" :aria-label="title">
        <header class="flex items-center justify-between border-b border-line px-5 py-4"><div><p class="eyebrow">{{ store.editingTask?.id ?? 'NEW TASK' }}</p><h2 class="mt-1 font-display text-xl text-text">{{ title }}</h2></div><Button aria-label="关闭" @click="store.closeTask()" variant="ghost" size="icon"><X :size="18" /></Button></header>
        <form class="task-editor-form" @submit.prevent="submit">
          <div class="task-editor-fields space-y-5">
          <label class="field-label">任务名称<Input v-model="form.title" autofocus required maxlength="200" /></label>
          <div class="field-label">
            <span class="flex items-center justify-between gap-3">描述
              <span class="flex gap-1">
                <Button type="button" variant="ghost" :class="['kind-option', !descriptionPreview && 'kind-option--active']" @click="descriptionPreview = false">编辑</Button>
                <Button type="button" variant="ghost" :class="['kind-option', descriptionPreview && 'kind-option--active']" @click="descriptionPreview = true">预览</Button>
              </span>
            </span>
            <RichTextarea v-if="!descriptionPreview" v-model="form.description" :min-height="112" :max-height="320" placeholder="支持 Markdown：## 标题、**加粗**、- 列表、换行" />
            <div v-else class="mt-2 min-h-[112px] rounded-lg border border-line bg-ink p-4">
              <MarkdownView :source="form.description" />
            </div>
          </div>
          <label class="field-label">
            <span class="flex items-center justify-between gap-3">负责人<Button v-if="store.operatorMember && !assignedToMe" type="button" variant="link" class="h-auto px-0 text-[12px] font-semibold" @click="assignToMe">分配给我</Button></span>
            <AppSelect v-model="form.assignee_id" :options="assigneeOptions" placeholder="未分配" />
          </label>
          <label class="field-label">所属项目<AppSelect v-model="form.project_id" :options="projectOptions" placeholder="不关联项目" /></label>
          <div class="grid grid-cols-2 gap-3">
            <label class="field-label">状态<AppSelect v-model="form.status" :options="statusOptions" /></label>
            <label class="field-label">优先级<AppSelect v-model="form.priority" :options="priorityOptions" /></label>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <label class="field-label">开始日期<Input v-model="form.start_date" type="date" /></label>
            <label class="field-label">截止日期<Input v-model="form.due_date" type="date" /></label>
          </div>
          <div class="grid grid-cols-2 gap-3"><label class="field-label">预估工时<Input v-model.number="form.estimated_hours" type="number" min="0" step=".5" /></label><label class="field-label">标签<Input v-model="tagsText" placeholder="逗号分隔" /></label></div>
          <label class="field-label">完成进度 <span class="float-right font-mono text-cyan">{{ form.progress }}%</span><input v-model.number="form.progress" type="range" min="0" max="100" class="mt-3 w-full accent-cyan" /></label>
          <section v-if="store.editingTask" class="rounded-xl border border-line bg-panel-2 p-4">
            <p class="eyebrow">进度记录</p>
            <p class="mt-1 text-[12px] text-muted-foreground">记录阻塞、额外处理和推进过程，不要为此另开任务。</p>
            <div class="mt-3 grid gap-2">
              <label class="field-label">类型<AppSelect v-model="entryKind" :options="entryKindOptions" /></label>
              <label class="field-label">发生了什么<RichTextarea v-model="entryContent" :min-height="84" :maxlength="2000" placeholder="例如：验证码超时，先切备用通道才能继续" /></label>
            </div>
            <Button type="button" :disabled="store.saving || !entryContent.trim()" @click="recordEntry" class="mt-3" variant="outline">记录进度</Button>
            <ol v-if="entries.length" class="entry-timeline mt-4">
              <li v-for="entry in entries" :key="entry.id" class="entry-item">
                <Badge :variant="kindBadgeVariant(entry.kind)">{{ entryKindMap[entry.kind] }}</Badge>
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
          <footer class="editor-actions"><Button v-if="store.editingTask" type="button" :disabled="store.saving" @click="removeTask" class="mr-auto" variant="destructive"><Trash2 :size="14" />删除</Button><Button type="button" @click="store.closeTask()" variant="outline"><X :size="14" />取消</Button><Button type="submit" :disabled="store.saving"><Save :size="14" />{{ store.saving ? '保存中…' : '保存任务' }}</Button></footer>
        </form>
      </aside>
    </div>
  </Teleport>
</template>
