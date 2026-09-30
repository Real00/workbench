<script setup lang="ts">
import { AlertTriangle } from '@lucide/vue'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogMedia,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { confirmState, resolveConfirm } from './confirm'

const state = confirmState()

function onOpenChange(open: boolean) {
  if (!open) resolveConfirm(false)
}
</script>

<template>
  <AlertDialog :open="state.open" @update:open="onOpenChange">
    <AlertDialogContent class="sm:max-w-sm">
      <AlertDialogHeader>
        <AlertDialogMedia v-if="state.danger" class="bg-destructive/10 text-destructive">
          <AlertTriangle />
        </AlertDialogMedia>
        <AlertDialogTitle>{{ state.title }}</AlertDialogTitle>
        <AlertDialogDescription>
          {{ state.message || '此操作需要确认后才会执行。' }}
        </AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter>
        <AlertDialogCancel @click="resolveConfirm(false)">取消</AlertDialogCancel>
        <AlertDialogAction
          :variant="state.danger ? 'destructive' : 'default'"
          @click.capture="resolveConfirm(true)"
        >
          {{ state.confirmText }}
        </AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
</template>
