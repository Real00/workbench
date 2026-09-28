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
  SelectValue,
} from '@/components/ui/select'

const EMPTY = '__empty__'

const props = defineProps<{
  options: AppSelectOption<T>[]
  disabled?: boolean
  placeholder?: string
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
        'h-7 w-fit max-w-full min-w-0 shrink-0 gap-1 overflow-hidden px-2 text-xs whitespace-nowrap',
        '*:data-[slot=select-value]:!block *:data-[slot=select-value]:min-w-0 *:data-[slot=select-value]:truncate *:data-[slot=select-value]:!whitespace-nowrap',
        '[&_svg:not([class*=size-])]:size-3.5',
        triggerClass,
      )"
      :aria-label="ariaLabel ?? display"
    >
      <SelectValue :placeholder="placeholder ?? '请选择'" />
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
