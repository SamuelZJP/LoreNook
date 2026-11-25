<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { api } from '@/api/endpoints'
import { planStateChanges, type Change } from '@/lib/stateChanges'

/** "最近变化": what the last few rounds changed in the state. Hidden when nothing did. */
const props = defineProps<{ chatId: string; schema: Record<string, any> | null; stamp: number }>()

// `stamp` moves whenever the latest state is refetched or saved, so the history follows it.
const history = useQuery({
  queryKey: computed(() => ['state-history', props.chatId, props.stamp]),
  queryFn: () => api.stateHistory(props.chatId),
})
const rounds = computed(() => planStateChanges(history.data.value ?? [], props.schema))

function text(c: Change): string {
  switch (c.kind) {
    case 'number': return c.from === null ? `${c.to}` : `${c.from} → ${c.to}`
    case 'text': return `→ ${c.to}`
    case 'flag': return c.to ? '→ 是' : '→ 否'
    case 'cleared': return '已清空'
    case 'list': return [...c.added.map((v) => `+${v}`), ...c.removed.map((v) => `−${v}`)].join('  ')
  }
}
const tone = (c: Change) => (c.kind === 'number' && c.from !== null ? (c.to > c.from ? 'up' : 'down') : '')
</script>

<template>
  <section v-if="rounds.length" class="changes">
    <h4>最近变化</h4>
    <ol>
      <template v-for="(r, i) in rounds" :key="r.roundNo">
        <li v-for="(c, j) in r.changes" :key="`${r.roundNo}-${j}`" :class="{ newest: i === 0 }">
          <span class="what"><span class="label">{{ c.label }}</span> <span class="value" :class="tone(c)">{{ text(c) }}</span></span>
          <span v-if="j === 0" class="round">#{{ r.roundNo }}</span>
        </li>
      </template>
    </ol>
  </section>
</template>

<style scoped>
.changes { padding: 0 var(--space-1); }
h4 { margin: 0 0 var(--space-2); font-size: var(--text-md); font-weight: 600; }
ol { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: var(--space-2); }
li { display: grid; grid-template-columns: 8px minmax(0, 1fr) auto; gap: var(--space-2); align-items: baseline; font-size: var(--text-sm); }
li::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: var(--border-strong); transform: translateY(-1px); }
li.newest::before { background: var(--accent); }
.what { min-width: 0; overflow-wrap: anywhere; color: var(--text-muted); }
.label { color: var(--text); font-weight: 500; }
.value { font-variant-numeric: tabular-nums; }
.value.up { color: var(--ok); }
.value.down { color: var(--danger); }
.round { color: var(--text-faint); font-size: var(--text-xs); font-variant-numeric: tabular-nums; }
</style>
