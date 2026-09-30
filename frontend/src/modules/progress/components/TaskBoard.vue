<script setup lang="ts">
import { ref } from 'vue'
import { Calendar, ChevronsLeft, Folder, Paperclip, User } from '@lucide/vue'
import ChipSelect from '../../../shared/ChipSelect.vue'
import type { AppSelectOption } from '../../../shared/AppSelect.vue'
import { Badge } from '@/components/ui/badge'
import { useProgressStore } from '../store'
import { isBlocked, latestEntry, priorityMap, statusMap, type Task, type TaskStatus } from '../types'

const props = defineProps<{ tasks: Task[] }>()
const store = useProgressStore()
const columns: TaskStatus[] = ['todo', 'in_progress', 'done', 'cancelled']

const statusOptions: AppSelectOption<TaskStatus>[] = Object.entries(statusMap).map(([value, label]) => ({
  value: value as TaskStatus,
  label,
}))

/* 看板拖拽：失败时 store 不做乐观更新，卡片自动停留在原列 */
const draggingId = ref<string | null>(null)
const dragOverColumn = ref<TaskStatus | null>(null)
const expandedColumns = ref(new Set<TaskStatus>())

function tasksIn(column: TaskStatus): Task[] {
  return props.tasks.filter(task => task.status === column)
}

function isCollapsed(column: TaskStatus): boolean {
  return !tasksIn(column).length && !expandedColumns.value.has(column)
}

function expandColumn(column: TaskStatus) {
  expandedColumns.value.add(column)
}

function collapseColumn(column: TaskStatus) {
  expandedColumns.value.delete(column)
}

function onDragStart(task: Task, event: DragEvent) {
  // 与卡片上的状态选择保持一致：已取消为终态，不再拖动
  if (task.status === 'cancelled') {
    event.preventDefault()
    return
  }
  draggingId.value = task.id
  event.dataTransfer?.setData('text/plain', task.id)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}

function onDragOver(column: TaskStatus) {
  if (!draggingId.value) return
  dragOverColumn.value = column
  expandColumn(column)
}

function onDragEnd() {
  draggingId.value = null
  dragOverColumn.value = null
}

async function onDrop(column: TaskStatus) {
  const id = draggingId.value
  if (!id) return
  onDragEnd()
  const task = props.tasks.find(item => item.id === id)
  if (!task || task.status === column) return
  await store.patchTask(task.id, { status: column })
}

async function onStatusChange(task: Task, status: TaskStatus | null | undefined) {
  if (!status || status === task.status) return
  await store.patchTask(task.id, { status })
}

function projectName(task: Task): string | null {
  return store.projects.find(project => project.id === task.project_id)?.name ?? null
}

function assigneeName(task: Task): string {
  return store.memberMap.get(task.assignee_id ?? '')?.name ?? '未分配'
}

