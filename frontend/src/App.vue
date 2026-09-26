<script setup lang="ts">
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
</script>

<template>
  <TooltipProvider>
    <RouterView />
    <Toaster position="top-center" :rich-colors="true" close-button />
  </TooltipProvider>
</template>
