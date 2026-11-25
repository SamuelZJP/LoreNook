<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import ModalDialog from './ModalDialog.vue'
import { centred, clampPlacement, rezoom, sourceRect, type Placement, type Size } from '@/lib/crop'

/** Crop an image file to a fixed aspect by dragging and zooming; emits the cropped JPEG. */
const props = withDefaults(defineProps<{ file: File; aspect?: number; output?: number; title?: string }>(), {
  aspect: 3 / 4, output: 1200, title: '调整立绘',
})
const emit = defineEmits<{ done: [Blob]; close: [] }>()

const FRAME_H = 360
const frame = computed<Size>(() => ({ w: Math.round(FRAME_H * props.aspect), h: FRAME_H }))
const src = URL.createObjectURL(props.file)
onBeforeUnmount(() => URL.revokeObjectURL(src))

const img = ref<HTMLImageElement>()
const natural = ref<Size | null>(null)
const zoom = ref(1)
const place = ref<Placement>({ x: 0, y: 0, scale: 1 })

function loaded() {
  const el = img.value!
  natural.value = { w: el.naturalWidth, h: el.naturalHeight }
  place.value = centred(natural.value, frame.value, 1)
}
function setZoom(z: number) {
  zoom.value = z
  if (natural.value) place.value = rezoom(natural.value, frame.value, place.value, z)
}

let drag: { px: number; py: number; x: number; y: number } | null = null
function down(e: PointerEvent) {
  (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  drag = { px: e.clientX, py: e.clientY, x: place.value.x, y: place.value.y }
}
function move(e: PointerEvent) {
  if (!drag || !natural.value) return
  place.value = clampPlacement(natural.value, frame.value, zoom.value, drag.x + e.clientX - drag.px, drag.y + e.clientY - drag.py)
}
function up() { drag = null }
function wheel(e: WheelEvent) {
  setZoom(Math.min(4, Math.max(1, zoom.value * (e.deltaY < 0 ? 1.08 : 1 / 1.08))))
}

const busy = ref(false)
function confirm() {
  if (!natural.value || !img.value) return
  busy.value = true
  const out = { w: Math.round(props.output * props.aspect), h: props.output }
  const r = sourceRect(frame.value, place.value)
  const canvas = document.createElement('canvas')
  canvas.width = out.w
  canvas.height = out.h
  const ctx = canvas.getContext('2d')!
  ctx.imageSmoothingQuality = 'high'
  ctx.drawImage(img.value, r.sx, r.sy, r.sw, r.sh, 0, 0, out.w, out.h)
  canvas.toBlob((blob) => {
    busy.value = false
    if (blob) emit('done', blob)
  }, 'image/jpeg', 0.9)
}
</script>

<template>
  <ModalDialog :title="title" width="440px" @close="emit('close')">
    <div class="crop stack">
      <div
        class="frame" :style="{ width: `${frame.w}px`, height: `${frame.h}px` }"
        @pointerdown="down" @pointermove="move" @pointerup="up" @pointercancel="up" @wheel.prevent="wheel"
      >
        <img
          ref="img" :src="src" alt="" draggable="false" @load="loaded"
          :style="natural ? { width: `${natural.w * place.scale}px`, height: `${natural.h * place.scale}px`, transform: `translate(${place.x}px, ${place.y}px)` } : { opacity: 0 }"
        />
      </div>
      <input class="zoom" type="range" min="1" max="4" step="0.01" :value="zoom" aria-label="缩放" @input="setZoom(Number(($event.target as HTMLInputElement).value))" />
    </div>
    <template #footer>
      <button class="btn" type="button" @click="emit('close')">取消</button>
      <button class="btn primary" type="button" :disabled="!natural || busy" @click="confirm">使用</button>
    </template>
  </ModalDialog>
</template>

<style scoped>
.crop { align-items: center; }
.frame {
  position: relative; overflow: hidden; border-radius: var(--radius-l); background: var(--bg-sunken);
  cursor: grab; touch-action: none; user-select: none; box-shadow: inset 0 0 0 1px var(--border);
}
.frame:active { cursor: grabbing; }
.frame img { position: absolute; top: 0; left: 0; max-width: none; pointer-events: none; }
.zoom { width: 100%; max-width: 270px; accent-color: var(--accent); }
</style>
