<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { useRouter } from 'vue-router'
import { api } from '@/api/endpoints'
import ModalDialog from './ModalDialog.vue'
import ProfilePicker from './ProfilePicker.vue'
import ErrorBox from './ErrorBox.vue'
import ChatParamsFields from './ChatParamsFields.vue'
import { toast } from '@/composables/toast'

const emit = defineEmits<{ close: [] }>()
const router = useRouter()
const qc = useQueryClient()

const characters = useQuery({ queryKey: ['characters'], queryFn: api.characters })
const identities = useQuery({ queryKey: ['identities'], queryFn: api.identities })
const presets = useQuery({ queryKey: ['presets', null], queryFn: () => api.presets({ chatId: null }) })
const models = useQuery({ queryKey: ['models', null], queryFn: () => api.models({ chatId: null }) })
const templates = useQuery({ queryKey: ['chat-templates'], queryFn: api.chatTemplates })

const form = reactive({ title: '', character_id: '', scene_id: '', user_identity_id: '' })
const titleTouched = ref(false)
const params = ref<InstanceType<typeof ChatParamsFields>>()

/** The template the parameters start from; '' starts from built-in defaults. */
const templateId = ref('')
const templatesLoaded = ref(false)
watch(() => templates.data.value, (list) => {
  if (!list || templatesLoaded.value) return
  templatesLoaded.value = true
  templateId.value = list.find((t) => t.is_default)?.id ?? ''
}, { immediate: true })
const template = computed(() => templates.data.value?.find((t) => t.id === templateId.value) ?? null)
// Parameters mount once their lists are known, so a template's references can be checked.
const paramsReady = computed(() => !presets.isPending.value && !models.isPending.value
  && (templatesLoaded.value || templates.isError.value))

watch(() => characters.data.value, (list) => {
  if (list?.length && !form.character_id) form.character_id = list[0].id
}, { immediate: true })
watch(() => identities.data.value, (list) => {
  if (list?.length && !form.user_identity_id) form.user_identity_id = list[0].id
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

const missing = computed(() => !characters.data.value?.length || !identities.data.value?.length)

const create = useMutation({
  mutationFn: () => {
    const { features: _, ...settings } = params.value!.snapshot()
    return api.createChat({
      title: form.title.trim(),
      character_id: form.character_id,
      scene_id: form.scene_id || null,
      user_identity_id: form.user_identity_id,
      ...settings,
    })
  },
  onSuccess: async (chat) => {
    qc.invalidateQueries({ queryKey: ['chats'] })
    toast('聊天已创建')
    for (const error of await params.value!.applyFeatures(chat.id)) toast(error, 'error')
    emit('close')
    router.push(`/chats/${chat.id}`)
  },
})

const saveAs = reactive({ name: '', is_default: false })
const saveTemplate = useMutation({
  mutationFn: () => api.createChatTemplate({
    name: saveAs.name.trim(), is_default: saveAs.is_default, settings: params.value!.snapshot(),
  }),
  onSuccess: (saved) => {
    qc.invalidateQueries({ queryKey: ['chat-templates'] })
    toast('配置已保存')
    saveAs.name = ''
    saveAs.is_default = false
    templateId.value = saved.id
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
      <div v-if="templates.data.value?.length" class="field">
        <label>配置</label>
        <select v-model="templateId" class="select">
          <option value="">（默认值）</option>
          <option v-for="t in templates.data.value" :key="t.id" :value="t.id">{{ t.name }}{{ t.is_default ? '（默认）' : '' }}</option>
        </select>
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

      <details class="params">
        <summary class="label">参数<span class="faint"> · {{ template?.name ?? '默认值' }}</span></summary>
        <div v-if="paramsReady" class="stack params-body">
          <ChatParamsFields
            ref="params" :key="templateId"
            :presets="presets.data.value ?? []" :models="models.data.value ?? []" :initial="template?.settings ?? null"
          />
          <div class="save-as">
            <h3>另存为配置</h3>
            <div class="row wrap">
              <input v-model="saveAs.name" class="input grow" placeholder="配置名称" />
              <label class="check"><input v-model="saveAs.is_default" type="checkbox" /> 设为默认</label>
              <button
                class="btn small" type="button" :disabled="!saveAs.name.trim() || saveTemplate.isPending.value"
                @click="saveTemplate.mutate()"
              >保存</button>
            </div>
            <ErrorBox v-if="saveTemplate.error.value" :error="saveTemplate.error.value" title="配置保存失败" />
          </div>
        </div>
      </details>
      <ErrorBox v-if="create.error.value" :error="create.error.value" title="创建失败" />
    </div>
    <template #footer>
      <button class="btn" type="button" @click="emit('close')">取消</button>
      <button
        class="btn primary" type="button"
        :disabled="create.isPending.value || !params || !form.title.trim() || !form.character_id || !form.user_identity_id"
        @click="create.mutate()"
      >{{ create.isPending.value ? '创建中…' : '创建' }}</button>
    </template>
  </ModalDialog>
</template>

<style scoped>
h3 { margin-top: 4px; }
.notice { padding: 10px 12px; border-radius: var(--radius-m); background: var(--warn-soft); }
summary { cursor: pointer; }
.params-body { padding-top: 10px; }
.save-as { border-top: 1px solid var(--border); padding-top: 12px; }
.save-as .row { gap: 10px; align-items: center; }
</style>
