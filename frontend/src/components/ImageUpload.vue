<script setup lang="ts">
import { computed, ref } from 'vue'
import { ImagePlus, X } from 'lucide-vue-next'
import { api } from '@/api/endpoints'
import { toast } from '@/composables/toast'

/** Upload one image. `modelValue` is what the backend returned: the name, or the URL with `value="url"`. */
const props = withDefaults(defineProps<{
  modelValue: string | null
  label?: string
  value?: 'name' | 'url'
  urlOf?: (value: string) => string
  size?: number
}>(), { label: '上传图片', value: 'name', size: 96 })
const emit = defineEmits<{ 'update:modelValue': [string | null] }>()

const input = ref<HTMLInputElement>()
const uploading = ref(false)
const preview = computed(() => (props.modelValue ? (props.urlOf ? props.urlOf(props.modelValue) : props.modelValue) : null))

async function choose(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  uploading.value = true
  try {
    const media = await api.uploadMedia(file)
    emit('update:modelValue', media[props.value])
  } catch (error) {
    toast(error instanceof Error ? error.message : String(error), 'error')
  } finally {
    uploading.value = false
    if (input.value) input.value.value = ''
  }
}
</script>

<template>
  <div class="upload" :style="{ width: `${size}px` }">
    <button class="tile" type="button" :style="{ height: `${size}px` }" :aria-label="label" :disabled="uploading" @click="input?.click()">
      <img v-if="preview" :src="preview" alt="" />
      <span v-else class="empty-tile"><ImagePlus /><span>{{ uploading ? '上传中…' : label }}</span></span>
    </button>
    <button v-if="modelValue" class="btn ghost small clear" type="button" @click="emit('update:modelValue', null)"><X /> 移除</button>
    <input ref="input" type="file" accept="image/png,image/jpeg,image/webp" hidden @change="choose" />
  </div>
</template>

<style scoped>
.upload { display: flex; flex-direction: column; gap: 4px; flex-shrink: 0; }
.tile { display: block; width: 100%; padding: 0; overflow: hidden; border: 1px dashed var(--border-strong); border-radius: var(--radius-m); background: var(--bg-sunken); color: var(--text-muted); cursor: pointer; font: inherit; }
.tile:hover:not(:disabled) { border-color: var(--accent); }
.tile img { display: block; width: 100%; height: 100%; object-fit: cover; }
.empty-tile { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; height: 100%; font-size: 12px; }
.empty-tile svg { width: 20px; height: 20px; }
.clear { width: 100%; }
</style>
