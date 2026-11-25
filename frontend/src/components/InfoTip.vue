<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref } from 'vue'
import { Info } from 'lucide-vue-next'

/**
 * A small ⓘ that reveals an explanation on hover or tap. Explanations live here
 * instead of as always-visible hint text. The bubble is teleported so panels
 * with overflow don't clip it.
 */
withDefaults(defineProps<{ label?: string }>(), { label: '说明' })

const open = ref(false)
const pinned = ref(false)
const anchor = ref<HTMLElement | null>(null)
const pos = ref({ top: 0, left: 0 })
const WIDTH = 260

async function show() {
  const r = anchor.value?.getBoundingClientRect()
  if (!r) return
  const left = Math.min(Math.max(8, r.left + r.width / 2 - WIDTH / 2), window.innerWidth - WIDTH - 8)
  pos.value = { top: r.bottom + 6, left }
  open.value = true
  await nextTick()
}
function hide() {
  if (!pinned.value) open.value = false
}
function toggle() {
  pinned.value = !pinned.value
  if (pinned.value) {
    show()
    document.addEventListener('pointerdown', outside, true)
  } else {
    open.value = false
    document.removeEventListener('pointerdown', outside, true)
  }
}
function outside(e: Event) {
  if (anchor.value?.contains(e.target as Node)) return
  pinned.value = false
  open.value = false
  document.removeEventListener('pointerdown', outside, true)
}
onBeforeUnmount(() => document.removeEventListener('pointerdown', outside, true))
</script>

<template>
  <button
    ref="anchor" class="info-tip" type="button" :aria-label="label" :aria-expanded="open"
    @mouseenter="show" @mouseleave="hide" @focus="show" @blur="hide" @click.stop="toggle"
  >
    <Info />
  </button>
  <Teleport to="body">
    <div v-if="open" class="info-bubble" role="tooltip" :style="{ top: `${pos.top}px`, left: `${pos.left}px`, width: `${WIDTH}px` }">
      <slot />
    </div>
  </Teleport>
</template>

<style scoped>
.info-tip {
  display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; padding: 0; flex: none;
  border: 0; border-radius: var(--radius-pill); background: none; color: var(--text-faint); cursor: help; vertical-align: middle;
}
.info-tip:hover, .info-tip[aria-expanded='true'] { color: var(--text-muted); background: var(--bg-hover); }
.info-tip svg { width: 15px; height: 15px; }
</style>

<style>
.info-bubble {
  position: fixed; z-index: 200; padding: var(--space-2) var(--space-3); border-radius: var(--radius-m);
  background: var(--bg-elev); border: 1px solid var(--border); box-shadow: var(--shadow-pop);
  font-size: var(--text-sm); line-height: 1.55; color: var(--text-muted); font-weight: 400;
}
.info-bubble code { font-size: var(--text-xs); }
</style>
