<script setup lang="ts">
import { toasts } from '@/composables/toast'
</script>

<template>
  <div class="toasts" aria-live="polite">
    <div v-for="t in toasts" :key="t.id" class="toast" :class="t.kind">{{ t.text }}</div>
  </div>
</template>

<style scoped>
.toasts { position: fixed; z-index: 200; top: calc(12px + env(safe-area-inset-top)); left: 50%; transform: translateX(-50%); display: flex; flex-direction: column; gap: 8px; align-items: center; pointer-events: none; width: min(92vw, 420px); }
.toast { padding: 9px 14px; border-radius: var(--radius-m); background: var(--text); color: var(--bg); box-shadow: var(--shadow-pop); font-size: 13px; white-space: pre-wrap; }
.toast.error { background: var(--danger); color: #fff; }
</style>
