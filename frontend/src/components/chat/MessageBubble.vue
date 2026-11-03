<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import AvatarBadge from '../AvatarBadge.vue'

/** One chat entry. `side` follows chat convention: the user's persona on the right. */
const props = defineProps<{
  side: 'user' | 'ai'
  name: string
  avatar?: string | null
  floor?: number | string | null
  pending?: boolean
  /** Paint the bubble as the reading page used for AI output. */
  page?: boolean
  /** Take the full reading width instead of shrinking to the text, e.g. when it holds an illustration. */
  wide?: boolean
  /**
   * Keep the bubble within `--reply-cap` (set by the chat view): `head` and `foot` stay in view
   * and only the default slot scrolls.
   */
  capped?: boolean
}>()

const bubble = ref<HTMLElement>()
const head = ref<HTMLElement>()
const body = ref<HTMLElement>()
const foot = ref<HTMLElement>()
const fixedHeight = ref(0)
const more = ref(false)

function measure() {
  fixedHeight.value = (head.value?.offsetHeight ?? 0) + (foot.value?.offsetHeight ?? 0)
  const el = body.value
  more.value = !!el && el.scrollHeight - el.scrollTop - el.clientHeight > 2
}
let observer: ResizeObserver | null = null
// Head and foot come and go (an illustration appears, a status bar loads), so re-observe on each change.
watch([() => props.capped, bubble, head, foot], ([capped]) => {
  observer?.disconnect()
  observer = null
  more.value = false
  if (!capped || !bubble.value) return
  observer = new ResizeObserver(measure)
  for (const el of [head.value, body.value, foot.value, body.value?.firstElementChild]) if (el) observer.observe(el)
  measure()
}, { flush: 'post' })
onBeforeUnmount(() => observer?.disconnect())
</script>

<template>
  <div class="msg" :class="[side, { pending, wide }]">
    <AvatarBadge class="av" :name="name" :src="avatar" :size="34" />
    <div class="col">
      <div class="meta">
        <span class="name">{{ name }}</span>
        <slot name="meta" />
      </div>
      <div ref="bubble" class="bubble" :class="{ 'page-surface': page, capped }" :style="capped ? { '--fixed-h': `${fixedHeight}px` } : undefined">
        <div v-if="$slots.head" ref="head"><slot name="head" /></div>
        <div ref="body" class="body" :class="{ more }" @scroll.passive="capped && measure()"><div><slot /></div></div>
        <div v-if="$slots.foot" ref="foot"><slot name="foot" /></div>
      </div>
      <div v-if="$slots.actions" class="actions"><slot name="actions" /></div>
    </div>
  </div>
</template>

<style scoped>
.msg { display: flex; gap: 10px; align-items: flex-start; max-width: 100%; }
.msg.user { flex-direction: row-reverse; }
.col { display: flex; flex-direction: column; gap: 4px; min-width: 0; max-width: min(760px, 86%); }
.user .col { align-items: flex-end; }
.wide .col { width: min(760px, 86%); }
.meta { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--text-faint); flex-wrap: wrap; }
.user .meta { flex-direction: row-reverse; }
.name { font-weight: 600; color: var(--text-muted); }
.bubble {
  padding: 10px 14px; border-radius: var(--radius-l); background: var(--bubble-ai);
  border: 1px solid var(--border); box-shadow: var(--shadow); min-width: 0; max-width: 100%;
}
.ai .bubble { border-top-left-radius: 4px; }
.bubble.page-surface { padding: 16px 20px 14px; --pad-y: 30px; }
.user .bubble { background: var(--bubble-user); color: var(--bubble-user-text); border-color: transparent; border-top-right-radius: 4px; }
.pending .bubble { border-style: dashed; border-color: var(--accent); }
.user.pending .bubble { border: 1px dashed var(--bubble-user-text); }
/* The body never shrinks below a few lines, so a tall illustration can push the bubble past the cap. */
.capped .body {
  max-height: max(calc(var(--reply-cap, 100vh) - var(--fixed-h) - var(--pad-y, 20px)), calc(var(--reading-size, 16px) * 8));
  overflow-y: auto; scrollbar-width: thin;
  margin-right: -10px; padding-right: 10px;
}
.capped .body.more { mask-image: linear-gradient(to bottom, #000 calc(100% - 2.5em), transparent); }
.actions { display: flex; gap: 4px; flex-wrap: wrap; }
.user .actions { justify-content: flex-end; }
@media (max-width: 640px) {
  .av { display: none; }
  .col { max-width: 94%; }
  .wide .col { width: 94%; }
  .bubble.page-surface { padding: 14px 14px 12px; --pad-y: 26px; }
  .capped .body { margin-right: -8px; padding-right: 8px; }
}
</style>
