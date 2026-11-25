<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { useRouter } from 'vue-router'
import { TriangleAlert, Upload } from 'lucide-vue-next'
import { api, type CardSummary } from '@/api/endpoints'
import { toast } from '@/composables/toast'
import ModalDialog from '../ModalDialog.vue'
import ErrorBox from '../ErrorBox.vue'

/** Pick a card file, show what it brings in, then import it as a new library character. */
const qc = useQueryClient()
const router = useRouter()
const input = ref<HTMLInputElement>()
const file = ref<File | null>(null)
const summary = ref<CardSummary | null>(null)
const keepCode = ref(false)
const busy = ref(false)
const error = ref<unknown>(null)

const code = computed(() => {
  const s = summary.value
  if (!s) return ''
  return [s.has_state_schema && '状态 Schema ', s.has_state_script && '状态脚本'].filter(Boolean).join('和').trim()
})

async function choose(e: Event) {
  const picked = (e.target as HTMLInputElement).files?.[0]
  if (input.value) input.value.value = ''
  if (!picked) return
  busy.value = true
  try {
    summary.value = await api.inspectCard(picked)
    file.value = picked
    keepCode.value = false
    error.value = null
  } catch (err) {
    toast(err instanceof Error ? err.message : String(err), 'error')
  } finally {
    busy.value = false
  }
}

function close() {
  file.value = null
  summary.value = null
  error.value = null
}

async function confirm() {
  if (!file.value) return
  busy.value = true
  error.value = null
  try {
    const character = await api.importCard(file.value, keepCode.value)
    await qc.invalidateQueries({ queryKey: ['characters'] })
    toast(`已导入「${character.name}」`)
    close()
    router.push(`/library/characters/${character.id}`)
  } catch (err) {
    error.value = err
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <button class="btn" type="button" :disabled="busy" @click="input?.click()"><Upload /> 导入角色卡</button>
  <input ref="input" type="file" accept=".lorenook,application/zip" hidden @change="choose" />

  <ModalDialog v-if="summary" title="导入角色卡" :dismissable="!busy" @close="close">
    <div class="stack">
      <p>
        <strong>{{ summary.name }}</strong>
        <span class="muted"> · {{ summary.scenes }} 个开场</span>
      </p>
      <p class="muted">导入后会成为资源库里的一个新角色，不会覆盖已有角色。</p>

      <div v-if="code" class="risk stack tight">
        <div class="row tight"><TriangleAlert class="ic" /><strong>这张卡带有{{ code }}</strong></div>
        <p>它们是不受限制的 Python，会在服务器上运行，可以读写文件、访问网络。只保留你信任的来源。</p>
        <label class="check"><input v-model="keepCode" type="checkbox" /> 保留代码</label>
        <p v-if="!keepCode && summary.has_state_schema" class="hint">
          不保留时，开场的初始变量不会校验；补上状态 Schema 后才能用它开始聊天。
        </p>
      </div>

      <p v-if="summary.unknown_features.length" class="hint warn">
        以下功能数据当前未安装，将被忽略：{{ summary.unknown_features.join('、') }}
      </p>
      <ErrorBox v-if="error" :error="error" title="导入失败" />
    </div>
    <template #footer>
      <button class="btn" type="button" :disabled="busy" @click="close">取消</button>
      <button class="btn primary" type="button" :disabled="busy" @click="confirm">{{ busy ? '导入中…' : '导入' }}</button>
    </template>
  </ModalDialog>
</template>

<style scoped>
.risk { padding: var(--space-3) var(--space-4); border-radius: var(--radius-m); background: var(--warn-soft); }
.risk .ic { width: 16px; height: 16px; color: var(--warn); flex-shrink: 0; }
.tight { gap: var(--space-1-5); }
</style>
