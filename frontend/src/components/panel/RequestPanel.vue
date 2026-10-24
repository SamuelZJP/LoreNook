<script setup lang="ts">
import { ref } from 'vue'
import { FileJson } from 'lucide-vue-next'
import { api, type ChatDetail } from '@/api/endpoints'
import type { RoundFlow } from '@/composables/roundFlow'
import ErrorBox from '../ErrorBox.vue'
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
    const r = await api.writingPreview(props.chat.id, props.flow.input.value)
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
      <h3 class="grow">写作请求预览</h3>
      <button class="btn small" type="button" :disabled="building" @click="build"><FileJson /> {{ building ? '构建中…' : '构建预览' }}</button>
    </div>
    <p class="hint">使用当前输入框内容和已选预设构建请求，不调用模型，也不合并模型默认参数。</p>
    <ErrorBox v-if="error" :error="error" title="预览失败" />
    <CodeEditor v-if="preview" :model-value="preview" language="json" readonly min-height="200px" />
  </div>
</template>
