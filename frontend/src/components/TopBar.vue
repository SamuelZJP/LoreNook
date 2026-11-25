<script setup lang="ts">
import { Menu } from 'lucide-vue-next'
import { sidebarOpen } from '@/composables/layout'
</script>

<template>
  <header class="topbar">
    <button class="btn ghost icon menu" type="button" aria-label="打开侧栏" @click="sidebarOpen = true"><Menu /></button>
    <slot />
  </header>
</template>

<style scoped>
.topbar {
  display: flex; align-items: center; gap: var(--space-2); height: var(--topbar-h); padding: 0 var(--space-3);
  padding-top: env(safe-area-inset-top); border-bottom: 1px solid var(--border); background: var(--bg-elev); flex-shrink: 0;
}
.menu { display: none; }
@media (max-width: 899px) { .menu { display: inline-flex; } }
</style>
