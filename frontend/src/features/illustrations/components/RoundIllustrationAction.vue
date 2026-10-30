<script setup lang="ts">
import { ImagePlus } from 'lucide-vue-next'
import type { RoundRead } from '@/api/endpoints'
import { useChatIllustrations } from '../useChatIllustrations'

/** "Illustrate this round", for an archived round with no attempt yet. */
defineProps<{ round: RoundRead }>()
const c = useChatIllustrations()
</script>

<template>
  <button
    v-if="c.enabled.value && round.archive_step === 'complete' && !c.byRound.value.get(round.id)"
    class="btn ghost small" type="button" :disabled="c.busy(round.id)" @click="c.illustrate(round.id)"
  ><ImagePlus /> 插图</button>
</template>
