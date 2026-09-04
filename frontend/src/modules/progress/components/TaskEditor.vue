<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Trash2, X } from '@lucide/vue'
import { useProgressStore } from '../store'
import { entryKindMap, priorityMap, statusMap, type Priority, type ProgressEntryKind, type TaskInput, type TaskStatus } from '../types'
import TaskResources from './TaskResources.vue'

const store = useProgressStore()
const blank = (): TaskInput => ({ title: '', description: '', status: 'todo', priority: 'medium', assignee_id: null, project_id: null, start_date: null, due_date: null, progress: 0, estimated_hours: null, tags: [] })
const form = reactive<TaskInput>(blank())
const tagsText = ref('')
const entryKind = ref<ProgressEntryKind>('update')
const entryContent = ref('')
const title = computed(() => store.editingTask ? '编辑任务' : '创建任务')
const entries = computed(() => [...(store.editingTask?.entries ?? [])].reverse())
const assignedToMe = computed(() => form.assignee_id === store.operatorMember?.id)

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
</script>

<template>
  <Teleport to="body">
    <div v-if="store.taskEditorOpen" class="fixed inset-0 z-50 bg-black/65" @click.self="store.taskEditorOpen = false">
      <aside class="editor-panel" role="dialog" aria-modal="true" :aria-label="title">
        <header class="flex items-center justify-between border-b border-line px-5 py-4"><div><p class="eyebrow">{{ store.editingTask?.id ?? 'NEW TASK' }}</p><h2 class="mt-1 font-display text-xl text-white">{{ title }}</h2></div><button class="icon-btn" aria-label="关闭" @click="store.taskEditorOpen = false"><X :size="18" /></button></header>
        <form class="space-y-5 overflow-y-auto p-5" @submit.prevent="submit">
          <label class="field-label">任务名称<input v-model="form.title" class="input" required maxlength="200" /></label>
          <label class="field-label">描述<textarea v-model="form.description" class="input min-h-24 py-3" /></label>
          <label class="field-label">
            <span class="flex items-center justify-between gap-3">负责人<button v-if="store.operatorMember && !assignedToMe" type="button" class="text-[10px] font-semibold text-cyan" @click="assignToMe">分配给我</button></span>
            <select v-model="form.assignee_id" class="input"><option :value="null">未分配</option><option v-for="member in store.assignableMembers" :key="member.id" :value="member.id">{{ member.operator ? `${member.name}（我）` : member.name }}{{ member.skills.length ? ` · ${member.skills.slice(0, 2).join(' / ')}` : '' }}</option></select>
          </label>
          <label class="field-label">所属项目<select v-model="form.project_id" class="input"><option :value="null">不关联项目</option><option v-for="project in store.projects" :key="project.id" :value="project.id">{{ project.name }}</option></select></label>
          <div class="grid grid-cols-2 gap-3">
            <label class="field-label">状态<select v-model="form.status" class="input"><option v-for="item in (Object.keys(statusMap) as TaskStatus[])" :key="item" :value="item">{{ statusMap[item] }}</option></select></label>
            <label class="field-label">优先级<select v-model="form.priority" class="input"><option v-for="item in (Object.keys(priorityMap) as Priority[])" :key="item" :value="item">{{ priorityMap[item] }}</option></select></label>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <label class="field-label">开始日期<input v-model="form.start_date" type="date" class="input" /></label>
            <label class="field-label">截止日期<input v-model="form.due_date" type="date" class="input" /></label>
          </div>
          <div class="grid grid-cols-2 gap-3"><label class="field-label">预估工时<input v-model.number="form.estimated_hours" type="number" min="0" step=".5" class="input" /></label><label class="field-label">标签<input v-model="tagsText" class="input" placeholder="逗号分隔" /></label></div>
          <label class="field-label">完成进度 <span class="float-right font-mono text-cyan">{{ form.progress }}%</span><input v-model.number="form.progress" type="range" min="0" max="100" class="mt-3 w-full accent-cyan" /></label>
          <section v-if="store.editingTask" class="rounded-xl border border-line bg-panel-2 p-4">
            <p class="eyebrow">进度记录</p>
            <p class="mt-1 text-[11px] text-muted">记录阻塞、额外处理和推进过程，不要为此另开任务。</p>
            <div class="mt-3 grid gap-2">
              <label class="field-label">类型<select v-model="entryKind" class="input"><option v-for="(label, kind) in entryKindMap" :key="kind" :value="kind">{{ label }}</option></select></label>
              <label class="field-label">发生了什么<textarea v-model="entryContent" class="input min-h-20 py-3" maxlength="2000" placeholder="例如：验证码超时，先切备用通道才能继续" /></label>
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
          <footer class="flex justify-end gap-2 border-t border-line pt-5"><button v-if="store.editingTask" type="button" class="btn-danger mr-auto" :disabled="store.saving" @click="store.deleteTask(store.editingTask.id)"><Trash2 :size="14" />删除</button><button type="button" class="btn-secondary" @click="store.taskEditorOpen = false">取消</button><button class="btn-primary" type="submit" :disabled="store.saving">{{ store.saving ? '保存中…' : '保存任务' }}</button></footer>
        </form>
      </aside>
    </div>
  </Teleport>
</template>
