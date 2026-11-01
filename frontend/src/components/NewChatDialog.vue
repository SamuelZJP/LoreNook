<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { useRouter } from 'vue-router'
import { api, MODEL_PURPOSES, type ModelPurpose } from '@/api/endpoints'
import { PURPOSE_LABELS } from '@/lib/archive'
import ModalDialog from './ModalDialog.vue'
import ProfilePicker from './ProfilePicker.vue'
import ErrorBox from './ErrorBox.vue'
import NewChatIllustrationSection from '@/features/illustrations/components/NewChatIllustrationSection.vue'
import NewChatRecallSection from '@/features/recall/components/NewChatRecallSection.vue'
import { toast } from '@/composables/toast'

const emit = defineEmits<{ close: [] }>()
const router = useRouter()
const qc = useQueryClient()

const characters = useQuery({ queryKey: ['characters'], queryFn: api.characters })
const identities = useQuery({ queryKey: ['identities'], queryFn: api.identities })
const presets = useQuery({ queryKey: ['presets', null], queryFn: () => api.presets({ chatId: null }) })
const models = useQuery({ queryKey: ['models', null], queryFn: () => api.models({ chatId: null }) })

const form = reactive({
  title: '',
  character_id: '',
  scene_id: '',
  user_identity_id: '',
  writing_preset_id: '' as string,
  extraPresets: [] as string[],
  bindings: { writing: '', state_update: '', round_summary: '', episode_summary: '' } as Record<ModelPurpose, string>,
  extraModels: [] as string[],
  recent_rounds: 5,
  min_summaries: 6,
})
const titleTouched = ref(false)
const illustrationSection = ref<InstanceType<typeof NewChatIllustrationSection>>()
const recallSection = ref<InstanceType<typeof NewChatRecallSection>>()

watch(() => characters.data.value, (list) => {
  if (list?.length && !form.character_id) form.character_id = list[0].id
}, { immediate: true })
watch(() => identities.data.value, (list) => {
  if (list?.length && !form.user_identity_id) form.user_identity_id = list[0].id
}, { immediate: true })
watch(() => presets.data.value, (list) => {
  if (list?.length && !form.writing_preset_id) form.writing_preset_id = list[0].id
}, { immediate: true })
watch(() => models.data.value, (list) => {
  if (list?.length === 1) for (const p of MODEL_PURPOSES) form.bindings[p] ||= list[0].id
}, { immediate: true })
const scenes = computed(() => characters.data.value?.find((c) => c.id === form.character_id)?.scenes ?? [])
const selectedScene = computed(() => scenes.value.find((s) => s.id === form.scene_id))
watch(scenes, (list) => {
  if (!list.some((s) => s.id === form.scene_id)) form.scene_id = list[0]?.id ?? ''
}, { immediate: true })
watch(() => form.character_id, (id) => {
  if (titleTouched.value) return
  form.title = characters.data.value?.find((c) => c.id === id)?.name ?? ''
}, { immediate: true })

const selectedPreset = computed(() => presets.data.value?.find((p) => p.id === form.writing_preset_id))
const writingModel = computed(() => models.data.value?.find((m) => m.id === form.bindings.writing))
const missing = computed(() => !characters.data.value?.length || !identities.data.value?.length)

const create = useMutation({
  mutationFn: () => {
    const model_bindings: Partial<Record<ModelPurpose, string>> = {}
    for (const p of MODEL_PURPOSES) if (form.bindings[p]) model_bindings[p] = form.bindings[p]
    return api.createChat({
      title: form.title.trim(),
      character_id: form.character_id,
      scene_id: form.scene_id || null,
      user_identity_id: form.user_identity_id,
      writing_preset_id: form.writing_preset_id || null,
      writing_preset_ids: form.extraPresets,
      model_config_ids: form.extraModels,
      model_bindings,
      recent_rounds: form.recent_rounds,
      min_summaries: form.min_summaries,
    })
  },
  onSuccess: async (chat) => {
    qc.invalidateQueries({ queryKey: ['chats'] })
    toast('聊天已创建')
    try {
      await illustrationSection.value?.apply(chat.id)
    } catch (e) {
      toast(`插图设置未保存：${e instanceof Error ? e.message : String(e)}`, 'error')
    }
    try {
      await recallSection.value?.apply(chat.id)
    } catch (e) {
      toast(`记忆召回设置未保存：${e instanceof Error ? e.message : String(e)}`, 'error')
    }
    emit('close')
    router.push(`/chats/${chat.id}`)
  },
})
</script>

