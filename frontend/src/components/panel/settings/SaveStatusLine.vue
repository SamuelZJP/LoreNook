<script setup lang="ts">
import { AlertCircle, Check, Loader2 } from 'lucide-vue-next'
import type { SaveTracker } from '@/composables/autosave'

/** One quiet line saying whether edits have reached the server; nothing until something is saved. */
defineProps<{ tracker: SaveTracker }>()
const errorMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))
</script>

<template>
  <div v-if="tracker.status.value !== 'idle'" class="save-line" :class="tracker.status.value" role="status">
    <template v-if="tracker.status.value === 'saving'"><Loader2 class="spin" /> 保存中…</template>
    <template v-else-if="tracker.status.value === 'saved'"><Check /> 已保存</template>
    <template v-else-if="tracker.status.value === 'error'">
      <AlertCircle /> <span class="grow">保存失败：{{ errorMessage(tracker.error.value) }}</span>
      <button class="btn small" type="button" @click="tracker.retry()">重试</button>
    </template>
  </div>
</template>

<style scoped>
.save-line { display: flex; align-items: center; gap: var(--space-1-5); min-height: 30px; font-size: var(--text-xs); color: var(--text-faint); }
.save-line svg { width: 14px; height: 14px; flex-shrink: 0; }
.save-line.saved { color: var(--ok); }
.save-line.error { color: var(--danger); }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
