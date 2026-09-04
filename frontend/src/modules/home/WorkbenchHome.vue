<script setup lang="ts">
import { ArrowUpRight, Boxes } from '@lucide/vue'
import { homeModules } from '../../app/modules'
</script>

<template>
  <div class="page-wrap">
    <header class="workbench-hero">
      <div>
        <p class="eyebrow">Personal workspace</p>
        <h1>个人工作台</h1>
        <p>从一个入口访问日常工作模块，保持信息清晰、操作专注。</p>
      </div>
      <span class="workbench-hero__mark"><Boxes :size="28" /></span>
    </header>
    <section class="module-grid" aria-label="工作台模块">
      <RouterLink
        v-for="module in homeModules"
        :key="module.id"
        :to="module.homeCard ? module.homeCard.to : '/'"
        class="module-card"
      >
        <span class="module-card__icon"><component :is="module.icon" :size="22" /></span>
        <div>
          <h2>{{ module.title }}</h2>
          <p>{{ module.description }}</p>
        </div>
        <span class="module-card__action">{{ module.homeCard && module.homeCard.action }} <ArrowUpRight :size="14" /></span>
      </RouterLink>
    </section>
  </div>
</template>
