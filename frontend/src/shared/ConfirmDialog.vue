<script setup lang="ts">
import { ref } from 'vue'
import { useDialogFocus } from './useDialogFocus'
import { AlertTriangle } from '@lucide/vue'
import { confirmState, resolveConfirm } from './confirm'

const state = confirmState()

const panel = ref<HTMLElement | null>(null)
useDialogFocus(panel, () => state.open, () => resolveConfirm(false))

</script>

<template>
  <Teleport to="body">
    <div
      v-if="state.open"
      ref="panel"
      class="fixed inset-0 z-[70] grid place-items-center bg-black/65 p-4"
      role="alertdialog"
      aria-modal="true"
      :aria-label="state.title"
      tabindex="-1"
      @click.self="resolveConfirm(false)"
    >
      <div class="w-[min(92vw,400px)] rounded-xl border border-line bg-panel p-5 shadow-[0_24px_60px_rgb(0_0_0/.5)]">
        <div class="flex items-start gap-3">
          <span v-if="state.danger" class="grid size-9 shrink-0 place-items-center rounded-lg bg-[rgb(248_113_113/.12)] text-[#f87171]"><AlertTriangle :size="18" /></span>
          <div class="min-w-0">
            <h3 class="font-display text-base font-semibold text-white">{{ state.title }}</h3>
            <p v-if="state.message" class="mt-1.5 text-xs leading-5 text-muted">{{ state.message }}</p>
          </div>
        </div>
        <footer class="mt-5 flex justify-end gap-2">
          <!-- 危险操作默认聚焦「取消」，避免回车误触 -->
          <button type="button" class="btn-secondary" autofocus @click="resolveConfirm(false)">取消</button>
          <button
            type="button"
            :class="state.danger ? 'btn-danger' : 'btn-primary'"
            @click="resolveConfirm(true)"
          >{{ state.confirmText }}</button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>
