<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import AvatarBadge from '../AvatarBadge.vue'
import { substituteNames } from '@/lib/format'

/** The head of a conversation: who this story is with, before its opening. */
const props = defineProps<{
  name: string
  avatar?: string | null
  portrait?: string | null
  description?: string
  scene?: string | null
  identity: string
}>()

const bio = computed(() => substituteNames(props.description ?? '', props.identity, props.name).trim())
const expanded = ref(false)
const clamped = ref(false)
const bioEl = ref<HTMLElement>()

// Offer "展开" only when the clamp actually hides text.
function measure() {
  const el = bioEl.value
  clamped.value = !!el && !expanded.value && el.scrollHeight - el.clientHeight > 1
}
let observer: ResizeObserver | null = null
watch(bioEl, (el) => {
  observer?.disconnect()
  if (!el) return
  observer = new ResizeObserver(measure)
  observer.observe(el)
})
watch(bio, () => { expanded.value = false; nextTick(measure) })
onBeforeUnmount(() => observer?.disconnect())
</script>

<template>
  <header class="intro">
    <AvatarBadge :name="name" :src="avatar || portrait" :size="88" class="face" />
    <h2>{{ name }}</h2>
    <div class="meta">
      <span v-if="scene">{{ scene }}</span>
      <span v-if="scene" aria-hidden="true">·</span>
      <span>{{ identity }} 的故事</span>
    </div>
    <p v-if="bio" ref="bioEl" class="bio" :class="{ open: expanded }">{{ bio }}</p>
    <button v-if="bio && (clamped || expanded)" class="more" type="button" @click="expanded = !expanded">
      {{ expanded ? '收起' : '展开' }}
    </button>
    <div class="divider">故事开始</div>
  </header>
</template>

<style scoped>
.intro { display: flex; flex-direction: column; align-items: center; text-align: center; padding-top: var(--space-6); }
.face { box-shadow: var(--shadow); }
.face :deep(img) { object-position: top; }
h2 { margin-top: var(--space-4); font-family: var(--font-reading); font-size: 28px; font-weight: 700; letter-spacing: 0.02em; }
.meta { display: flex; gap: var(--space-1-5); margin-top: var(--space-1-5); font-size: var(--text-sm); color: var(--text-faint); }
.bio {
  max-width: 480px; margin-top: var(--space-3); color: var(--text-muted); line-height: 1.75; white-space: pre-line;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.bio.open { display: block; }
.more { margin-top: var(--space-1); border: 0; background: none; padding: var(--space-1) var(--space-2); font: inherit; font-size: var(--text-xs); color: var(--accent); cursor: pointer; }
.divider {
  align-self: stretch; display: flex; align-items: center; gap: var(--space-3); margin: var(--space-8) 0 var(--space-2);
  font-size: var(--text-xs); color: var(--text-faint); letter-spacing: 0.08em;
}
.divider::before, .divider::after { content: ''; flex: 1; height: 1px; background: var(--border); }
</style>
