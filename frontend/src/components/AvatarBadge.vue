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
  fontSize: `${Math.round(props.size * 0.42)}px`,
  background: url.value ? undefined : `hsl(${hue(props.name ?? '')} 55% 52%)`,
}))
</script>

<template>
  <span class="avatar" :style="style">
    <img v-if="url" :src="url" alt="" referrerpolicy="no-referrer" @error="failed = true" />
    <template v-else>{{ initials(name) }}</template>
  </span>
</template>

<style scoped>
.avatar {
  display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;
  border-radius: 50%; color: #fff; font-weight: 600; overflow: hidden; user-select: none;
}
.avatar img { width: 100%; height: 100%; object-fit: cover; }
</style>
