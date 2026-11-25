<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, onUpdated, ref } from 'vue'

/**
 * A horizontal row that scrolls: edges fade where more content hides, and the
 * mouse wheel scrolls sideways while the pointer is over it. At either end the
 * wheel goes back to scrolling the page. Touch users swipe.
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

function wheel(e: WheelEvent) {
  const el = track.value
  // Trackpads already scroll sideways; only turn vertical wheel motion.
  if (!el || Math.abs(e.deltaX) >= Math.abs(e.deltaY)) return
  if ((e.deltaY > 0 && !canRight.value) || (e.deltaY < 0 && !canLeft.value)) return
  e.preventDefault()
  el.scrollLeft += e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY
}

let observer: ResizeObserver | null = null
onMounted(() => {
  update()
  observer = new ResizeObserver(update)
  observer.observe(track.value!)
  // Not passive: the wheel's default page scroll is cancelled while the row can still move.
  track.value!.addEventListener('wheel', wheel, { passive: false })
})
// Items arriving later change the scroll width without resizing the track.
onUpdated(() => nextTick(update))
onBeforeUnmount(() => {
  observer?.disconnect()
  track.value?.removeEventListener('wheel', wheel)
})
</script>

<template>
  <div class="scroll-row" :class="{ 'fade-left': canLeft, 'fade-right': canRight }">
    <div ref="track" class="track" @scroll.passive="update"><slot /></div>
  </div>
</template>

<style scoped>
.track {
  /* Room for focus rings and selected outlines, which the scroll box would clip. */
  display: flex; gap: var(--space-3); overflow-x: auto; padding: 2px 2px var(--space-2);
  scrollbar-width: thin;
}
.fade-right .track { mask-image: linear-gradient(to right, #000 calc(100% - 48px), transparent); }
.fade-left .track { mask-image: linear-gradient(to left, #000 calc(100% - 48px), transparent); }
.fade-left.fade-right .track { mask-image: linear-gradient(to right, transparent, #000 48px, #000 calc(100% - 48px), transparent); }
</style>
