<script setup lang="ts" generic="T extends string">
import type { HTMLAttributes } from 'vue'
import { ChevronDown } from '@lucide/vue'
import AppSelect, { type AppSelectOption } from './AppSelect.vue'

defineProps<{
  options: AppSelectOption<T>[]
  disabled?: boolean
  triggerClass?: HTMLAttributes['class']
  ariaLabel?: string
}>()

const model = defineModel<T | null>()
</script>

<template>
  <AppSelect v-model="model" :options="options" :disabled="disabled">
    <template #trigger="{ open, display, disabled: isDisabled, toggle, keydown }">
      <button
        type="button"
        :class="[triggerClass, open && 'chip-select--open']"
        :aria-expanded="open"
        :aria-label="ariaLabel ?? display"
        :disabled="isDisabled"
        aria-haspopup="listbox"
        @click="toggle"
        @keydown="keydown"
      >
        <slot :display="display" :open="open">{{ display }}</slot>
        <ChevronDown v-if="!isDisabled" :size="12" />
      </button>
    </template>
  </AppSelect>
</template>
