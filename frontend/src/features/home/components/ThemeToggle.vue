<script setup lang="ts">
import { Moon, Sun } from 'lucide-vue-next'
import { prefs, resolvedTheme } from '@/lib/prefs'

/** Switches the app theme, which is also day and night here. */
function toggle() {
  prefs.theme = resolvedTheme.value === 'dark' ? 'light' : 'dark'
}
</script>

<template>
  <button class="toggle" type="button" :aria-label="resolvedTheme === 'dark' ? '切换到白天' : '切换到夜晚'" @click="toggle">
    <Sun v-if="resolvedTheme === 'dark'" /><Moon v-else />
  </button>
</template>

<style scoped>
.toggle {
  width: 44px; height: 44px; display: grid; place-items: center; border-radius: 50%;
  border: 1px solid var(--h-line); background: transparent; color: var(--h-ink); cursor: pointer;
}
.toggle:hover { border-color: var(--h-ink); }
.toggle svg { width: 18px; height: 18px; stroke-width: 1.4; }
</style>
