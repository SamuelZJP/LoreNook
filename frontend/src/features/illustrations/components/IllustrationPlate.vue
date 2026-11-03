<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Maximize2, RefreshCw, FileText, EyeOff, Image as ImageIcon, AlertTriangle, PenTool, Sparkles, Users, MoreHorizontal, X } from 'lucide-vue-next'
import { illustrationApi, type Illustration, type IllustrationProgress } from '../api'

/** One round's illustration, framed as a book plate at the head of its reading page. */
const props = defineProps<{ chatId: string; illustration: Illustration; progress?: IllustrationProgress; busy?: boolean }>()
const emit = defineEmits<{ open: []; regenerate: []; focus: []; prompt: []; hide: [hidden: boolean] }>()

const it = computed(() => props.illustration)
const frameStyle = computed(() => ({ aspectRatio: `${it.value.width} / ${it.value.height}`, '--plate-ratio': it.value.width / it.value.height }))
const src = computed(() => illustrationApi.image(props.chatId, it.value.id))
const loaded = ref(false)
watch(src, () => { loaded.value = false })

// The stream is ahead of the list by up to one refetch.
const status = computed(() => props.progress?.status ?? it.value.status)
const percent = computed(() => {
  const { value, max } = props.progress ?? {}
  return value != null && max ? Math.min(100, Math.round((value / max) * 100)) : null
})
const detail = computed(() => {
  const p = props.progress
  if (status.value !== 'rendering' || !p) return ''
  if (p.queued) return '在 ComfyUI 中排队'
  const count = p.value != null && p.max ? `${p.value} / ${p.max}` : ''
  return [p.node, count].filter(Boolean).join(' · ')
})

// Touch screens have no hover, so the buttons fold into one toggle that keeps the image clear.
const actionsOpen = ref(false)
const actionsEl = ref<HTMLElement>()
function closeOutside(e: PointerEvent) {
  if (!actionsEl.value?.contains(e.target as Node)) actionsOpen.value = false
}
watch(actionsOpen, (open) => {
  if (open) document.addEventListener('pointerdown', closeOutside)
  else document.removeEventListener('pointerdown', closeOutside)
})
onBeforeUnmount(() => document.removeEventListener('pointerdown', closeOutside))

const steps = computed(() => {
  const s = status.value
  return [
    { label: '整理上下文', done: s !== 'pending', active: s === 'pending' },
    { label: '渲染', done: false, active: s === 'rendering' },
  ]
})
</script>

<template>
  <!-- Hidden: a thin line that can bring it back -->
  <button v-if="it.hidden" class="hidden-strip" type="button" @click="emit('hide', false)">
    <span class="rule" /><ImageIcon /><span>插图已隐藏 · 点此显示</span><span class="rule" />
  </button>

  <!-- Failed: one quiet line, never a large error box -->
  <div v-else-if="it.status === 'failed'" class="failed">
    <AlertTriangle class="warn-ic" />
    <span class="grow">插图未能生成 · <span class="muted-ink">{{ it.error }}</span></span>
    <button class="btn small paper" type="button" :disabled="busy" @click="emit('regenerate')">重试</button>
    <button class="btn ghost small paper-ghost" type="button" :disabled="busy" @click="emit('focus')">换人物</button>
    <button v-if="it.prompt" class="btn ghost small paper-ghost" type="button" @click="emit('prompt')">提示词</button>
    <button class="btn ghost small paper-ghost" type="button" @click="emit('hide', true)">隐藏</button>
  </div>

  <figure v-else class="plate">
    <div class="frame">
      <div class="image" :style="frameStyle">
        <template v-if="it.status === 'ready'">
          <button class="open" type="button" aria-label="全屏查看插图" @click="emit('open')">
            <img :src="src" :class="{ loaded }" alt="" loading="lazy" decoding="async" @load="loaded = true" />
          </button>
          <span class="vignette" aria-hidden="true" />
        </template>
        <div v-else class="working" role="status">
          <PenTool v-if="status === 'rendering'" class="pulse" />
          <Sparkles v-else class="pulse" />
          <span class="working-title">{{ status === 'rendering' ? '正在绘制插图' : '正在准备插图' }}</span>
          <span class="steps">
            <span v-for="s in steps" :key="s.label" :class="{ active: s.active }">{{ s.label }}{{ s.done ? ' ✓' : '' }}</span>
          </span>
          <span v-if="detail" class="detail">{{ detail }}</span>
          <span v-if="percent !== null" class="meter" role="progressbar" :aria-valuenow="percent" aria-valuemin="0" aria-valuemax="100" aria-label="绘制进度"><span :style="{ width: `${percent}%` }" /></span>
          <span v-else class="bar" aria-hidden="true" />
        </div>
      </div>
      <div v-if="it.status === 'ready'" ref="actionsEl" class="actions" :class="{ open: actionsOpen }">
        <button class="toggle" type="button" :aria-label="actionsOpen ? '收起按钮' : '展开按钮'" :aria-expanded="actionsOpen" @click="actionsOpen = !actionsOpen">
          <X v-if="actionsOpen" /><MoreHorizontal v-else />
        </button>
        <button type="button" aria-label="全屏查看" title="全屏查看" @click="emit('open')"><Maximize2 /></button>
        <button type="button" aria-label="重新生成" title="重新生成" :disabled="busy" @click="emit('regenerate')"><RefreshCw /></button>
        <button type="button" aria-label="换人物重新生成" title="换人物重新生成" :disabled="busy" @click="emit('focus')"><Users /></button>
        <button type="button" aria-label="查看提示词" title="查看提示词" @click="emit('prompt')"><FileText /></button>
        <button type="button" aria-label="隐藏插图" title="隐藏插图" @click="emit('hide', true)"><EyeOff /></button>
      </div>
    </div>
  </figure>
