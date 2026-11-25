<script setup lang="ts">
import { computed } from 'vue'
import type { RoundRead } from '@/api/endpoints'
import { sceneLine } from '@/lib/format'

/** When and where the round ended. Placed before the body, after any illustration. Opens the state panel. */
const props = defineProps<{ round: RoundRead }>()
const emit = defineEmits<{ open: [] }>()
const line = computed(() => sceneLine(props.round.scene))
</script>

<template>
  <p v-if="line" class="scene">
    <span class="rule" /><button type="button" class="line" title="查看状态" @click="emit('open')">{{ line }}</button><span class="rule" />
  </p>
</template>

<style scoped>
.scene {
  display: flex; align-items: center; gap: var(--space-3); margin: 0 0 var(--space-3); font-family: var(--font-reading); font-size: var(--text-xs);
  letter-spacing: 0.12em; color: var(--page-muted); text-align: center; overflow-wrap: anywhere;
}
.line {
  border: 0; background: none; padding: var(--space-0-5) var(--space-2); border-radius: var(--radius-pill);
  font: inherit; letter-spacing: inherit; color: inherit; cursor: pointer; transition: background 0.12s, color 0.12s;
}
.line:hover { background: var(--page-rule); color: var(--page-em); }
.rule { flex: 1; height: 1px; background: var(--page-border); min-width: 16px; }
</style>
