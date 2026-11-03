<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import ErrorBox from '@/components/ErrorBox.vue'
import { statusBarApi } from '../api'

/** A chat's status bar switch. Saves on change; only offered when the chat's character has code. */
const props = defineProps<{ chatId: string }>()
const qc = useQueryClient()
const bar = useQuery({ queryKey: computed(() => ['status-bar', props.chatId]), queryFn: () => statusBarApi.chat(props.chatId) })
const hasCode = computed(() => !!bar.data.value?.code.trim())

const saving = ref(false)
const error = ref<unknown>(null)
async function setEnabled(enabled: boolean) {
  saving.value = true
  error.value = null
  try {
    qc.setQueryData(['status-bar', props.chatId], await statusBarApi.patchChat(props.chatId, { enabled }))
  } catch (e) {
    error.value = e
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="stack">
    <h3>状态栏</h3>
    <ErrorBox v-if="bar.error.value" :error="bar.error.value" title="读取失败" />
    <template v-else-if="bar.data.value">
      <label class="check">
        <input type="checkbox" :checked="bar.data.value.enabled && hasCode" :disabled="!hasCode || saving"
               @change="setEnabled(($event.target as HTMLInputElement).checked)" />
        在回复底部显示状态栏
      </label>
      <span v-if="!hasCode" class="hint">本聊天的角色没有状态栏代码，可以在“资源”标签的角色“状态栏”中编写。</span>
      <span v-else class="hint">最新回合总是显示；更早的回合可在回合下方单独展开。</span>
    </template>
    <ErrorBox v-if="error" :error="error" title="保存失败" />
  </div>
</template>
