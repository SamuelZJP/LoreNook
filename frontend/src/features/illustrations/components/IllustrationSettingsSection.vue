<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import type { ChatDetail } from '@/api/endpoints'
import ErrorBox from '@/components/ErrorBox.vue'
import InfoTip from '@/components/InfoTip.vue'
import { useSaveTracker } from '@/composables/autosave'
import { illustrationApi, type IllustrationMode, type IllustrationSettings } from '../api'
import { MODE_LABELS } from '../lib'
import FocusPicker from './FocusPicker.vue'

/** A chat's illustration settings, saved as they change. */
const props = defineProps<{ chat: ChatDetail }>()
const qc = useQueryClient()
const tracker = useSaveTracker()
const chatId = computed(() => props.chat.id)
const settings = useQuery({ queryKey: computed(() => ['illustration-settings', chatId.value]), queryFn: () => illustrationApi.settings(chatId.value) })
const workflows = useQuery({ queryKey: computed(() => ['workflows', chatId.value]), queryFn: () => illustrationApi.workflows({ chatId: chatId.value }) })
const options = useQuery({ queryKey: computed(() => ['focus-options', chatId.value]), queryFn: () => illustrationApi.focusOptions(chatId.value) })

const form = reactive({ mode: 'off' as IllustrationMode, image_workflow_id: '', focus: [] as string[] })
// Filled once; after that the form leads, so a late save can't undo newer edits.
const loaded = computed(() => !!settings.data.value)
let filled = false
watch(() => settings.data.value, (s) => {
  if (!s || filled) return
  filled = true
  Object.assign(form, { mode: s.mode ?? 'off', image_workflow_id: s.image_workflow_id ?? '', focus: [...(s.focus ?? [])] })
}, { immediate: true })

const body = (): IllustrationSettings => ({ mode: form.mode, image_workflow_id: form.image_workflow_id || null, focus: [...form.focus] })
watch(() => JSON.stringify(body()), (now) => {
  const s = settings.data.value
  if (!filled || !s) return
  if (now === JSON.stringify({ mode: s.mode ?? 'off', image_workflow_id: s.image_workflow_id ?? null, focus: s.focus ?? [] })) return
  tracker.schedule('illustration', async () => {
    qc.setQueryData(['illustration-settings', chatId.value], await illustrationApi.putSettings(chatId.value, body()))
  }, 300)
})
</script>

<template>
  <div class="stack">
    <ErrorBox v-if="settings.error.value" :error="settings.error.value" title="读取失败" />
    <template v-if="loaded">
      <div class="field">
        <div class="row tip-row">
          <label class="label">生成时机</label>
          <InfoTip>回合整理完成后在后台生成，不会耽误下一回合。除“关闭”外，都可以在回合下方手动生成。</InfoTip>
        </div>
        <select v-model="form.mode" class="select">
          <option v-for="(label, mode) in MODE_LABELS" :key="mode" :value="mode">{{ label }}</option>
        </select>
      </div>
      <template v-if="form.mode !== 'off'">
        <div class="field">
          <label>绘图工作流</label>
          <select v-model="form.image_workflow_id" class="select">
            <option value="">（未选择）</option>
            <option v-for="w in workflows.data.value" :key="w.id" :value="w.id">{{ w.name }} · {{ w.width }}×{{ w.height }}</option>
          </select>
          <span v-if="!workflows.data.value?.length" class="hint">本聊天还没有绘图工作流，可在“幕后 › 本聊天资源”中导入。</span>
          <span v-else-if="!form.image_workflow_id" class="hint warn">选择工作流后才会生成插图。</span>
        </div>
        <div class="field">
          <div class="row tip-row">
            <label class="label">主要人物</label>
            <InfoTip>人物来自角色的“插图外貌”。生成时也可以临时更换。</InfoTip>
          </div>
          <FocusPicker v-if="options.data.value" v-model="form.focus" :options="options.data.value" />
        </div>
      </template>
    </template>
  </div>
</template>

<style scoped>
.tip-row { gap: var(--space-1); }
</style>
