<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { MODEL_PURPOSES, type ChatTemplateSettings, type ModelConfig, type ModelPurpose, type Preset } from '@/api/endpoints'
import { PURPOSE_LABELS } from '@/lib/archive'
import NewChatIllustrationSection from '@/features/illustrations/components/NewChatIllustrationSection.vue'
import NewChatRecallSection from '@/features/recall/components/NewChatRecallSection.vue'

/**
 * A new chat's parameters: everything except character, identity, scene and title.
 * Shared by the new-chat dialog and the chat-template editor. `initial` is read once on mount;
 * `null` means no template, which picks the first preset and binds a lone model everywhere.
 */
const props = defineProps<{ presets: Preset[]; models: ModelConfig[]; initial: ChatTemplateSettings | null }>()

const form = reactive({
  writing_preset_id: '',
  writing_preset_ids: [] as string[],
  bindings: { writing: '', state_update: '', round_summary: '', episode_summary: '' } as Record<ModelPurpose, string>,
  model_config_ids: [] as string[],
  recent_rounds: 5,
  min_summaries: 6,
})
/** How many library references in `initial` no longer exist and were dropped. */
const dropped = ref(0)
const illustrationSection = ref<InstanceType<typeof NewChatIllustrationSection>>()
const recallSection = ref<InstanceType<typeof NewChatRecallSection>>()

const selectedPreset = computed(() => props.presets.find((p) => p.id === form.writing_preset_id))
const writingModel = computed(() => props.models.find((m) => m.id === form.bindings.writing))

onMounted(() => {
  const initial = props.initial
  if (!initial) {
    form.writing_preset_id = props.presets[0]?.id ?? ''
    if (props.models.length === 1) for (const p of MODEL_PURPOSES) form.bindings[p] = props.models[0].id
    return
  }
  const presetIds = new Set(props.presets.map((p) => p.id))
  const modelIds = new Set(props.models.map((m) => m.id))
  let missing = 0
  const keep = (id: string | null | undefined, ids: Set<string>) => {
    if (!id) return ''
    if (ids.has(id)) return id
    missing++
    return ''
  }
  form.writing_preset_id = keep(initial.writing_preset_id, presetIds)
  form.writing_preset_ids = (initial.writing_preset_ids ?? []).map((id) => keep(id, presetIds)).filter(Boolean)
  for (const p of MODEL_PURPOSES) form.bindings[p] = keep(initial.model_bindings?.[p], modelIds)
  form.model_config_ids = (initial.model_config_ids ?? []).map((id) => keep(id, modelIds)).filter(Boolean)
  form.recent_rounds = initial.recent_rounds ?? 5
  form.min_summaries = initial.min_summaries ?? 6
  dropped.value = missing
  recallSection.value?.restore(initial.features?.recall)
  illustrationSection.value?.restore(initial.features?.illustrations)
})

function snapshot(): ChatTemplateSettings {
  const model_bindings: Partial<Record<ModelPurpose, string>> = {}
  for (const p of MODEL_PURPOSES) if (form.bindings[p]) model_bindings[p] = form.bindings[p]
  return {
    writing_preset_id: form.writing_preset_id || null,
    writing_preset_ids: form.writing_preset_ids.filter((id) => id !== form.writing_preset_id),
    model_config_ids: [...form.model_config_ids],
    model_bindings,
    recent_rounds: form.recent_rounds,
    min_summaries: form.min_summaries,
    features: {
      recall: recallSection.value?.snapshot() ?? {},
      illustrations: illustrationSection.value?.snapshot() ?? {},
    },
  }
}

/** Applies the feature settings once the chat exists; each failure is reported, none stops the others. */
async function applyFeatures(chatId: string): Promise<string[]> {
  const errors: string[] = []
  const steps: [string, (() => Promise<unknown>) | undefined][] = [
    ['插图设置', illustrationSection.value && (() => illustrationSection.value!.apply(chatId))],
    ['记忆召回设置', recallSection.value && (() => recallSection.value!.apply(chatId))],
  ]
  for (const [label, run] of steps) {
    try {
      await run?.()
    } catch (e) {
      errors.push(`${label}未保存：${e instanceof Error ? e.message : String(e)}`)
    }
  }
  return errors
}

defineExpose({ snapshot, applyFeatures })
</script>

<template>
  <div class="stack">
    <p v-if="dropped" class="hint warn">配置引用的 {{ dropped }} 项预设或模型已从资源库删除，已忽略。</p>

    <h3>写作预设</h3>
    <div class="field">
      <label>使用的预设</label>
      <select v-model="form.writing_preset_id" class="select">
        <option value="">（暂不选择）</option>
        <option v-for="p in presets" :key="p.id" :value="p.id">{{ p.name }}</option>
      </select>
    </div>
    <details v-if="presets.length > 1">
      <summary class="label">同时复制其他预设</summary>
      <div class="row wrap checks">
        <label v-for="p in presets" v-show="p.id !== form.writing_preset_id" :key="p.id" class="check">
          <input v-model="form.writing_preset_ids" type="checkbox" :value="p.id" /> {{ p.name }}
        </label>
      </div>
    </details>

    <h3>模型绑定</h3>
    <p v-if="!models.length" class="hint">资源库中还没有模型配置，可以稍后在聊天设置中添加。</p>
    <div class="grid-2">
      <div v-for="p in MODEL_PURPOSES" :key="p" class="field">
        <label>{{ PURPOSE_LABELS[p] }}</label>
        <select v-model="form.bindings[p]" class="select">
          <option value="">（未绑定）</option>
          <option v-for="m in models" :key="m.id" :value="m.id">{{ m.name }} · {{ m.model }}</option>
        </select>
      </div>
    </div>
    <p v-if="selectedPreset && writingModel" class="hint">
      写作模型 API 类型：<code>{{ writingModel.api_type }}</code>。预设构建的请求必须使用相同的 API 类型。
    </p>
    <details v-if="models.length > 1">
      <summary class="label">额外复制未绑定的模型配置</summary>
      <div class="row wrap checks">
        <label v-for="m in models" :key="m.id" class="check">
          <input v-model="form.model_config_ids" type="checkbox" :value="m.id" /> {{ m.name }}
        </label>
      </div>
    </details>

    <NewChatRecallSection ref="recallSection" :models="models" />
    <NewChatIllustrationSection ref="illustrationSection" />

    <h3>记忆</h3>
    <div class="grid-2">
      <div class="field">
        <label>最近完整回合数 X</label>
        <input v-model.number="form.recent_rounds" class="input" type="number" min="0" />
      </div>
      <div class="field">
        <label>最少保留回合摘要数 Y</label>
        <input v-model.number="form.min_summaries" class="input" type="number" min="0" />
      </div>
    </div>
  </div>
</template>

<style scoped>
h3 { margin-top: var(--space-1); }
.checks { padding: var(--space-2) 0; gap: var(--space-4); }
summary { cursor: pointer; }
.warn { color: var(--warn); }
</style>
