<script setup lang="ts">
import { ChevronRight } from 'lucide-vue-next'

/** A fold for options most people never touch. Closed by default. */
withDefaults(defineProps<{ label?: string; open?: boolean }>(), { label: '高级设置', open: false })
</script>

<template>
  <details class="disclosure" :open="open">
    <summary><ChevronRight class="chev" /><span>{{ label }}</span><slot name="summary" /></summary>
    <div class="body stack"><slot /></div>
  </details>
</template>

<style scoped>
.disclosure { border-top: 1px solid var(--border); padding-top: var(--space-2); }
summary {
  display: flex; align-items: center; gap: var(--space-1-5); list-style: none; cursor: pointer; user-select: none;
  color: var(--text-muted); font-size: var(--text-sm); font-weight: 500; padding: var(--space-1) 0;
}
summary::-webkit-details-marker { display: none; }
summary:hover { color: var(--text); }
.chev { width: 15px; height: 15px; transition: transform 0.15s; }
.disclosure[open] > summary .chev { transform: rotate(90deg); }
.body { padding-top: var(--space-3); }
</style>