function today(): string {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

function isOverdue(task: Task): boolean {
  if (!task.due_date || task.status === 'done' || task.status === 'cancelled') return false
  return task.due_date.slice(0, 10) < today()
}
</script>

<template>
  <div class="task-board">
    <section
      v-for="column in columns"
      :key="column"
      :class="[
        'board-column',
        `board-column--${column}`,
        {
          'board-column--collapsed': isCollapsed(column),
          'board-column--drop': dragOverColumn === column,
        },
      ]"
      @dragover.prevent="onDragOver(column)"
      @drop.prevent="onDrop(column)"
    >
      <button
        v-if="isCollapsed(column)"
        type="button"
        class="board-column__rail"
        :aria-label="`展开${statusMap[column]}列（暂无任务）`"
        @click="expandColumn(column)"
      >
        <span class="board-column__rail-title">{{ statusMap[column] }}</span>
        <Badge variant="secondary" as="span" class="shrink-0">0</Badge>
      </button>
      <template v-else>
        <header class="flex items-center justify-between gap-2">
          <h2>{{ statusMap[column] }}</h2>
          <span class="flex shrink-0 items-center gap-1">
            <Badge variant="secondary">{{ tasksIn(column).length }}</Badge>
            <button
              v-if="!tasksIn(column).length"
              type="button"
              class="board-column__collapse"
              :aria-label="`收起${statusMap[column]}列`"
              title="收起空列"
              @click="collapseColumn(column)"
            >
              <ChevronsLeft :size="13" />
            </button>
          </span>
        </header>
        <div class="mt-3 space-y-2">
          <p v-if="!tasksIn(column).length" class="board-column__empty">{{ draggingId ? '松开移到这里' : '暂无任务，可拖入卡片' }}</p>
          <article
            v-for="task in tasksIn(column)"
            :key="task.id"
            class="board-card"
            role="button"
            tabindex="0"
            :class="{ 'board-card--dragging': draggingId === task.id }"
            :draggable="task.status === 'cancelled' ? 'false' : 'true'"
            @click="store.openTask(task)"
            @keydown.enter="store.openTask(task)"
            @dragstart="onDragStart(task, $event)"
            @dragend="onDragEnd"
          >
            <div class="board-card__top">
              <h3>{{ task.title }}</h3>
              <div class="board-card__chip" @click.stop @dragstart.stop>
                <ChipSelect
                  :model-value="task.status"
                  :options="statusOptions"
                  :disabled="task.status === 'cancelled' || store.saving"
                  :aria-label="`修改状态：${isBlocked(task) ? '阻塞' : statusMap[task.status]}`"
                  @update:model-value="status => onStatusChange(task, status)"
                />
              </div>
            </div>
            <p v-if="isBlocked(task)" class="board-card__blocked">阻塞 · {{ latestEntry(task)?.content }}</p>
            <p v-else-if="latestEntry(task)?.content">{{ latestEntry(task)?.content }}</p>
            <p v-else-if="task.tags.length">{{ task.tags.join(' / ') }}</p>
            <ul class="board-card__meta">
              <li v-if="projectName(task)"><Folder :size="12" />{{ projectName(task) }}</li>
              <li><User :size="12" />{{ assigneeName(task) }}</li>
              <li v-if="task.due_date" :class="{ 'board-card__meta--overdue': isOverdue(task) }">
                <Calendar :size="12" />{{ task.due_date.slice(0, 10) }}<template v-if="isOverdue(task)"> · 已逾期</template>
              </li>
              <li :class="`board-card__priority board-card__priority--${task.priority}`">{{ priorityMap[task.priority] }}</li>
            </ul>
            <div class="board-card__foot">
              <div class="progress-line min-w-0 flex-1"><i :style="{ width: `${task.progress}%` }" /></div>
              <span class="shrink-0 font-mono text-[12px] text-muted-foreground">{{ task.progress }}%</span>
              <span
                v-if="task.resources.length"
                class="board-card__resources shrink-0 font-mono text-[12px] text-muted-foreground"
                :title="`${task.resources.length} 个资源，点击查看`"
                :aria-label="`${task.resources.length} 个资源`"
              ><Paperclip :size="12" />{{ task.resources.length }}</span>
            </div>
          </article>
        </div>
      </template>
    </section>
  </div>
</template>

<style scoped>
/* 空列收起为窄轨：覆盖全局四列等宽网格，保证非空列获得更多宽度 */
.task-board {
  display: flex;
  gap: 12px;
  align-items: stretch;
  overflow-x: auto;
}
.board-column {
  flex: 1 1 230px;
  min-width: 230px;
}
.board-column--drop {
  border-color: var(--color-cyan);
  border-style: dashed;
  background: rgb(37 99 235 / .06);
}
/* 空列落点：虚线槽位给出可投放暗示，拖拽中切换文案 */
.board-column__empty {
  display: grid;
  min-height: 76px;
  place-items: center;
  border: 1px dashed #d0d5dd;
  border-radius: 10px;
  background: rgb(255 255 255 / .45);
  font-size: 12px;
  color: var(--muted-foreground);
}
.board-column--drop .board-column__empty {
  border-color: var(--color-cyan);
  background: rgb(37 99 235 / .06);
}
.board-column--collapsed {
  flex: 0 0 52px;
  min-width: 52px;
  max-width: 52px;
  padding: 12px 4px;
}
.board-column__rail {
  display: flex;
  width: 100%;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  border: 0;
  background: transparent;
  padding: 0;
}
.board-column__rail-title {
  writing-mode: vertical-rl;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: .14em;
  color: var(--color-text-secondary);
}
.board-column__collapse {
  display: grid;
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 6px;
  color: var(--muted-foreground);
}
.board-column__collapse:hover {
  border-color: var(--color-line);
  background: var(--color-panel);
  color: var(--color-text);
}
/* 卡片以摘要为主：标题 + 状态快捷修改，其余编辑移入详情 */
.board-card__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}
.board-card__top h3 {
  flex: 1 1 auto;
  min-width: 0;
  margin-top: 0;
}
.board-card__chip {
  flex-shrink: 0;
}
.board-card--dragging {
  opacity: .45;
}
.board-card__blocked {
  color: var(--color-danger);
}
.board-card__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 12px;
  margin-top: 10px;
  font-size: 12px;
  color: var(--muted-foreground);
}
.board-card__meta li {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 4px;
}
.board-card__meta svg {
  flex-shrink: 0;
  color: #98a2b3;
}
.board-card__meta--overdue {
  color: var(--color-danger);
}
.board-card__meta--overdue svg {
  color: var(--color-danger);
}
.board-card__priority--urgent {
  color: var(--color-danger);
  font-weight: 600;
}
.board-card__priority--high {
  color: var(--color-warning);
}
.board-card__priority--medium {
  color: var(--color-text-secondary);
}
.board-card__priority--low {
  color: #98a2b3;
}
.board-card__resources {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  border: 1px solid var(--color-line);
  border-radius: 6px;
  padding: 1px 5px;
}
</style>
