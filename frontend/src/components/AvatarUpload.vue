<script setup lang="ts">
import { ref } from 'vue'
import { Camera, X } from 'lucide-vue-next'
import { api } from '@/api/endpoints'
import { toast } from '@/composables/toast'
import AvatarBadge from './AvatarBadge.vue'
import CropDialog from './CropDialog.vue'

/** A round avatar that uploads a square-cropped image when clicked. `modelValue` is the stored URL, '' for none. */
withDefaults(defineProps<{ modelValue: string; name?: string; size?: number }>(), { size: 64 })
const emit = defineEmits<{ 'update:modelValue': [string] }>()

const input = ref<HTMLInputElement>()
const file = ref<File | null>(null)
const uploading = ref(false)

function choose(e: Event) {
  file.value = (e.target as HTMLInputElement).files?.[0] ?? null
  if (input.value) input.value.value = ''
}
async function upload(blob: Blob) {
  file.value = null
  uploading.value = true
  try {
    emit('update:modelValue', (await api.uploadMedia(blob)).url)
  } catch (error) {
    toast(error instanceof Error ? error.message : String(error), 'error')
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="avatar-upload" :style="{ width: `${size}px`, height: `${size}px` }">
    <button class="face" type="button" :disabled="uploading" aria-label="上传头像" title="上传头像" @click="input?.click()">
      <AvatarBadge v-if="modelValue || name?.trim()" :name="name" :src="modelValue" :size="size" class="badge-img" />
      <span class="hover" :class="{ always: !modelValue && !name?.trim() }"><Camera /></span>
    </button>
    <button v-if="modelValue" class="clear" type="button" aria-label="移除头像" title="移除头像" @click="emit('update:modelValue', '')"><X /></button>
    <input ref="input" type="file" accept="image/png,image/jpeg,image/webp" hidden @change="choose" />
    <CropDialog v-if="file" :file="file" :aspect="1" :output="512" title="调整头像" @done="upload" @close="file = null" />
  </div>
</template>

<style scoped>
.avatar-upload { position: relative; flex-shrink: 0; }
.face {
  position: relative; display: block; width: 100%; height: 100%; padding: 0; border: 0; border-radius: 50%; overflow: hidden;
  background: var(--bg-elev); box-shadow: 0 0 0 3px var(--bg-elev), var(--shadow); cursor: pointer;
}
.badge-img { width: 100% !important; height: 100% !important; border-radius: 50% !important; }
.hover {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  background: rgb(20 14 8 / 45%); color: #fff; opacity: 0; transition: opacity 0.15s;
}
.face:hover .hover, .face:focus-visible .hover { opacity: 1; }
/* Nothing to show yet: the camera stays, on a quiet ground. */
.hover.always { opacity: 1; background: var(--bg-sunken); color: var(--text-faint); }
.hover svg { width: 20px; height: 20px; }
.clear {
  position: absolute; top: -2px; right: -2px; width: 20px; height: 20px; padding: 0; border: 0; border-radius: 50%;
  display: flex; align-items: center; justify-content: center; background: var(--ink); color: var(--ink-text); cursor: pointer;
  opacity: 0; transition: opacity 0.15s;
}
.avatar-upload:hover .clear, .clear:focus-visible { opacity: 1; }
.clear svg { width: 12px; height: 12px; }
@media (hover: none) { .clear { opacity: 1; } }
</style>
