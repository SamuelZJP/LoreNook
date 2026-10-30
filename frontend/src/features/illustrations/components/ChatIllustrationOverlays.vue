<script setup lang="ts">
import { useChatIllustrations } from '../useChatIllustrations'
import FocusDialog from './FocusDialog.vue'
import PromptDialog from './PromptDialog.vue'
import SceneViewer from './SceneViewer.vue'

/** Full-screen viewer and dialogs for the open chat. */
const c = useChatIllustrations()
function regenerate(roundId: string) {
  c.viewing.value = null
  c.illustrate(roundId)
}
</script>

<template>
  <SceneViewer
    v-if="c.viewing.value && c.gallery.value.length" :chat-id="c.chatId.value" :items="c.gallery.value" :start-id="c.viewing.value"
    @close="c.viewing.value = null" @prompt="(id) => (c.promptOf.value = c.byRound.value.get(id) ?? null)" @regenerate="regenerate"
  />
  <PromptDialog v-if="c.promptOf.value" :illustration="c.promptOf.value" @close="c.promptOf.value = null" />
  <FocusDialog
    v-if="c.choosingFocus.value" :chat-id="c.chatId.value" :current="c.byRound.value.get(c.choosingFocus.value)?.focus ?? []"
    @close="c.choosingFocus.value = null"
    @confirm="(focus) => { c.illustrate(c.choosingFocus.value!, focus); c.choosingFocus.value = null }"
  />
</template>
