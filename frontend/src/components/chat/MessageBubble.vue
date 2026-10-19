<script setup lang="ts">
import AvatarBadge from '../AvatarBadge.vue'

/** One chat entry. `side` follows chat convention: the user's persona on the right. */
defineProps<{
  side: 'user' | 'ai'
  name: string
  avatar?: string | null
  floor?: number | string | null
  pending?: boolean
}>()
</script>

<template>
  <div class="msg" :class="[side, { pending }]">
    <AvatarBadge class="av" :name="name" :src="avatar" :size="34" />
    <div class="col">
      <div class="meta">
        <span class="name">{{ name }}</span>
        <slot name="meta" />
      </div>
      <div class="bubble"><slot /></div>
      <div v-if="$slots.actions" class="actions"><slot name="actions" /></div>
    </div>
  </div>
</template>

<style scoped>
.msg { display: flex; gap: 10px; align-items: flex-start; max-width: 100%; }
.msg.user { flex-direction: row-reverse; }
.col { display: flex; flex-direction: column; gap: 4px; min-width: 0; max-width: min(760px, 86%); }
.user .col { align-items: flex-end; }
.meta { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--text-faint); flex-wrap: wrap; }
.user .meta { flex-direction: row-reverse; }
.name { font-weight: 600; color: var(--text-muted); }
.bubble {
  padding: 10px 14px; border-radius: var(--radius-l); background: var(--bubble-ai);
  border: 1px solid var(--border); box-shadow: var(--shadow); min-width: 0; max-width: 100%;
}
.ai .bubble { border-top-left-radius: 4px; }
.user .bubble { background: var(--bubble-user); color: var(--bubble-user-text); border-color: transparent; border-top-right-radius: 4px; }
.pending .bubble { border-style: dashed; border-color: var(--accent); }
.user.pending .bubble { border: 1px dashed var(--bubble-user-text); }
.actions { display: flex; gap: 4px; flex-wrap: wrap; }
.user .actions { justify-content: flex-end; }
@media (max-width: 640px) {
  .av { display: none; }
  .col { max-width: 94%; }
}
</style>
