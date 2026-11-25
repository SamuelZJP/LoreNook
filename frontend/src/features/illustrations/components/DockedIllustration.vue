<script setup lang="ts">
import { useChatIllustrations } from '../useChatIllustrations'
import IllustrationPlate from './IllustrationPlate.vue'

/** The panel's illustration while it is docked: the round being read, cross-fading as reading moves on. */
const c = useChatIllustrations()
</script>

<template>
  <div v-if="c.docked.value && c.current.value" class="docked">
    <Transition name="swap" mode="out-in">
      <IllustrationPlate
        :key="c.current.value.id" fixed :chat-id="c.chatId.value" :illustration="c.current.value"
        :progress="c.progress.value[c.current.value.id]" :busy="c.busy(c.current.value.round_id)"
        @open="c.viewing.value = c.current.value!.id" @regenerate="c.illustrate(c.current.value!.round_id)"
        @prompt="c.promptOf.value = c.current.value" @focus="c.choosingFocus.value = c.current.value!.round_id"
        @hide="c.setHidden(c.current.value!, $event)"
      />
    </Transition>
  </div>
</template>

<style scoped>
.docked { padding: var(--space-3) var(--space-4) calc(var(--space-4) + env(safe-area-inset-bottom)); }
/* At most a third of the panel's height on short screens; the frame stays 4:3 and narrows. */
.docked :deep(.plate.fixed) { max-width: calc((100dvh - 2 * var(--island-gap)) / 3 * 4 / 3); margin-inline: auto; }
/* Hidden and failed plates are single lines; keep them off the panel's bottom edge. */
.docked :deep(.hidden-strip), .docked :deep(.failed) { margin: 0; }
.swap-enter-active, .swap-leave-active { transition: opacity 0.25s ease; }
.swap-enter-from, .swap-leave-to { opacity: 0; }
@media (prefers-reduced-motion: reduce) { .swap-enter-active, .swap-leave-active { transition: none; } }
</style>
