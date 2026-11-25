<script setup lang="ts">
import { computed } from 'vue'
import { AlertTriangle } from 'lucide-vue-next'
import type { FocusOptions } from '../api'
import { FOCUS_SOFT_LIMIT } from '../lib'

/** Choose main characters. An empty choice means the default. */
const props = defineProps<{ options: FocusOptions; modelValue: string[] }>()
const emit = defineEmits<{ 'update:modelValue': [string[]] }>()
const chosen = computed(() => new Set(props.modelValue))
function toggle(id: string) {
  const next = new Set(chosen.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  // Keep the options' order: it decides how the reference images are numbered.
  emit('update:modelValue', props.options.options.map((o) => o.id).filter((i) => next.has(i)))
}
const defaultNames = computed(() => props.options.options.filter((o) => props.options.default.includes(o.id)).map((o) => o.name).join('、'))
const undescribed = computed(() => {
  const ids = props.modelValue.length ? props.modelValue : props.options.default
  return props.options.options.filter((o) => ids.includes(o.id) && !o.has_appearance && !o.has_reference).map((o) => o.name).join('、')
})
</script>

<template>
  <div class="stack tight">
    <label v-for="o in options.options" :key="o.id" class="check">
      <input type="checkbox" :checked="chosen.has(o.id)" @change="toggle(o.id)" />
      {{ o.name }}<span v-if="o.has_reference" class="badge">有参考图</span>
    </label>
    <p v-if="!modelValue.length" class="hint">{{ defaultNames ? `未选择时默认：${defaultNames}` : '未选择时由剧情自动判断中心人物' }}</p>
    <p v-if="undescribed" class="hint warn"><AlertTriangle /> 未填写外貌：{{ undescribed }}。可以在“画像”标签中填写外貌或上传参考图。</p>
    <p v-if="modelValue.length > FOCUS_SOFT_LIMIT" class="hint warn"><AlertTriangle /> 目前的图像模型通常在 1–2 位主要人物时效果最好。</p>
  </div>
</template>

<style scoped>
.warn { color: var(--warn); display: flex; align-items: center; gap: var(--space-1); }
.warn svg { width: 14px; height: 14px; flex-shrink: 0; }
</style>
