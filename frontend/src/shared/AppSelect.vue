<script lang="ts">
export interface AppSelectOption<T extends string = string> {
  value: T
  label: string
  hint?: string
}
</script>

<script setup lang="ts" generic="T extends string">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Check, ChevronDown } from '@lucide/vue'

const props = defineProps<{ options: AppSelectOption<T>[]; placeholder?: string }>()
const model = defineModel<T | null>()

const open = ref(false)
const root = ref<HTMLElement | null>(null)
const highlighted = ref(0)

const selected = computed(() => props.options.find(option => option.value === model.value))
const display = computed(() => selected.value?.label ?? props.placeholder ?? '请选择')

function choose(option: AppSelectOption<T>) {
  model.value = option.value
  open.value = false
}

function toggle() {
  if (open.value) {
    open.value = false
    return
  }
  highlighted.value = Math.max(
    0,
    props.options.findIndex(option => option.value === model.value),
  )
  open.value = true
}

function onKeydown(event: KeyboardEvent) {
  if (!open.value) {
    if (['Enter', ' ', 'ArrowDown', 'ArrowUp'].includes(event.key)) {
      event.preventDefault()
      toggle()
    }
    return
  }
  if (event.key === 'Escape') {
    event.preventDefault()
    open.value = false
  } else if (event.key === 'ArrowDown') {
    event.preventDefault()
    highlighted.value = Math.min(highlighted.value + 1, props.options.length - 1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    highlighted.value = Math.max(highlighted.value - 1, 0)
  } else if (event.key === 'Home') {
    event.preventDefault()
    highlighted.value = 0
  } else if (event.key === 'End') {
    event.preventDefault()
    highlighted.value = props.options.length - 1
  } else if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    const option = props.options[highlighted.value]
    if (option) choose(option)
  } else if (event.key === 'Tab') {
    open.value = false
  }
}

function onDocumentPointerdown(event: PointerEvent) {
  if (open.value && root.value && !root.value.contains(event.target as Node)) open.value = false
}

onMounted(() => document.addEventListener('pointerdown', onDocumentPointerdown))
onBeforeUnmount(() => document.removeEventListener('pointerdown', onDocumentPointerdown))
watch(open, isOpen => {
  if (!isOpen) return
  highlighted.value = Math.max(
    0,
    props.options.findIndex(option => option.value === model.value),
  )
})
</script>

<template>
  <div ref="root" class="select-wrap">
    <button
      type="button"
      :class="['select-trigger', open && 'select-trigger--open']"
      :aria-expanded="open"
      aria-haspopup="listbox"
      @click="toggle"
      @keydown="onKeydown"
    >
      <span :class="!selected && 'placeholder'">{{ display }}</span>
      <ChevronDown :size="14" />
    </button>
    <ul v-if="open" class="select-menu" role="listbox" :aria-label="placeholder ?? '选项列表'">
      <li v-for="(option, index) in options" :key="option.value">
        <button
          type="button"
          role="option"
          :aria-selected="option.value === model"
          :class="[
            'select-option',
            index === highlighted && 'select-option--active',
            option.value === model && 'select-option--selected',
          ]"
          @click="choose(option)"
          @mousemove="highlighted = index"
        >
          <b>{{ option.label }}</b>
          <small v-if="option.hint">{{ option.hint }}</small>
          <Check v-if="option.value === model" :size="13" class="shrink-0" />
        </button>
      </li>
    </ul>
  </div>
</template>
