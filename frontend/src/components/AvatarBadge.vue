<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { hue, initials } from '@/lib/format'

const props = withDefaults(defineProps<{ name?: string | null; src?: string | null; size?: number }>(), { size: 36 })
const failed = ref(false)
watch(() => props.src, () => (failed.value = false))

// Avatars are stored references; only show image-like ones.
const url = computed(() => {
  const src = props.src?.trim()
  if (!src || failed.value) return null
  return /^(https?:|data:image\/|\/|\.\/)/i.test(src) ? src : null
})
const style = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  fontSize: `${Math.round(props.size * 0.44)}px`,
  borderRadius: `${Math.round(props.size * 0.3)}px`,
  '--avatar-hue': url.value ? undefined : String(hue(props.name ?? '')),
}))
</script>

<template>
  <span class="avatar" :style="style">
    <img v-if="url" :src="url" alt="" referrerpolicy="no-referrer" @error="failed = true" />
    <template v-else>{{ initials(name) }}</template>
  </span>
</template>

<style scoped>
/* A rounded tile: the image, or the name's first character in a soft tone of a stable hue. */
.avatar {
  display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;
  overflow: hidden; user-select: none; font-family: var(--font-reading); font-weight: 500;
  background: hsl(var(--avatar-hue, 30) 32% var(--avatar-bg-l));
  color: hsl(var(--avatar-hue, 30) 35% var(--avatar-text-l));
  box-shadow: inset 0 0 0 1px var(--border);
}
.avatar img { width: 100%; height: 100%; object-fit: cover; }
</style>
