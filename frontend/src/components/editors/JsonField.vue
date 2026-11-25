<script setup lang="ts">
import { computed } from 'vue'
import CodeEditor from '../CodeEditor.vue'

/** JSON text editor with inline parse feedback. Parent keeps the text; use `parseJson` to read it. */
const props = withDefaults(defineProps<{ modelValue: string; label?: string; minHeight?: string; maxHeight?: string; readonly?: boolean; requireObject?: boolean }>(), {
  minHeight: '120px', maxHeight: '50vh', requireObject: true,
})
const emit = defineEmits<{ 'update:modelValue': [string] }>()
const problem = computed(() => jsonProblem(props.modelValue, props.requireObject))
</script>

<script lang="ts">
export function jsonProblem(text: string, requireObject = true): string | null {
  try {
    const v = JSON.parse(text)
    if (requireObject && (typeof v !== 'object' || v === null || Array.isArray(v))) return '必须是 JSON 对象'
    return null
  } catch (e) {
    return (e as Error).message
  }
}
</script>

<template>
  <div class="field">
    <label v-if="label">{{ label }}</label>
    <CodeEditor :model-value="modelValue" language="json" :min-height="minHeight" :max-height="maxHeight" :readonly="readonly" @update:model-value="emit('update:modelValue', $event)" />
    <span v-if="problem && !readonly" class="bad">JSON 无效：{{ problem }}</span>
  </div>
</template>

<style scoped>
.bad { font-size: var(--text-xs); color: var(--danger); }
</style>
