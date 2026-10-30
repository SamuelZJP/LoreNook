<script setup lang="ts">
import type { Illustration } from '@/api/endpoints'
import ModalDialog from '../ModalDialog.vue'

defineProps<{ illustration: Illustration }>()
const emit = defineEmits<{ close: [] }>()
</script>

<template>
  <ModalDialog title="插图提示词" width="640px" @close="emit('close')">
    <div class="stack">
      <div v-for="(value, name) in illustration.prompt ?? {}" :key="name" class="field">
        <label><code>{{ name }}</code></label>
        <pre class="value">{{ value || '（空）' }}</pre>
      </div>
      <p class="hint">种子 {{ illustration.seed }} · {{ illustration.width }}×{{ illustration.height }}</p>
    </div>
  </ModalDialog>
</template>

<style scoped>
.value { padding: 8px 10px; background: var(--bg-sunken); border-radius: var(--radius-s); font-size: 13px; line-height: 1.6; user-select: text; }
</style>
