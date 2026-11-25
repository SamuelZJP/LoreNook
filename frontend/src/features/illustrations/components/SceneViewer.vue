<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ChevronLeft, ChevronRight, X, Download, FileText, RefreshCw } from 'lucide-vue-next'
import type { RoundRead } from '@/api/endpoints'
import { illustrationApi, type Illustration } from '../api'
import { sceneLine } from '@/lib/format'
import { summaryBody } from '../lib'

/** Full-screen view of the chat's illustrations in round order. */
const props = defineProps<{ chatId: string; items: { round: RoundRead; illustration: Illustration }[]; startId: string }>()
const emit = defineEmits<{ close: []; prompt: [roundId: string]; regenerate: [roundId: string] }>()

const index = ref(Math.max(0, props.items.findIndex((i) => i.illustration.id === props.startId)))
watch(() => props.items.length, (n) => { if (index.value >= n) index.value = Math.max(0, n - 1) })
const current = computed(() => props.items[index.value])
const text = computed(() => ({ caption: sceneLine(current.value?.round.scene), body: summaryBody(current.value?.round.summary) }))
const src = (i: Illustration) => illustrationApi.image(props.chatId, i.id)

function go(step: number) {
  const n = props.items.length
  if (n) index.value = (index.value + step + n) % n
}
function onKey(e: KeyboardEvent) {
  // A dialog opened on top (the prompt) handles its own keys.
  if (document.querySelector('.dialog[aria-modal="true"]')) return
  if (e.key === 'Escape') emit('close')
  else if (e.key === 'ArrowLeft') go(-1)
  else if (e.key === 'ArrowRight') go(1)
}
// Swipe on touch screens.
let touchX: number | null = null
function touchEnd(e: TouchEvent) {
  if (touchX === null) return
  const dx = e.changedTouches[0].clientX - touchX
  touchX = null
  if (Math.abs(dx) > 50) go(dx < 0 ? 1 : -1)
}
const closeButton = ref<HTMLButtonElement>()
onMounted(() => {
  document.addEventListener('keydown', onKey)
  closeButton.value?.focus({ preventScroll: true })
})
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <div class="viewer" role="dialog" aria-modal="true" aria-label="插图">
      <header>
        <span class="pos">第 {{ current?.round.round_no }} 回合 · {{ index + 1 }} / {{ items.length }}</span>
        <span class="spacer" />
        <button v-if="current?.illustration.prompt" class="vbtn" type="button" @click="emit('prompt', current.round.id)"><FileText /><span class="label-text">提示词</span></button>
        <button class="vbtn" type="button" @click="current && emit('regenerate', current.round.id)"><RefreshCw /><span class="label-text">重新生成</span></button>
        <a v-if="current" class="vbtn icon" :href="src(current.illustration)" :download="`第${current.round.round_no}回合`" aria-label="下载"><Download /></a>
        <button ref="closeButton" class="vbtn icon" type="button" aria-label="关闭" @click="emit('close')"><X /></button>
      </header>

      <div class="stage" @touchstart.passive="touchX = $event.touches[0].clientX" @touchend="touchEnd">
        <button v-if="items.length > 1" class="nav" type="button" aria-label="上一张" @click="go(-1)"><ChevronLeft /></button>
        <img v-if="current" :key="current.illustration.id" :src="src(current.illustration)" alt="" class="main" />
        <button v-if="items.length > 1" class="nav" type="button" aria-label="下一张" @click="go(1)"><ChevronRight /></button>
      </div>

      <div v-if="current" class="caption">
        <div v-if="text.caption" class="when">{{ text.caption }}</div>
        <p v-if="text.body" class="summary">{{ text.body }}</p>
      </div>

      <div v-if="items.length > 1" class="strip">
        <button
          v-for="(item, i) in items" :key="item.illustration.id" type="button" class="thumb" :class="{ on: i === index }"
          :aria-label="`第 ${item.round.round_no} 回合插图`" :aria-current="i === index" @click="index = i"
        >
          <img :src="src(item.illustration)" alt="" loading="lazy" />
        </button>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.viewer {
  position: fixed; inset: 0; z-index: 90; display: flex; flex-direction: column;
  background: #0f0e12; color: #e4dccd; padding: env(safe-area-inset-top) 0 env(safe-area-inset-bottom);
}
header { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-3) var(--space-4); flex-wrap: wrap; }
.pos { color: #978b7c; font-variant-numeric: tabular-nums; font-size: var(--text-sm); }
.vbtn {
  height: 36px; padding: 0 var(--space-3); border-radius: var(--radius-s); border: 1px solid #3a343a; background: transparent; color: inherit;
  font: inherit; font-size: var(--text-sm); display: inline-flex; align-items: center; gap: var(--space-1-5); cursor: pointer; text-decoration: none;
}
.vbtn.icon { width: 36px; padding: 0; justify-content: center; }
.vbtn:hover { background: rgb(255 255 255 / 6%); }
.vbtn svg { width: 16px; height: 16px; }
.stage { flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; gap: var(--space-4); padding: 0 var(--space-4); }
.main { max-width: calc(100% - 136px); max-height: 100%; object-fit: contain; border-radius: var(--radius-xs); box-shadow: 0 20px 60px rgb(0 0 0 / 60%), 0 0 0 1px rgb(228 220 205 / 8%); }
.nav {
  width: 44px; height: 44px; flex-shrink: 0; border-radius: 50%; border: 1px solid #3a343a; background: rgb(255 255 255 / 4%);
  color: inherit; display: flex; align-items: center; justify-content: center; cursor: pointer;
}
.nav svg { width: 20px; height: 20px; }
.caption { display: flex; flex-direction: column; align-items: center; gap: var(--space-1-5); padding: var(--space-4) var(--space-6) 0; text-align: center; }
.when { font-family: var(--font-reading); font-size: var(--text-sm); letter-spacing: 0.14em; color: #978b7c; }
.summary { margin: 0; max-width: 680px; font-family: var(--font-reading); font-size: var(--text-lg); line-height: 1.85; color: #c2b6a4; max-height: 5.6em; overflow-y: auto; }
.strip { display: flex; justify-content: center; gap: var(--space-3); padding: var(--space-4) var(--space-4) var(--space-5); overflow-x: auto; }
.thumb { flex-shrink: 0; width: 84px; height: 56px; padding: 0; border-radius: var(--radius-xs); overflow: hidden; border: 2px solid transparent; background: #1d1b20; cursor: pointer; opacity: 0.55; }
.thumb.on { border-color: #e4dccd; opacity: 1; }
.thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
@media (max-width: 640px) {
  .label-text { display: none; }
  .vbtn { width: 36px; padding: 0; justify-content: center; }
  .nav { display: none; }
  .main { max-width: 100%; }
  .stage { padding: 0; }
  .strip { justify-content: flex-start; }
}
</style>
