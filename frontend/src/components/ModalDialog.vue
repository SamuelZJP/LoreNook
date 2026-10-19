<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { X } from 'lucide-vue-next'

const props = withDefaults(defineProps<{ title: string; width?: string; dismissable?: boolean }>(), {
  width: '560px',
  dismissable: true,
})
const emit = defineEmits<{ close: [] }>()

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.dismissable) emit('close')
}
onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <div class="backdrop" @mousedown.self="dismissable && emit('close')">
      <div class="dialog" :style="{ maxWidth: width }" role="dialog" aria-modal="true" :aria-label="title">
        <header>
          <h2 class="grow ellipsis">{{ title }}</h2>
          <button class="btn ghost icon" type="button" aria-label="关闭" :disabled="!dismissable" @click="emit('close')"><X /></button>
        </header>
        <div class="body"><slot /></div>
        <footer v-if="$slots.footer"><slot name="footer" /></footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.backdrop {
  position: fixed; inset: 0; z-index: 100; background: rgb(0 0 0 / 45%);
  display: flex; align-items: center; justify-content: center; padding: 16px;
}
.dialog {
  width: 100%; max-height: calc(100dvh - 32px); display: flex; flex-direction: column;
  background: var(--bg-elev); border-radius: var(--radius-l); box-shadow: var(--shadow-pop); border: 1px solid var(--border);
}
header { display: flex; align-items: center; gap: 8px; padding: 14px 16px 10px; }
.body { padding: 4px 16px 16px; overflow-y: auto; }
footer { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--border); flex-wrap: wrap; }
@media (max-width: 640px) {
  .backdrop { padding: 0; align-items: flex-end; }
  .dialog { max-width: none !important; max-height: 92dvh; border-radius: var(--radius-l) var(--radius-l) 0 0; padding-bottom: env(safe-area-inset-bottom); }
}
</style>
