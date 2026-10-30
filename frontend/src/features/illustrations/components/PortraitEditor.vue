<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { Plus, Save, Trash2, ChevronUp, ChevronDown } from 'lucide-vue-next'
import ErrorBox from '@/components/ErrorBox.vue'
import ImageUpload from '@/components/ImageUpload.vue'
import { toast } from '@/composables/toast'
import { illustrationApi } from '../api'
import { mediaUrl } from '../lib'

/** The "画像" tab of a profile: a cast on a character, an appearance on a user identity. */
const props = defineProps<{ kind: 'character' | 'identity'; ownerId: string; chatId: string | null }>()
const qc = useQueryClient()

const owner = computed(() => {
  if (props.chatId) return `/api/chats/${props.chatId}`
  return props.kind === 'character' ? `/api/characters/${props.ownerId}` : `/api/user-identities/${props.ownerId}`
})

interface Draft { key: string; id: string | null; name: string; appearance: string; reference_image: string | null }
let nextKey = 0
const toDraft = (m: { id?: string | null; name: string; appearance?: string; reference_image?: string | null }): Draft =>
  ({ key: `k${nextKey++}`, id: m.id ?? null, name: m.name, appearance: m.appearance ?? '', reference_image: m.reference_image ?? null })

const cast = ref<Draft[]>([])
const look = ref({ appearance: '', reference_image: null as string | null })
const loaded = ref('')
const loadError = ref<unknown>(null)
const saveError = ref<unknown>(null)
const saving = ref(false)
const snapshot = () => JSON.stringify(props.kind === 'character'
  ? cast.value.map(({ id, name, appearance, reference_image }) => ({ id, name, appearance, reference_image })) : look.value)
const dirty = computed(() => snapshot() !== loaded.value)
const invalid = computed(() => props.kind === 'character' && cast.value.some((m) => !m.name.trim()))

async function load() {
  loadError.value = null
  try {
    if (props.kind === 'character') cast.value = (await illustrationApi.cast(owner.value)).map(toDraft)
    else {
      const a = await illustrationApi.appearance(owner.value)
      look.value = { appearance: a.appearance ?? '', reference_image: a.reference_image ?? null }
    }
    loaded.value = snapshot()
  } catch (e) {
    loadError.value = e
  }
}
watch(owner, load, { immediate: true })

function move(i: number, step: number) {
  const list = [...cast.value]
  const [item] = list.splice(i, 1)
  list.splice(i + step, 0, item)
  cast.value = list
}

async function save() {
  saving.value = true
  saveError.value = null
  try {
    if (props.kind === 'character') {
      const members = await illustrationApi.putCast(owner.value, cast.value.map(({ id, name, appearance, reference_image }) => ({ id, name, appearance, reference_image })))
      cast.value = members.map(toDraft)
    } else {
      await illustrationApi.putAppearance(owner.value, look.value)
    }
    loaded.value = snapshot()
    if (props.chatId) qc.invalidateQueries({ queryKey: ['focus-options', props.chatId] })
    toast('画像已保存')
  } catch (e) {
    saveError.value = e
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="stack">
    <ErrorBox v-if="loadError" :error="loadError" title="读取失败" />
    <template v-else-if="kind === 'character'">
      <p class="hint">
        画面里可能出现的人物。多主角的角色卡（例如“ABC 学园”）应在这里列出每位主角。第一位是默认的主要人物；没有人物时默认使用角色卡本身。
        外貌用简洁的视觉描述即可，提示词模板会让模型改写成工作流需要的风格。
      </p>
      <div v-for="(m, i) in cast" :key="m.key" class="card card-pad member">
        <ImageUpload v-model="m.reference_image" label="参考图" :url-of="mediaUrl" />
        <div class="grow stack tight">
          <div class="row">
            <input v-model="m.name" class="input grow" placeholder="姓名" aria-label="姓名" />
            <button class="btn ghost icon small" type="button" aria-label="上移" :disabled="i === 0" @click="move(i, -1)"><ChevronUp /></button>
            <button class="btn ghost icon small" type="button" aria-label="下移" :disabled="i === cast.length - 1" @click="move(i, 1)"><ChevronDown /></button>
            <button class="btn ghost icon small danger" type="button" aria-label="删除人物" @click="cast.splice(i, 1)"><Trash2 /></button>
          </div>
          <textarea v-model="m.appearance" class="textarea" rows="3" placeholder="外貌：发型、发色、瞳色、体型、常穿的衣服…" aria-label="外貌" />
        </div>
      </div>
      <div class="row"><button class="btn small" type="button" @click="cast.push(toDraft({ name: '' }))"><Plus /> 添加人物</button></div>
    </template>
    <template v-else>
      <p class="hint">用户身份入画时使用的外貌。可在聊天的插图设置中把用户身份选为主要人物。</p>
      <div class="card card-pad member">
        <ImageUpload v-model="look.reference_image" label="参考图" :url-of="mediaUrl" />
        <textarea v-model="look.appearance" class="textarea grow" rows="4" placeholder="外貌：发型、发色、瞳色、体型、常穿的衣服…" aria-label="外貌" />
      </div>
    </template>
    <ErrorBox v-if="saveError" :error="saveError" title="保存失败" />
    <div class="row">
      <span v-if="invalid" class="hint bad">人物需要姓名</span>
      <span class="spacer" />
      <button class="btn primary" type="button" :disabled="!dirty || invalid || saving" @click="save"><Save /> 保存画像</button>
    </div>
  </div>
</template>

<style scoped>
.member { display: flex; gap: 12px; align-items: flex-start; }
.bad { color: var(--danger); }
@media (max-width: 640px) { .member { flex-direction: column; } .member > .grow { width: 100%; } }
</style>
