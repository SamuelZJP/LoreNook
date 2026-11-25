<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { hue, initials } from '@/lib/format'

/**
 * A 3:4 cover for a character or identity: the portrait, else the avatar
 * filling the frame, else the avatar's gradient with the name's first character.
 * The default slot overlays the bottom, for names and taglines.
 */
const props = defineProps<{ name?: string | null; portrait?: string | null; avatar?: string | null }>()

const failed = ref(new Set<string>())
watch(() => [props.portrait, props.avatar], () => (failed.value = new Set()))
const usable = (src?: string | null) => {
  const s = src?.trim()
  return s && /^(https?:|data:image\/|\/|\.\/)/i.test(s) && !failed.value.has(s) ? s : null
}
const image = computed(() => usable(props.portrait) ?? usable(props.avatar))
function onError() {
  if (image.value) failed.value = new Set([...failed.value, image.value])
}
</script>

<template>
  <div class="cover" :class="{ blank: !image && !name?.trim() }" :style="{ '--cover-hue': String(hue(name ?? '')) }">
    <img v-if="image" :src="image" alt="" referrerpolicy="no-referrer" @error="onError" />
    <span v-else-if="name?.trim()" class="glyph" aria-hidden="true">{{ initials(name) }}</span>
    <div v-if="$slots.default" class="overlay"><slot /></div>
  </div>
</template>

<style scoped>
.cover {
  position: relative; aspect-ratio: 3 / 4; overflow: hidden; border-radius: inherit;
  /* Same gradient as AvatarBadge, with a soft light from the top left. */
  background:
    radial-gradient(90% 60% at 20% 10%, rgb(255 255 255 / 22%), transparent 70%),
    linear-gradient(150deg, hsl(var(--cover-hue) 50% 66%), hsl(calc(var(--cover-hue) + 24) 42% 40%));
}
/* Nothing to show yet: a plain ground instead of a tint picked from an empty name. */
.cover.blank { background: var(--bg-sunken); }
.cover img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.glyph {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  font-family: var(--font-reading); font-size: 7em; line-height: 1; user-select: none;
  color: rgb(255 255 255 / 30%);
}
.overlay {
  position: absolute; left: 0; right: 0; bottom: 0; padding: var(--space-8) var(--space-3) var(--space-3);
  background: linear-gradient(to top, rgb(20 14 8 / 72%), rgb(20 14 8 / 0%));
  color: #fdfbf7;
}
</style>
