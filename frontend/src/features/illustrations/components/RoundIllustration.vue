<script setup lang="ts">
import { computed } from 'vue'
import { Image as ImageIcon } from 'lucide-vue-next'
import type { RoundRead } from '@/api/endpoints'
import { useChatIllustrations } from '../useChatIllustrations'
import IllustrationPlate from './IllustrationPlate.vue'

/**
 * A round's plate, or nothing. Place at the head of the round's reading page, before its scene line.
 * While the panel is docked the plate lives there, and the page keeps a small marker instead.
 */
const props = defineProps<{ round: RoundRead }>()
const emit = defineEmits<{ show: [] }>()
const c = useChatIllustrations()
const item = computed(() => c.byRound.value.get(props.round.id))

const label = computed(() => {
  const it = item.value
  if (!it) return ''
  if (it.hidden) return '插图已隐藏'
  if (it.status === 'failed') return '插图未能生成'
  if (it.status === 'ready') return '插图'
  return '插图绘制中'
})
const showing = computed(() => c.current.value?.round_id === props.round.id)
function markRef(el: unknown) {
  c.mark(props.round.id, el instanceof HTMLElement ? el : null)
}
function show() {
  c.show(props.round.id)
  emit('show')
}
</script>

<template>
  <template v-if="item">
    <button
      v-if="c.docked.value" :ref="markRef" class="marker" :class="{ showing }" type="button"
      :title="showing ? '右侧正在显示这一回合的插图' : '在右侧显示这一回合的插图'" @click="show"
    >
      <ImageIcon /><span>{{ label }}</span>
    </button>
    <IllustrationPlate
      v-else :chat-id="c.chatId.value" :illustration="item" :progress="c.progress.value[item.id]" :busy="c.busy(round.id)"
      @open="c.viewing.value = item!.id" @regenerate="c.illustrate(round.id)" @prompt="c.promptOf.value = item!"
      @focus="c.choosingFocus.value = round.id" @hide="c.setHidden(item!, $event)"
    />
  </template>
</template>

<style scoped>
.marker {
  display: inline-flex; align-items: center; gap: var(--space-1); margin-bottom: var(--space-2); padding: 2px var(--space-2);
  border: 0; border-radius: var(--radius-pill); background: var(--bg-sunken); color: var(--text-faint);
  font: inherit; font-size: var(--text-xs); cursor: pointer; transition: color 0.15s, background 0.15s;
}
.marker:hover { color: var(--text); background: var(--bg-hover); }
.marker.showing { color: var(--accent); background: var(--accent-soft); }
.marker svg { width: 13px; height: 13px; }
</style>
