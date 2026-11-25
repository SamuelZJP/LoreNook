<script setup lang="ts">
import { ref } from 'vue'
import { FileJson } from 'lucide-vue-next'
import { api, type ChatDetail } from '@/api/endpoints'
import type { RoundFlow } from '@/composables/roundFlow'
import ErrorBox from '../ErrorBox.vue'
import InfoTip from '../InfoTip.vue'
import CodeEditor from '../CodeEditor.vue'
import { pretty } from '@/lib/format'

const props = defineProps<{ chat: ChatDetail; flow: RoundFlow }>()
const preview = ref<string | null>(null)
const error = ref<unknown>(null)
const building = ref(false)
async function build() {
  error.value = null
  building.value = true
  try {
    const r = await api.writingPreview(props.chat.id, props.flow.input.value, props.flow.instruction.value, props.flow.preparedLayout())
    preview.value = pretty(r.request)
  } catch (e) {
    preview.value = null
    error.value = e
  } finally {
    building.value = false
  }
}
</script>

<template>
  <div class="stack">
    <div class="row">
      <h3>请求预览</h3>
      <InfoTip>用输入框里的内容生成一份将发给模型的请求，只预览，不会真的发送。</InfoTip>
      <span class="grow" />
      <button class="btn small" type="button" :disabled="building" @click="build"><FileJson /> {{ building ? '构建中…' : '构建预览' }}</button>
    </div>
    <ErrorBox v-if="error" :error="error" title="预览失败" />
    <CodeEditor v-if="preview" :model-value="preview" language="json" readonly min-height="200px" />
  </div>
</template>