<template>
  <ModalDialog title="新建聊天" width="620px" @close="emit('close')">
    <div class="stack">
      <p class="hint">创建时会把所选角色、身份、定义、预设和模型配置复制为本聊天独立的副本。之后修改资源库不会影响这个聊天。</p>
      <div v-if="missing && !characters.isLoading.value && !identities.isLoading.value" class="notice">
        需要先在资源库中创建至少一个角色和一个用户身份。
        <RouterLink to="/library/characters" @click="emit('close')">前往资源库</RouterLink>
      </div>
      <div class="grid-2">
        <div class="field">
          <label>角色</label>
          <ProfilePicker v-model="form.character_id" :items="characters.data.value ?? []" label="角色" />
        </div>
        <div class="field">
          <label>用户身份</label>
          <ProfilePicker v-model="form.user_identity_id" :items="identities.data.value ?? []" label="用户身份" />
        </div>
      </div>
      <div v-if="scenes.length > 1" class="field">
        <label>开场</label>
        <select v-model="form.scene_id" class="select">
          <option v-for="s in scenes" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        <span v-if="selectedScene?.description" class="hint">{{ selectedScene.description }}</span>
      </div>
      <div class="field">
        <label>标题</label>
        <input v-model="form.title" class="input" @input="titleTouched = true" />
      </div>

      <h3>写作预设</h3>
      <div class="field">
        <label>使用的预设</label>
        <select v-model="form.writing_preset_id" class="select">
          <option value="">（暂不选择）</option>
          <option v-for="p in presets.data.value" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
      </div>
      <details v-if="(presets.data.value?.length ?? 0) > 1">
        <summary class="label">同时复制其他预设</summary>
        <div class="row wrap checks">
          <label v-for="p in presets.data.value" v-show="p.id !== form.writing_preset_id" :key="p.id" class="check">
            <input v-model="form.extraPresets" type="checkbox" :value="p.id" /> {{ p.name }}
          </label>
        </div>
      </details>

      <h3>模型绑定</h3>
      <p v-if="!models.data.value?.length" class="hint">资源库中还没有模型配置，可以稍后在聊天设置中添加。</p>
      <div class="grid-2">
        <div v-for="p in MODEL_PURPOSES" :key="p" class="field">
          <label>{{ PURPOSE_LABELS[p] }}</label>
          <select v-model="form.bindings[p]" class="select">
            <option value="">（未绑定）</option>
            <option v-for="m in models.data.value" :key="m.id" :value="m.id">{{ m.name }} · {{ m.model }}</option>
          </select>
        </div>
      </div>
      <p v-if="selectedPreset && writingModel" class="hint">
        写作模型 API 类型：<code>{{ writingModel.api_type }}</code>。预设构建的请求必须使用相同的 API 类型。
      </p>
      <details v-if="(models.data.value?.length ?? 0) > 1">
        <summary class="label">额外复制未绑定的模型配置</summary>
        <div class="row wrap checks">
          <label v-for="m in models.data.value" :key="m.id" class="check">
            <input v-model="form.extraModels" type="checkbox" :value="m.id" /> {{ m.name }}
          </label>
        </div>
      </details>

      <NewChatRecallSection ref="recallSection" :models="models.data.value ?? []" />
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
      <ErrorBox v-if="create.error.value" :error="create.error.value" title="创建失败" />
    </div>
    <template #footer>
      <button class="btn" type="button" @click="emit('close')">取消</button>
      <button
        class="btn primary" type="button"
        :disabled="create.isPending.value || !form.title.trim() || !form.character_id || !form.user_identity_id"
        @click="create.mutate()"
      >{{ create.isPending.value ? '创建中…' : '创建' }}</button>
    </template>
  </ModalDialog>
</template>

<style scoped>
h3 { margin-top: 4px; }
.notice { padding: 10px 12px; border-radius: var(--radius-m); background: var(--warn-soft); }
.checks { padding: 8px 0; gap: 14px; }
summary { cursor: pointer; }
</style>
