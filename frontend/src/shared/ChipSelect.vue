<script setup lang="ts" generic="T extends string">
import type { HTMLAttributes } from 'vue'
import { computed } from 'vue'
import { cn } from '@/lib/utils'
import type { AppSelectOption } from './AppSelect.vue'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from '@/components/ui/select'

const EMPTY = '__empty__'

const props = defineProps<{
  options: AppSelectOption<T>[]
  disabled?: boolean
  triggerClass?: HTMLAttributes['class']
  ariaLabel?: string
}>()

const model = defineModel<T | null>()

const encoded = computed(() => {
  const value = model.value
  if (value == null) return undefined
  return value === '' ? EMPTY : value
})

const selected = computed(() => props.options.find(option => option.value === (model.value ?? '')))
const display = computed(() => selected.value?.label ?? '请选择')

function onChange(value: unknown) {
  if (value == null) {
    model.value = null
    return
  }
  if (value === EMPTY) {
    model.value = '' as T
    return
  }
  model.value = String(value) as T
}
</script>

<template>
  <Select :model-value="encoded" :disabled="disabled" @update:model-value="onChange">
    <SelectTrigger
      :class="cn(
        'chip-select-trigger h-auto w-fit min-h-0 gap-1 border-0 bg-transparent p-0 shadow-none ring-0 focus-visible:ring-2 [&_svg]:size-3',
        triggerClass,
      )"
      :aria-label="ariaLabel ?? display"
    >
      <slot :display="display" :open="false">{{ display }}</slot>
    </SelectTrigger>
    <SelectContent position="popper" align="start" class="min-w-36">
      <SelectItem
        v-for="option in options"
        :key="option.value || EMPTY"
        :value="option.value === '' ? EMPTY : option.value"
      >
        {{ option.label }}
      </SelectItem>
    </SelectContent>
  </Select>
</template>
