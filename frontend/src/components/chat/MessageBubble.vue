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
  /** Keep the action row visible instead of revealing it on hover, e.g. on the newest entry. */
  pinActions?: boolean
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
  <div class="msg" :class="[side, { pending, wide, 'pin-actions': pinActions }]">
    <div class="col">
      <div class="meta">
        <AvatarBadge class="av" :name="name" :src="avatar" :size="side === 'ai' ? 28 : 24" />
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
/* AI text runs the full reading width under a name line; the user's input is a soft bubble on the right. */
.msg { display: flex; max-width: 100%; }
.msg.user { justify-content: flex-end; }
.col { display: flex; flex-direction: column; gap: var(--space-2); min-width: 0; max-width: 100%; }
.ai .col { width: 100%; }
.user .col { align-items: flex-end; max-width: 80%; }
.meta { display: flex; align-items: center; gap: var(--space-2); font-size: var(--text-xs); color: var(--text-faint); flex-wrap: wrap; }
.user .meta { flex-direction: row-reverse; }
.name { font-weight: 600; font-size: var(--text-sm); color: var(--text); }
.user .name { font-weight: 500; color: var(--text-muted); font-size: var(--text-xs); }
.bubble { --pad-y: calc(var(--space-3) * 2); padding: var(--space-3) var(--space-4); border-radius: var(--radius-l); background: var(--bg-sunken); min-width: 0; max-width: 100%; }
.bubble.page-surface { --pad-y: 0px; padding: 0; background: none; border-radius: 0; }
.user .bubble { background: var(--bubble-user); color: var(--bubble-user-text); border-radius: 20px 20px var(--radius-xs) 20px; padding: var(--space-3) var(--space-4); }
/* An unsaved candidate keeps a dashed outline so it never reads as part of the story yet. */
.pending .bubble, .pending .bubble.page-surface { outline: 1px dashed var(--accent); outline-offset: var(--space-2); border-radius: var(--radius-s); }
.user.pending .bubble { outline-color: var(--text-faint); border-radius: 20px 20px var(--radius-xs) 20px; }
/* The body never shrinks below a few lines, so a tall illustration can push the bubble past the cap. */
.capped .body {
  max-height: max(calc(var(--reply-cap, 100vh) - var(--fixed-h) - var(--pad-y)), calc(var(--reading-size, 16px) * 8));
  overflow-y: auto; scrollbar-width: thin;
  margin-right: calc(-1 * var(--space-3)); padding-right: var(--space-3);
}
.capped .body.more { mask-image: linear-gradient(to bottom, #000 calc(100% - 2.5em), transparent); }
.actions { display: flex; gap: var(--space-0-5); flex-wrap: wrap; margin-left: calc(-1 * var(--space-2)); opacity: 0; transition: opacity 0.15s; }
.actions :deep(.btn.ghost) { color: var(--text-faint); }
.actions :deep(.btn.ghost:hover:not(:disabled)) { color: var(--text); }
.msg:hover .actions, .msg:focus-within .actions, .pin-actions .actions { opacity: 1; }
.user .actions { justify-content: flex-end; margin-left: 0; margin-right: calc(-1 * var(--space-2)); }
@media (hover: none) { .actions { opacity: 1; } }
@media (max-width: 640px) {
  .user .col { max-width: 92%; }
  .capped .body { margin-right: calc(-1 * var(--space-2)); padding-right: var(--space-2); }
}
</style>
