<script setup lang="ts">
import { computed } from 'vue'
import { KINDS, type LibraryKind } from './kinds'

/** The library's front page: large tiles for the story's people, small ones for how the AI works. */
const props = defineProps<{ counts: Partial<Record<LibraryKind, number>> }>()
const profiles = computed(() => KINDS.filter((k) => k.group === 'profiles'))
const settings = computed(() => KINDS.filter((k) => k.group === 'settings'))
const count = (id: LibraryKind) => props.counts[id]
</script>

<template>
  <div class="hub">
    <div class="big">
      <RouterLink v-for="k in profiles" :key="k.id" :to="`/library/${k.id}`" class="tile" :class="k.id">
        <component :is="k.icon" class="tile-icon" />
        <div>
          <div class="tile-label">{{ k.label }}</div>
          <div class="tile-meta">{{ k.blurb }}<template v-if="count(k.id) !== undefined"> · {{ count(k.id) }}</template></div>
        </div>
      </RouterLink>
    </div>
    <h2 class="group">AI 设置</h2>
    <div class="small">
      <RouterLink v-for="k in settings" :key="k.id" :to="`/library/${k.id}`" class="chip">
        <component :is="k.icon" class="chip-icon" />
        <div class="grow">
          <div class="chip-label">{{ k.label }}</div>
          <div class="chip-meta">{{ k.blurb }}</div>
        </div>
        <span v-if="count(k.id) !== undefined" class="chip-count">{{ count(k.id) }}</span>
      </RouterLink>
    </div>
  </div>
</template>

<style scoped>
.hub { display: flex; flex-direction: column; gap: var(--space-4); }
.big { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: var(--space-4); }
.tile {
  position: relative; display: flex; flex-direction: column; justify-content: space-between; min-height: 220px;
  padding: var(--space-6); border-radius: var(--radius-xl); overflow: hidden; text-decoration: none; color: var(--text);
  background: var(--accent-soft); transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.tile.identities { background: var(--bg-sunken); }
.tile:hover { transform: translateY(-3px); box-shadow: var(--shadow-pop); }
.tile-icon { width: 30px; height: 30px; color: var(--accent); stroke-width: 1.5; }
.tile-label { font-family: var(--font-reading); font-size: var(--text-display); font-weight: 600; letter-spacing: 0.06em; line-height: 1.1; }
.tile-meta { margin-top: var(--space-2); color: var(--text-muted); font-size: var(--text-sm); }
.group { margin-top: var(--space-4); font-size: var(--text-sm); font-weight: 600; color: var(--text-muted); letter-spacing: 0.08em; }
.small { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: var(--space-3); }
.chip {
  display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3) var(--space-4); border-radius: var(--radius-l);
  border: 1px solid var(--border); background: var(--bg-elev); text-decoration: none; color: var(--text);
}
.chip:hover { border-color: var(--border-strong); background: var(--bg-hover); }
.chip-icon { width: 20px; height: 20px; color: var(--text-muted); flex-shrink: 0; }
.chip-label { font-weight: 600; }
.chip-meta { font-size: var(--text-xs); color: var(--text-faint); }
.chip-count { font-size: var(--text-sm); color: var(--text-muted); font-variant-numeric: tabular-nums; }
@media (max-width: 899px) {
  .tile { min-height: 150px; padding: var(--space-5); }
  .tile-label { font-size: var(--text-3xl); }
}
</style>
