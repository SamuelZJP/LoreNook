<script setup lang="ts">
import { ref } from 'vue'
import { ImagePlus, X } from 'lucide-vue-next'
import { api } from '@/api/endpoints'
import { toast } from '@/composables/toast'
import ProfileCover from './ProfileCover.vue'
import CropDialog from './CropDialog.vue'

/**
 * Pick an image, crop it to 3:4 and upload it. `modelValue` is the stored URL, '' for none.
 * The `badge` slot hangs off the frame's lower left corner (the profile's avatar).
 */
defineProps<{ modelValue: string }>()
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
  <div class="portrait-upload stack tight">
    <div class="frame-wrap" :class="{ 'has-badge': !!$slots.badge }">
      <button class="frame" type="button" :disabled="uploading" aria-label="上传立绘" @click="input?.click()">
        <!-- No name: an empty frame stays plain under the upload prompt. -->
        <ProfileCover :portrait="modelValue" />
        <span v-if="!modelValue" class="cta"><ImagePlus /> {{ uploading ? '上传中…' : '上传立绘' }}</span>
      </button>
      <div v-if="$slots.badge" class="badge"><slot name="badge" /></div>
    </div>
    <button v-if="modelValue" class="btn ghost small remove" type="button" @click="emit('update:modelValue', '')"><X /> 移除立绘</button>
    <input ref="input" type="file" accept="image/png,image/jpeg,image/webp" hidden @change="choose" />
    <CropDialog v-if="file" :file="file" @done="upload" @close="file = null" />
  </div>
</template>

<style scoped>
.frame-wrap { position: relative; }
.frame-wrap.has-badge { margin-bottom: 28px; }
.badge { position: absolute; left: var(--space-3); bottom: -28px; z-index: 1; }
.frame {
  display: block; width: 100%; padding: 0; border: 0; border-radius: var(--radius-l); overflow: hidden;
  cursor: pointer; background: none; box-shadow: inset 0 0 0 1px var(--border);
}
.frame:hover:not(:disabled) { outline: 2px solid var(--accent); outline-offset: 2px; }
.remove { align-self: flex-end; }
/* Centred over the empty frame, clear of the avatar badge at the bottom. */
.frame { position: relative; }
.cta {
  position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--space-2);
  font-size: var(--text-sm); font-weight: 500; color: var(--text-muted);
}
.frame:hover .cta { color: var(--accent); }
.cta svg { width: 28px; height: 28px; stroke-width: 1.5; }
</style>