</template>

<style scoped>
.plate { margin: 2px 0 12px; }
.frame { position: relative; padding: 5px; border: 1px solid var(--page-border); border-radius: 4px; background: var(--page-bg); box-shadow: 0 1px 3px rgb(60 40 20 / 10%); }
/* The width follows the height limit, so a portrait image keeps its ratio instead of being cropped to the column. */
.image { --plate-max: min(62vh, 560px); position: relative; overflow: hidden; border-radius: 2px; background: var(--page-rule); max-height: var(--plate-max); width: min(100%, calc(var(--plate-max) * var(--plate-ratio))); margin-inline: auto; }
.open { display: block; width: 100%; height: 100%; padding: 0; border: 0; background: none; cursor: zoom-in; }
img { display: block; width: 100%; height: 100%; object-fit: cover; object-position: center 35%; opacity: 0; transition: opacity 0.6s ease; }
img.loaded { opacity: 1; }
.vignette { position: absolute; inset: 0; pointer-events: none; box-shadow: inset 0 0 80px rgb(43 30 15 / 32%), inset 0 0 0 1px rgb(43 38 33 / 16%); }

.actions { position: absolute; top: 14px; right: 14px; display: flex; gap: 6px; opacity: 0; transition: opacity 0.15s; }
.frame:hover .actions, .frame:focus-within .actions { opacity: 1; }
.actions .toggle { display: none; }
@media (hover: none) {
  .actions { opacity: 1; flex-direction: row-reverse; }
  .actions .toggle { display: flex; }
  .actions:not(.open) button:not(.toggle) { display: none; }
}
.actions button {
  width: 34px; height: 34px; border-radius: 50%; border: 0; display: flex; align-items: center; justify-content: center;
  background: rgb(29 27 32 / 55%); color: #f6efe3; cursor: pointer; backdrop-filter: blur(4px);
}
.actions button:hover:not(:disabled) { background: rgb(29 27 32 / 75%); }
.actions button:disabled { opacity: 0.5; cursor: not-allowed; }
.actions svg { width: 16px; height: 16px; }

.working {
  position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px;
  background-color: var(--page-rule);
  background-image: linear-gradient(100deg, transparent 30%, color-mix(in srgb, var(--page-bg) 75%, transparent) 50%, transparent 70%);
  background-size: 60% 100%; background-repeat: no-repeat; animation: shimmer 2.4s ease-in-out infinite;
  box-shadow: inset 0 0 60px rgb(133 122 106 / 18%); color: var(--page-muted);
}
.working svg { width: 26px; height: 26px; }
.working-title { font-family: var(--font-reading); font-size: 15px; letter-spacing: 0.2em; }
.steps { display: flex; gap: 14px; flex-wrap: wrap; justify-content: center; font-size: 12px; opacity: 0.8; padding: 0 12px; }
.steps .active { color: var(--page-em); font-weight: 600; opacity: 1; }
.bar { position: absolute; left: 0; right: 0; bottom: 0; height: 2px; background: linear-gradient(90deg, transparent, var(--page-muted), transparent); background-size: 40% 100%; background-repeat: no-repeat; animation: shimmer 1.8s linear infinite; opacity: 0.5; }
.detail { font-size: 12px; font-variant-numeric: tabular-nums; color: var(--page-em); padding: 0 12px; text-align: center; }
.meter { position: absolute; left: 0; right: 0; bottom: 0; height: 3px; background: color-mix(in srgb, var(--page-muted) 20%, transparent); }
.meter span { display: block; height: 100%; background: var(--page-em); transition: width 0.3s ease; }
.pulse { animation: pulse 1.8s ease-in-out infinite; }
@keyframes shimmer { 0% { background-position: -60% 0; } 100% { background-position: 160% 0; } }
@keyframes pulse { 0%, 100% { opacity: 0.35; } 50% { opacity: 1; } }
@media (prefers-reduced-motion: reduce) { .working, .bar, .pulse { animation: none; } }

.rule { flex: 1; min-width: 16px; height: 0; border-top: 1px dashed var(--page-border); }

.failed {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 0 0 14px; padding: 6px 8px 6px 10px;
  border: 1px solid var(--page-border); border-radius: 8px; background: var(--page-rule); font-size: 13px; color: var(--page-em);
}
.failed .grow { min-width: 0; overflow-wrap: anywhere; }
.muted-ink { color: var(--page-muted); }
.warn-ic { width: 16px; height: 16px; color: var(--warn); flex-shrink: 0; }
.btn.paper { background: var(--page-bg); border-color: var(--page-border); color: var(--page-text); }
.btn.paper-ghost { color: var(--page-muted); }
.hidden-strip {
  display: flex; align-items: center; gap: 12px; width: 100%; margin: 0 0 10px; padding: 6px 0; border: 0; background: none;
  font-family: var(--font-reading); font-size: 12.5px; letter-spacing: 0.12em; color: var(--page-muted); cursor: pointer;
}
.hidden-strip svg { width: 14px; height: 14px; }
.hidden-strip:hover { color: var(--page-em); }

@media (max-width: 640px) {
  /* Full-bleed inside the page bubble on phones. */
  .plate { margin: -14px -14px 12px; }
  .frame { padding: 0; border: 0; border-radius: 0; box-shadow: none; }
  .image { --plate-max: 70vh; border-radius: 4px 16px 0 0; }
}
</style>
