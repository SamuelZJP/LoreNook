<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { Save } from 'lucide-vue-next'
import type { ModelConfig } from '@/api/endpoints'
import ErrorBox from '@/components/ErrorBox.vue'
import { toast } from '@/composables/toast'
import { illustrationApi, type IllustrationMode, type IllustrationSettings } from '../api'
import { MODE_LABELS } from '../lib'
import FocusPicker from './FocusPicker.vue'

/** A chat's illustration settings. Saves on its own, separately from the rest of the chat. */
const props = defineProps<{ chatId: string; modelConfigs: ModelConfig[] }>()
const qc = useQueryClient()
const settings = useQuery({ queryKey: computed(() => ['illustration-settings', props.chatId]), queryFn: () => illustrationApi.settings(props.chatId) })
const workflows = useQuery({ queryKey: computed(() => ['workflows', props.chatId]), queryFn: () => illustrationApi.workflows({ chatId: props.chatId }) })
const options = useQuery({ queryKey: computed(() => ['focus-options', props.chatId]), queryFn: () => illustrationApi.focusOptions(props.chatId) })

const form = reactive({ mode: 'off' as IllustrationMode, image_workflow_id: '', model_config_id: '', focus: [] as string[] })
function fill(s: IllustrationSettings | undefined) {
  if (!s) return
  form.mode = s.mode ?? 'off'
  form.image_workflow_id = s.image_workflow_id ?? ''
  form.model_config_id = s.model_config_id ?? ''
  form.focus = [...(s.focus ?? [])]
}
watch(() => settings.data.value, fill, { immediate: true })

const body = computed<IllustrationSettings>(() => ({
  mode: form.mode, image_workflow_id: form.image_workflow_id || null, model_config_id: form.model_config_id || null, focus: form.focus,
}))
const dirty = computed(() => {
  const s = settings.data.value
  return !!s && JSON.stringify(body.value) !== JSON.stringify({
    mode: s.mode, image_workflow_id: s.image_workflow_id ?? null, model_config_id: s.model_config_id ?? null, focus: s.focus ?? [],
  })
})
const incomplete = computed(() => form.mode !== 'off' && (!form.image_workflow_id || !form.model_config_id))
const selected = computed(() => workflows.data.value?.find((w) => w.id === form.image_workflow_id))

const saving = ref(false)
const error = ref<unknown>(null)
async function save() {
  saving.value = true
  error.value = null
  try {
    qc.setQueryData(['illustration-settings', props.chatId], await illustrationApi.putSettings(props.chatId, body.value))
    toast('插图设置已保存')
  } catch (e) {
    error.value = e
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="stack">
    <h3>插图</h3>
    <ErrorBox v-if="settings.error.value" :error="settings.error.value" title="读取失败" />
    <div class="field">
      <label>生成时机</label>
      <select v-model="form.mode" class="select">
        <option v-for="(label, mode) in MODE_LABELS" :key="mode" :value="mode">{{ label }}</option>
      </select>
      <span class="hint">回合归档完成后在后台生成，不会阻塞下一回合。除“关闭”外都可以在回合下方手动生成。</span>
    </div>
    <template v-if="form.mode !== 'off'">
      <div class="field">
        <label>图像工作流</label>
        <select v-model="form.image_workflow_id" class="select">
          <option value="">（未选择）</option>
          <option v-for="w in workflows.data.value" :key="w.id" :value="w.id">{{ w.name }} · {{ w.image_inputs.length ? '图生图' : '文生图' }} · {{ w.width }}×{{ w.height }}</option>
        </select>
        <span v-if="!workflows.data.value?.length" class="hint">本聊天还没有图像工作流，可以在“资源”标签中从资源库导入。</span>
        <span v-if="selected?.image_inputs.length" class="hint">这个工作流需要 {{ selected.image_inputs.length }} 张参考图，按主要人物的顺序对应；缺少时该次生成会报错。</span>
      </div>
      <div class="field">
        <label>提示词模型</label>
        <select v-model="form.model_config_id" class="select">
          <option value="">（未选择）</option>
          <option v-for="m in modelConfigs" :key="m.id" :value="m.id">{{ m.name }} · {{ m.model }}</option>
        </select>
      </div>
      <div class="field">
        <label>主要人物</label>
        <FocusPicker v-if="options.data.value" v-model="form.focus" :options="options.data.value" />
        <span class="hint">人物来自角色卡的“画像”标签。生成时也可以为单次更换。</span>
      </div>
      <p v-if="incomplete" class="hint warn">选择工作流和提示词模型后才会生成插图。</p>
    </template>
    <ErrorBox v-if="error" :error="error" title="保存失败" />
    <div class="row">
      <span class="spacer" />
      <button class="btn" type="button" :disabled="!dirty" @click="fill(settings.data.value)">还原</button>
      <button class="btn primary" type="button" :disabled="!dirty || saving" @click="save"><Save /> 保存插图设置</button>
    </div>
  </div>
</template>

<style scoped>
.warn { color: var(--warn); }
</style>
