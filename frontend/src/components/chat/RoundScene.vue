<script setup lang="ts">
import { computed } from 'vue'
import type { RoundRead } from '@/api/endpoints'
import { sceneLine } from '@/lib/format'

/** When and where the round ended. Placed before the body, after any illustration. */
const props = defineProps<{ round: RoundRead }>()
const line = computed(() => sceneLine(props.round.scene))
</script>

<template>
  <p v-if="line" class="scene"><span class="rule" /><span>{{ line }}</span><span class="rule" /></p>
</template>

<style scoped>
.scene {
  display: flex; align-items: center; gap: var(--space-3); margin: 0 0 var(--space-3); font-family: var(--font-reading); font-size: var(--text-xs);
  letter-spacing: 0.12em; color: var(--page-muted); text-align: center; overflow-wrap: anywhere;
}
.rule { flex: 1; height: 1px; background: var(--page-border); min-width: 16px; }
</style>
