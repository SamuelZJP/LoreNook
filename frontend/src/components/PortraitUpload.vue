<script setup lang="ts">
import { ref } from 'vue'
import { ImagePlus, X } from 'lucide-vue-next'
import { api } from '@/api/endpoints'
import { toast } from '@/composables/toast'
import ProfileCover from './ProfileCover.vue'
import CropDialog from './CropDialog.vue'

/** Pick an image, crop it to 3:4 and upload it. `modelValue` is the stored URL, '' for none. */
defineProps<{ modelValue: string; name?: string; avatar?: string }>()
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
    <button class="frame" type="button" :disabled="uploading" aria-label="上传立绘" @click="input?.click()">
      <ProfileCover :name="name" :portrait="modelValue" :avatar="avatar">
        <span v-if="!modelValue" class="cta"><ImagePlus /> {{ uploading ? '上传中…' : '上传立绘' }}</span>
      </ProfileCover>
    </button>
    <button v-if="modelValue" class="btn ghost small" type="button" @click="emit('update:modelValue', '')"><X /> 移除立绘</button>
    <input ref="input" type="file" accept="image/png,image/jpeg,image/webp" hidden @change="choose" />
    <CropDialog v-if="file" :file="file" @done="upload" @close="file = null" />
  </div>
</template>

<style scoped>
.frame {
  display: block; width: 100%; padding: 0; border: 0; border-radius: var(--radius-l); overflow: hidden;
  cursor: pointer; background: none; box-shadow: inset 0 0 0 1px var(--border);
}
.frame:hover:not(:disabled) { outline: 2px solid var(--accent); outline-offset: 2px; }
.cta { display: inline-flex; align-items: center; gap: var(--space-1-5); font-size: var(--text-sm); font-weight: 500; }
.cta svg { width: 16px; height: 16px; }
</style>
