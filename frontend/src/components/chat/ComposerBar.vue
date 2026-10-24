<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Send, RefreshCw, Loader2 } from 'lucide-vue-next'
import type { RoundFlow } from '@/composables/roundFlow'
import { prefs } from '@/lib/prefs'

const props = defineProps<{ flow: RoundFlow; canWrite: boolean; blockReason?: string | null }>()
const area = ref<HTMLTextAreaElement>()
const input = props.flow.input

const phase = computed(() => props.flow.phase.value)
const locked = computed(() => !props.canWrite || ['generating', 'archiving', 'checking', 'incomplete'].includes(phase.value))
const hasCandidate = computed(() => !!props.flow.candidate.value)

// Auto-grow stops at 4 lines or 25vh; dragging the handle can go up to 50vh.
// A manual height holds until the next send or a double-click on the handle.
const AUTO_LINES = 4
const AUTO_VH = 0.25
const MANUAL_VH = 0.5
const manualHeight = ref<number | null>(null)

function metrics(el: HTMLTextAreaElement) {
  const cs = getComputedStyle(el)
  const pad = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom)
  return { line: parseFloat(cs.lineHeight), pad }
}

function resize() {
  const el = area.value
  if (!el) return
  if (manualHeight.value !== null) {
    manualHeight.value = clampManual(manualHeight.value)
    el.style.height = `${manualHeight.value}px`
    return
  }
  const { line, pad } = metrics(el)
  const max = Math.min(line * AUTO_LINES + pad, window.innerHeight * AUTO_VH)
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, max)}px`
}
watch(input, () => nextTick(resize))

function clampManual(h: number) {
  const el = area.value
  const m = el ? metrics(el) : null
  const min = m ? m.line + m.pad : 0
  return Math.max(min, Math.min(h, window.innerHeight * MANUAL_VH))
}

let drag: { y: number; h: number } | null = null
function onHandleDown(e: PointerEvent) {
  if (!area.value) return
  e.preventDefault()
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  drag = { y: e.clientY, h: area.value.offsetHeight }
}
function onHandleMove(e: PointerEvent) {
  if (!drag) return
  manualHeight.value = clampManual(drag.h + drag.y - e.clientY)
  resize()
}
function onHandleUp() {
  drag = null
}
function resetHeight() {
  manualHeight.value = null
  nextTick(resize)
}

onMounted(() => window.addEventListener('resize', resize))
onBeforeUnmount(() => window.removeEventListener('resize', resize))

function onKey(e: KeyboardEvent) {
  if (e.key !== 'Enter' || e.isComposing) return
  const ctrl = e.ctrlKey || e.metaKey
  if ((prefs.sendKey === 'enter' && !e.shiftKey && !ctrl) || (prefs.sendKey === 'ctrl-enter' && ctrl)) {
    e.preventDefault()
    submit()
  }
}
function submit() {
  if (locked.value) return
  props.flow.generate()
  resetHeight()
}

// Touch devices send with the button; keyboard hints would only confuse.
const coarse = window.matchMedia('(pointer: coarse)').matches

const placeholder = computed(() => {
  if (props.blockReason) return props.blockReason
  if (phase.value === 'incomplete') return '上一回合尚未完成归档'
  if (hasCandidate.value) return '可以修改输入后重新生成'
  if (coarse) return '输入内容'
  return prefs.sendKey === 'enter' ? '输入内容，Enter 发送，Shift+Enter 换行' : '输入内容，Ctrl+Enter 发送'
})
</script>

<template>
  <div class="composer">
    <div
      class="handle" title="拖动调整高度，双击恢复自动"
      @pointerdown="onHandleDown" @pointermove="onHandleMove" @pointerup="onHandleUp" @pointercancel="onHandleUp"
      @dblclick="resetHeight"
    />
    <textarea
      ref="area" v-model="input" class="area" rows="1" :placeholder="placeholder"
      :disabled="locked" @keydown="onKey"
    />
    <button
      class="btn primary send" type="button" :disabled="locked"
      :title="hasCandidate ? '用当前输入重新生成' : '生成回复（允许空输入）'" @click="submit"
    >
      <Loader2 v-if="phase === 'generating'" class="spin" />
      <RefreshCw v-else-if="hasCandidate" />
      <Send v-else />
      <span class="send-label">{{ hasCandidate ? '重新生成' : '发送' }}</span>
    </button>
  </div>
</template>

<style scoped>
.composer {
  position: relative; display: flex; gap: 8px; align-items: flex-end; padding: 10px 12px;
  background: var(--bg-elev); border: 1px solid var(--border); border-radius: var(--radius-l); box-shadow: var(--shadow);
}
.area {
  flex: 1; border: 0; background: transparent; color: var(--text); resize: none; font: inherit;
  font-size: var(--reading-size); line-height: 1.6; max-height: 50vh; padding: 4px 2px; outline: none;
}
.handle {
  position: absolute; top: 0; left: 50%; transform: translateX(-50%);
  width: 64px; height: 12px; cursor: ns-resize; touch-action: none;
}
.handle::after {
  content: ''; position: absolute; top: 4px; left: 16px; right: 16px; height: 4px;
  border-radius: 2px; background: var(--border);
}
.handle:hover::after { background: var(--text-muted); }
.area:disabled { opacity: 0.6; }
.send { min-height: 38px; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 480px) { .send-label { display: none; } .send { width: 40px; padding: 0; } }
</style>
