<script setup lang="ts">
import { computed, ref } from 'vue'
import { ApiError } from '@/api/client'
import { AlertTriangle } from 'lucide-vue-next'

const props = defineProps<{ error: unknown; title?: string }>()
const open = ref(false)

const message = computed(() => {
  const e = props.error
  if (e instanceof ApiError || e instanceof Error) return e.message
  return String(e)
})
const status = computed(() => (props.error instanceof ApiError ? props.error.status : null))
const raw = computed(() => {
  const e = props.error
  if (!(e instanceof ApiError) || typeof e.detail === 'string') return null
  return JSON.stringify(e.detail, null, 2)
})
</script>

<template>
  <div v-if="error" class="error-box" role="alert">
    <AlertTriangle class="icon" />
    <div class="grow">
      <div class="title">
        {{ title ?? '操作失败' }}
        <span v-if="status" class="faint">HTTP {{ status }}</span>
      </div>
      <pre class="message">{{ message }}</pre>
      <slot />
      <button v-if="raw" class="link" type="button" @click="open = !open">{{ open ? '隐藏' : '查看' }}原始信息</button>
      <pre v-if="open && raw" class="raw">{{ raw }}</pre>
    </div>
  </div>
</template>

<style scoped>
.error-box {
  display: flex; gap: var(--space-3); padding: var(--space-3) var(--space-3); border-radius: var(--radius-m);
  background: var(--danger-soft); color: var(--text); border: 1px solid color-mix(in srgb, var(--danger) 35%, transparent);
}
.icon { width: 18px; height: 18px; color: var(--danger); flex-shrink: 0; margin-top: var(--space-0-5); }
.title { font-weight: 600; display: flex; gap: var(--space-2); align-items: baseline; }
.message { font-family: inherit; font-size: var(--text-sm); margin-top: var(--space-0-5); }
.raw { margin-top: var(--space-1-5); padding: var(--space-2); background: var(--bg-elev); border-radius: var(--radius-s); max-height: 240px; overflow: auto; }
.link { border: 0; background: none; color: var(--accent); padding: 0; margin-top: var(--space-1); cursor: pointer; font: inherit; font-size: var(--text-xs); }
</style>
