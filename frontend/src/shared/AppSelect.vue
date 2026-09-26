<script lang="ts">
export interface AppSelectOption<T extends string = string> {
  value: T
  label: string
  hint?: string
}

const EMPTY = '__empty__'
</script>

<script setup lang="ts" generic="T extends string">
import { computed } from 'vue'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const props = defineProps<{
  options: AppSelectOption<T>[]
  placeholder?: string
  disabled?: boolean
}>()
const model = defineModel<T | null>()

const encoded = computed(() => {
  const value = model.value
  if (value == null) return undefined
  return value === '' ? EMPTY : value
})

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
    <SelectTrigger class="mt-2 h-10 w-full min-w-0">
      <SelectValue :placeholder="placeholder ?? '请选择'" />
    </SelectTrigger>
    <SelectContent position="popper" class="w-(--reka-select-trigger-width)">
      <SelectItem
        v-for="option in options"
        :key="option.value || EMPTY"
        :value="option.value === '' ? EMPTY : option.value"
      >
        <span>{{ option.label }}</span>
        <span v-if="option.hint" class="text-muted-foreground">{{ option.hint }}</span>
      </SelectItem>
    </SelectContent>
  </Select>
</template>
