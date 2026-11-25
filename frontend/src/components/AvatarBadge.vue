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
/* A circle: the image, or the name's first character in white on a gradient of a stable hue. */
.avatar {
  display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; border-radius: 50%;
  overflow: hidden; user-select: none; font-family: var(--font-reading); font-weight: 600; color: #fff;
  text-shadow: 0 1px 2px rgb(0 0 0 / 20%);
  background: linear-gradient(140deg, hsl(var(--avatar-hue, 30) 50% 66%), hsl(calc(var(--avatar-hue, 30) + 24) 42% 40%));
  box-shadow: inset 0 0 0 1px rgb(255 255 255 / 12%);
}
.avatar img { width: 100%; height: 100%; object-fit: cover; }
</style>
