<script setup lang="ts">
import CaptureComposer from './CaptureComposer.vue'
import CaptureList from './CaptureList.vue'
</script>
<template><div class="page-wrap"><header class="page-header"><div><p class="eyebrow">Capture</p><h1>随手记</h1><p>保留想法与上下文，需要时再推进。</p></div></header><section class="card"><CaptureComposer /></section><section class="card mt-5"><h2 class="mb-5">我的记录</h2><CaptureList /></section></div></template>
