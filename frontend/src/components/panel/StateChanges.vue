<script setup lang="ts">
import type { Change, LatestChanges } from '@/lib/stateChanges'

/** What the latest round changed, grouped like the state it replaces in the panel. */
defineProps<{ changes: LatestChanges | null; loading: boolean }>()

function value(c: Change): string {
  switch (c.kind) {
    case 'number': return c.from === null ? `${c.to}` : `${c.from} → ${c.to}`
    case 'text': return `→ ${c.to}`
    case 'flag': return c.to ? '→ 是' : '→ 否'
    case 'cleared': return '已清空'
    case 'list': return [...c.added.map((v) => `+${v}`), ...c.removed.map((v) => `−${v}`)].join('  ')
  }
}
const tone = (c: Change) => (c.kind === 'number' && c.from !== null && c.to !== c.from ? (c.to > c.from ? 'up' : 'down') : '')
</script>

<template>
  <p v-if="loading && !changes" class="note">读取中…</p>
  <p v-else-if="!changes" class="note">还没有回合</p>
  <p v-else-if="!changes.groups.length" class="note">这一回合没有变化</p>
  <template v-else>
    <section v-for="g in changes.groups" :key="g.key" class="group">
      <h4>{{ g.title }}</h4>
      <dl>
        <div v-for="(c, i) in g.changes" :key="i" class="item">
          <dt>{{ c.label }}</dt>
          <dd :class="tone(c)">{{ value(c) }}</dd>
        </div>
      </dl>
    </section>
  </template>
</template>

<style scoped>
.note { padding: var(--space-4) var(--space-1); color: var(--text-faint); font-size: var(--text-sm); text-align: center; }
.group { padding: 0 var(--space-1); }
h4 { margin: 0 0 var(--space-1); font-size: var(--text-md); font-weight: 600; }
dl { margin: 0; display: flex; flex-direction: column; }
/* Rows match StateItems so switching views keeps the same rhythm. */
.item { display: flex; gap: var(--space-3); padding: var(--space-2) 0; align-items: baseline; }
.item + .item { border-top: 1px solid var(--border); }
dt { flex: 0 1 auto; max-width: 50%; color: var(--text-muted); font-size: var(--text-sm); overflow-wrap: anywhere; }
dd { margin: 0; flex: 1; min-width: 0; text-align: right; font-size: var(--text-sm); font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
dd.up { color: var(--ok); }
dd.down { color: var(--danger); }
</style>
