<script setup lang="ts">
import type { Item } from '@/lib/stateDisplay'

defineOptions({ name: 'StateItems' })
defineProps<{ items: Item[] }>()
</script>

<template>
  <dl class="items">
    <template v-for="it in items" :key="it.key">
      <details v-if="it.kind === 'group'" class="group">
        <summary :title="it.hint">{{ it.label }}<span class="count">{{ it.items.length }}</span></summary>
        <StateItems :items="it.items" />
      </details>
      <div v-else class="item" :class="it.kind">
        <dt :title="it.hint">{{ it.label }}</dt>
        <dd v-if="it.kind === 'text'">{{ it.value }}</dd>
        <dd v-else-if="it.kind === 'dot'"><span class="dot" :class="{ on: it.value }" />{{ it.value ? '是' : '否' }}</dd>
        <dd v-else-if="it.kind === 'tags'" class="tags"><span v-for="(t, i) in it.value" :key="i" class="tag">{{ t }}</span></dd>
        <dd v-else-if="it.kind === 'bar'" class="bar-cell">
          <span class="num">{{ it.value }}<span class="max">/{{ it.max }}</span></span>
          <span class="track"><span class="fill" :style="{ width: `${it.ratio * 100}%` }" /></span>
        </dd>
      </div>
    </template>
  </dl>
</template>

<style scoped>
.items { margin: 0; display: flex; flex-direction: column; }
.item { display: flex; gap: var(--space-3); padding: var(--space-1-5) 0; align-items: baseline; }
.item + .item, .group + .item, .item + .group, .group + .group { border-top: 1px solid var(--border); }
dt { flex: 0 0 auto; max-width: 40%; color: var(--text-muted); font-size: var(--text-sm); }
dd { margin: 0; flex: 1; min-width: 0; text-align: right; font-size: var(--text-sm); overflow-wrap: anywhere; }
.bar { flex-wrap: wrap; }
.bar-cell { display: flex; flex-direction: column; align-items: flex-end; gap: var(--space-1); }
.num { font-variant-numeric: tabular-nums; font-weight: 500; }
.max { color: var(--text-faint); font-weight: 400; }
.track { width: 100%; height: 4px; border-radius: var(--radius-pill); background: var(--bg-hover); overflow: hidden; }
.fill { display: block; height: 100%; border-radius: inherit; background: var(--accent); }
.tags { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: var(--space-1); }
.tag { padding: 0 var(--space-2); border-radius: var(--radius-pill); background: var(--bg-sunken); border: 1px solid var(--border); font-size: var(--text-xs); line-height: 1.7; }
.dot { display: inline-block; width: 7px; height: 7px; margin-right: var(--space-1-5); border-radius: 50%; background: var(--border-strong); vertical-align: middle; }
.dot.on { background: var(--accent); }
.group summary {
  display: flex; align-items: center; gap: var(--space-1-5); padding: var(--space-1-5) 0; cursor: pointer;
  color: var(--text-muted); font-size: var(--text-sm); list-style: none;
}
.group summary::-webkit-details-marker { display: none; }
.group summary::before { content: '›'; display: inline-block; width: 10px; transition: transform 0.15s; }
.group[open] summary::before { transform: rotate(90deg); }
.count { margin-left: auto; color: var(--text-faint); font-size: var(--text-xs); }
.group > .items { padding: 0 0 var(--space-1-5) var(--space-3); border-left: 1px solid var(--border); margin-left: var(--space-1); }
</style>
