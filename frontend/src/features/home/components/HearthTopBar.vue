<script setup lang="ts">
import ThemeToggle from './ThemeToggle.vue'
</script>

<template>
  <header class="topbar">
    <RouterLink class="mark" to="/" aria-label="炉隅 Lore Nook 首页">
      <svg width="18" height="22" viewBox="0 0 18 22" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 1.5c1.2 3.2 5.5 5.6 5.5 10.4A5.5 5.5 0 0 1 9 17.4a5.5 5.5 0 0 1-5.5-5.5C3.5 9 6 7.6 6.6 5.2 7.8 6.4 8 8 8 9.2 9.6 7.6 9.6 4.2 9 1.5Z" /><path d="M2 20.5h14" /></svg>
      <span>LORE NOOK</span>
    </RouterLink>
    <ThemeToggle />
  </header>
</template>

<style scoped>
.topbar { position: absolute; top: 0; left: 0; right: 0; z-index: 3; display: flex; justify-content: space-between; align-items: center; padding: 28px 40px; }
.mark { display: flex; align-items: center; gap: 10px; font-family: var(--h-latin); font-size: 18px; letter-spacing: 0.18em; color: var(--h-ink); text-decoration: none; }
@media (max-width: 640px) { .topbar { padding: 20px 16px; } }
</style>
