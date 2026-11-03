<script setup lang="ts">
import { computed } from 'vue'
import type { RoundRead } from '@/api/endpoints'
import { useChatIllustrations } from '../useChatIllustrations'
import IllustrationPlate from './IllustrationPlate.vue'

/** A round's plate, or nothing. Place at the head of the round's reading page, before its scene line. */
const props = defineProps<{ round: RoundRead }>()
const c = useChatIllustrations()
const item = computed(() => c.byRound.value.get(props.round.id))
</script>

<template>
  <IllustrationPlate
    v-if="item" :chat-id="c.chatId.value" :illustration="item" :progress="c.progress.value[item.id]" :busy="c.busy(round.id)"
    @open="c.viewing.value = item!.id" @regenerate="c.illustrate(round.id)" @prompt="c.promptOf.value = item!"
    @focus="c.choosingFocus.value = round.id" @hide="c.setHidden(item!, $event)"
  />
</template>
