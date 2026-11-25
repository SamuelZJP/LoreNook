import { computed, reactive, ref, watch, type Ref } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { useRouter } from 'vue-router'
import { api } from '@/api/endpoints'
import type ChatParamsFields from '@/components/ChatParamsFields.vue'
import { toast } from './toast'

const LAST_IDENTITY = 'lorenook.lastIdentity'

/**
 * Starting a chat from one character: scene, identity (the last one used by default),
 * title and the parameters, which start from the default chat template.
 */
export function useChatStart(characterId: Ref<string>) {
  const router = useRouter()
  const qc = useQueryClient()

  const characters = useQuery({ queryKey: ['characters'], queryFn: api.characters })
  const identities = useQuery({ queryKey: ['identities'], queryFn: api.identities })
  const presets = useQuery({ queryKey: ['presets', null], queryFn: () => api.presets({ chatId: null }) })
  const models = useQuery({ queryKey: ['models', null], queryFn: () => api.models({ chatId: null }) })
  const templates = useQuery({ queryKey: ['chat-templates'], queryFn: api.chatTemplates })

  const character = computed(() => characters.data.value?.find((c) => c.id === characterId.value) ?? null)
  const scenes = computed(() => character.value?.scenes ?? [])
  const form = reactive({ title: '', scene_id: '', user_identity_id: '' })
  const titleTouched = ref(false)
  const params = ref<InstanceType<typeof ChatParamsFields>>()

  watch(scenes, (list) => {
    if (!list.some((s) => s.id === form.scene_id)) form.scene_id = list[0]?.id ?? ''
  }, { immediate: true })
  watch(character, (c) => {
    if (!titleTouched.value) form.title = c?.name ?? ''
  }, { immediate: true })
  watch(() => identities.data.value, (list) => {
    if (!list?.length || list.some((i) => i.id === form.user_identity_id)) return
    const last = localStorage.getItem(LAST_IDENTITY)
    form.user_identity_id = list.find((i) => i.id === last)?.id ?? list[0].id
  }, { immediate: true })

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

  const create = useMutation({
    mutationFn: () => {
      const { features: _, ...settings } = params.value!.snapshot()
      return api.createChat({
        title: form.title.trim() || character.value?.name || '新聊天',
        character_id: characterId.value,
        scene_id: form.scene_id || null,
        user_identity_id: form.user_identity_id,
        ...settings,
      })
    },
    onSuccess: async (chat) => {
      localStorage.setItem(LAST_IDENTITY, form.user_identity_id)
      qc.invalidateQueries({ queryKey: ['chats'] })
      for (const error of await params.value!.applyFeatures(chat.id)) toast(error, 'error')
      router.push(`/chats/${chat.id}`)
    },
  })
  const canStart = computed(() => !!params.value && !!characterId.value && !!form.user_identity_id && !create.isPending.value)

  const saveAs = reactive({ name: '', is_default: false })
  const saveTemplate = useMutation({
    mutationFn: () => api.createChatTemplate({
      name: saveAs.name.trim(), is_default: saveAs.is_default, settings: params.value!.snapshot(),
    }),
    onSuccess: (saved) => {
      qc.invalidateQueries({ queryKey: ['chat-templates'] })
      toast('模板已保存')
      saveAs.name = ''
      saveAs.is_default = false
      templateId.value = saved.id
    },
  })

  return {
    characters, identities, presets, models, templates, character, scenes, form, titleTouched, params,
    templateId, template, paramsReady, create, canStart, saveAs, saveTemplate,
  }
}
