<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { Save, Trash2 } from 'lucide-vue-next'
import { api, type ChatTemplate } from '@/api/endpoints'
import ChatParamsFields from '../ChatParamsFields.vue'
import ErrorBox from '../ErrorBox.vue'
import { toast } from '@/composables/toast'

const props = defineProps<{ id: string | null }>()
const emit = defineEmits<{ saved: [id: string]; deleted: [] }>()
const qc = useQueryClient()

const presets = useQuery({ queryKey: ['presets', null], queryFn: () => api.presets({ chatId: null }) })
const models = useQuery({ queryKey: ['models', null], queryFn: () => api.models({ chatId: null }) })

const original = ref<ChatTemplate | null>(null)
const loaded = ref(false)
const name = ref('')
const isDefault = ref(false)
const params = ref<InstanceType<typeof ChatParamsFields>>()
const loadError = ref<unknown>(null)
const saveError = ref<unknown>(null)
const saving = ref(false)
const ready = computed(() => loaded.value && !presets.isPending.value && !models.isPending.value)

watch(() => props.id, async () => {
  loaded.value = false
  loadError.value = null
  saveError.value = null
  original.value = null
  name.value = ''
  isDefault.value = false
  if (props.id) {
    try {
      const found = (await api.chatTemplates()).find((t) => t.id === props.id)
      if (!found) throw new Error('配置不存在')
      original.value = found
      name.value = found.name
      isDefault.value = found.is_default
    } catch (e) {
      loadError.value = e
      return
    }
  }
  loaded.value = true
}, { immediate: true })

async function save() {
  saving.value = true
  saveError.value = null
  try {
    const body = { name: name.value.trim(), is_default: isDefault.value, settings: params.value!.snapshot() }
    const saved = original.value
      ? await api.patchChatTemplate(original.value.id, body)
      : await api.createChatTemplate(body)
    original.value = saved
    qc.invalidateQueries({ queryKey: ['chat-templates'] })
    toast('配置已保存')
    emit('saved', saved.id)
  } catch (e) {
    saveError.value = e
  } finally {
    saving.value = false
  }
}

async function remove() {
  if (!original.value || !confirm('删除这个配置？')) return
  try {
    await api.deleteChatTemplate(original.value.id)
    qc.invalidateQueries({ queryKey: ['chat-templates'] })
    toast('已删除')
    emit('deleted')
  } catch (e) {
    saveError.value = e
  }
}
</script>

<template>
  <div class="stack">
    <p class="hint">新建聊天时选择配置，即可预填以下参数；角色、用户身份和开场每次单独选择。配置只保存资源库条目的引用，被删除的条目会在使用时忽略。</p>
    <ErrorBox v-if="loadError" :error="loadError" title="读取失败" />
    <template v-else-if="ready">
      <div class="grid-2">
        <div class="field"><label>名称</label><input v-model="name" class="input" /></div>
        <div class="field">
          <label>默认</label>
          <label class="check"><input v-model="isDefault" type="checkbox" /> 新建聊天时默认选中</label>
        </div>
      </div>
      <ChatParamsFields
        ref="params" :presets="presets.data.value ?? []" :models="models.data.value ?? []"
        :initial="original?.settings ?? null"
      />
      <ErrorBox v-if="saveError" :error="saveError" title="保存失败" />
      <div class="row">
        <button v-if="original" class="btn danger" type="button" @click="remove"><Trash2 /> 删除</button>
        <span class="spacer" />
        <button class="btn primary" type="button" :disabled="saving || !name.trim()" @click="save">
          <Save /> {{ saving ? '保存中…' : '保存' }}
        </button>
      </div>
    </template>
  </div>
</template>
