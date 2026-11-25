<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, onUpdated, ref } from 'vue'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'

/**
 * A horizontal row that scrolls: edges fade where more content hides, and
 * arrow buttons page through it with a mouse. Touch users swipe.
 */
const track = ref<HTMLElement>()
const canLeft = ref(false)
const canRight = ref(false)

function update() {
  const el = track.value
  if (!el) return
  canLeft.value = el.scrollLeft > 1
  canRight.value = el.scrollLeft + el.clientWidth < el.scrollWidth - 1
}
function page(dir: 1 | -1) {
  const el = track.value
  if (el) el.scrollBy({ left: dir * el.clientWidth * 0.85, behavior: 'smooth' })
}

let observer: ResizeObserver | null = null
onMounted(() => {
  update()
  observer = new ResizeObserver(update)
  observer.observe(track.value!)
})
// Items arriving later change the scroll width without resizing the track.
onUpdated(() => nextTick(update))
onBeforeUnmount(() => observer?.disconnect())
</script>

<template>
  <div class="scroll-row" :class="{ 'fade-left': canLeft, 'fade-right': canRight }">
    <div ref="track" class="track" @scroll.passive="update"><slot /></div>
    <button v-if="canLeft" class="arrow left" type="button" aria-label="向左" @click="page(-1)"><ChevronLeft /></button>
    <button v-if="canRight" class="arrow right" type="button" aria-label="向右" @click="page(1)"><ChevronRight /></button>
  </div>
</template>

<style scoped>
.scroll-row { position: relative; }
.track {
  display: flex; gap: var(--space-3); overflow-x: auto; scroll-snap-type: x proximity; padding-bottom: var(--space-2);
  scrollbar-width: thin;
}
.fade-right .track { mask-image: linear-gradient(to right, #000 calc(100% - 48px), transparent); }
.fade-left .track { mask-image: linear-gradient(to left, #000 calc(100% - 48px), transparent); }
.fade-left.fade-right .track { mask-image: linear-gradient(to right, transparent, #000 48px, #000 calc(100% - 48px), transparent); }
.arrow {
  position: absolute; top: calc(50% - var(--space-1)); transform: translateY(-50%); z-index: 2;
  display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px; padding: 0;
  border: 1px solid var(--border); border-radius: 50%; background: var(--bg-elev); color: var(--text);
  box-shadow: var(--shadow); cursor: pointer; opacity: 0; transition: opacity 0.15s;
}
.arrow svg { width: 18px; height: 18px; }
.arrow.left { left: -6px; }
.arrow.right { right: -6px; }
.scroll-row:hover .arrow, .arrow:focus-visible { opacity: 1; }
@media (hover: none) { .arrow { display: none; } }
</style>
