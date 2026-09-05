<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { Bold, Code, Heading2, Italic, Link2, List, Quote } from '@lucide/vue'

const props = withDefaults(
  defineProps<{
    placeholder?: string
    minHeight?: number
    maxHeight?: number
    maxlength?: number
    mono?: boolean
    toolbar?: boolean
    counter?: boolean
    required?: boolean
  }>(),
  { minHeight: 96, maxHeight: 480, mono: false, toolbar: false, counter: false, required: false },
)

const model = defineModel<string>()
const el = ref<HTMLTextAreaElement | null>(null)

function resize() {
  const node = el.value
  if (!node) return
  node.style.height = 'auto'
  node.style.height = `${Math.min(Math.max(node.scrollHeight, props.minHeight), props.maxHeight)}px`
}

watch(() => model.value, async () => {
  await nextTick()
  resize()
})
onMounted(resize)

function focusAt(start: number, end: number) {
  void nextTick(() => {
    const node = el.value
    if (!node) return
    node.focus()
    node.setSelectionRange(start, end)
    resize()
  })
}

function wrap(before: string, after: string, sample: string) {
  const node = el.value
  const value = model.value ?? ''
  const start = node?.selectionStart ?? value.length
  const end = node?.selectionEnd ?? start
  const selected = value.slice(start, end) || sample
  model.value = `${value.slice(0, start)}${before}${selected}${after}${value.slice(end)}`
  focusAt(start + before.length, start + before.length + selected.length)
}

function prefixLine(prefix: string) {
  const node = el.value
  const value = model.value ?? ''
  const caret = node?.selectionStart ?? value.length
  const lineStart = value.lastIndexOf('\n', Math.max(caret - 1, 0)) + 1
  model.value = `${value.slice(0, lineStart)}${prefix}${value.slice(lineStart)}`
  focusAt(caret + prefix.length, caret + prefix.length)
}

const tools = [
  { title: '标题', icon: Heading2, run: () => prefixLine('## ') },
  { title: '加粗', icon: Bold, run: () => wrap('**', '**', '加粗文字') },
  { title: '斜体', icon: Italic, run: () => wrap('*', '*', '斜体文字') },
  { title: '行内代码', icon: Code, run: () => wrap('`', '`', 'code') },
  { title: '列表', icon: List, run: () => prefixLine('- ') },
  { title: '引用', icon: Quote, run: () => prefixLine('> ') },
  { title: '链接', icon: Link2, run: () => wrap('[', '](https://)', '链接文字') },
] as const

defineExpose({ focus: () => el.value?.focus() })
</script>

<template>
  <div class="rich-textarea" :class="mono && 'rich-textarea--mono'">
    <div v-if="toolbar" class="rich-toolbar">
      <button
        v-for="tool in tools"
        :key="tool.title"
        type="button"
        class="rich-tool"
        :title="tool.title"
        :aria-label="tool.title"
        @mousedown.prevent="tool.run()"
      >
        <component :is="tool.icon" :size="13" />
      </button>
    </div>
    <textarea
      ref="el"
      v-model="model"
      class="rich-input"
      :style="{ minHeight: `${minHeight}px`, maxHeight: `${maxHeight}px` }"
      :maxlength="maxlength"
      :placeholder="placeholder"
      :required="required"
      @input="resize"
    />
    <div v-if="counter && maxlength" class="rich-counter font-mono">{{ (model ?? '').length }}/{{ maxlength }}</div>
  </div>
</template>
