<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { Send, RefreshCw, Loader2 } from 'lucide-vue-next'
import type { RoundFlow } from '@/composables/roundFlow'
import { prefs } from '@/lib/prefs'

const props = defineProps<{ flow: RoundFlow; canWrite: boolean; blockReason?: string | null }>()
const area = ref<HTMLTextAreaElement>()
const input = props.flow.input

const phase = computed(() => props.flow.phase.value)
const locked = computed(() => !props.canWrite || ['generating', 'archiving', 'checking', 'incomplete'].includes(phase.value))
const hasCandidate = computed(() => !!props.flow.candidate.value)

function resize() {
  const el = area.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, window.innerHeight * 0.4)}px`
}
watch(input, () => nextTick(resize))

function onKey(e: KeyboardEvent) {
  if (e.key !== 'Enter' || e.isComposing) return
  const ctrl = e.ctrlKey || e.metaKey
  if ((prefs.sendKey === 'enter' && !e.shiftKey && !ctrl) || (prefs.sendKey === 'ctrl-enter' && ctrl)) {
    e.preventDefault()
    submit()
  }
}
function submit() {
  if (!locked.value) props.flow.generate()
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
  display: flex; gap: 8px; align-items: flex-end; padding: 10px 12px;
  background: var(--bg-elev); border: 1px solid var(--border); border-radius: var(--radius-l); box-shadow: var(--shadow);
}
.area {
  flex: 1; border: 0; background: transparent; color: var(--text); resize: none; font: inherit;
  font-size: var(--reading-size); line-height: 1.6; max-height: 40vh; padding: 4px 2px; outline: none;
}
.area:disabled { opacity: 0.6; }
.send { min-height: 38px; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 480px) { .send-label { display: none; } .send { width: 40px; padding: 0; } }
</style>
