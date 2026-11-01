<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { Pencil, Plus, Import } from 'lucide-vue-next'
import ModalDialog from '@/components/ModalDialog.vue'
import { toast } from '@/composables/toast'
import { illustrationApi } from '../api'
import WorkflowEditor from './WorkflowEditor.vue'

/** A chat's own image workflows, for the chat resources panel. */
const props = defineProps<{ chatId: string }>()
const qc = useQueryClient()
const workflows = useQuery({ queryKey: computed(() => ['workflows', props.chatId]), queryFn: () => illustrationApi.workflows({ chatId: props.chatId }) })
const library = useQuery({ queryKey: ['workflows', null], queryFn: () => illustrationApi.workflows({ chatId: null }) })
const settings = useQuery({ queryKey: computed(() => ['illustration-settings', props.chatId]), queryFn: () => illustrationApi.settings(props.chatId) })

const editing = ref<{ id: string | null } | null>(null)
const importing = ref('')
async function importSource() {
  if (!importing.value) return
  try {
    await illustrationApi.importWorkflow(props.chatId, importing.value)
    qc.invalidateQueries({ queryKey: ['workflows', props.chatId] })
    toast('已从资源库导入')
  } catch (e) {
    toast(e instanceof Error ? e.message : String(e), 'error')
  } finally {
    importing.value = ''
  }
}
</script>

<template>
  <div class="row"><h3 class="grow">图像工作流</h3><button class="btn small" type="button" @click="editing = { id: null }"><Plus /> 新增</button></div>
  <div v-if="!workflows.data.value?.length" class="empty">没有图像工作流</div>
  <button v-for="w in workflows.data.value" :key="w.id" class="list-item card" type="button" @click="editing = { id: w.id }">
    <div class="grow">
      <div class="ellipsis">{{ w.name }}</div>
      <div class="faint ellipsis mono small">{{ w.width }}×{{ w.height }}</div>
    </div>
    <span v-if="w.id === settings.data.value?.image_workflow_id" class="badge accent">使用中</span>
    <Pencil class="ic" />
  </button>
  <div v-if="library.data.value?.length" class="row">
    <select v-model="importing" class="select grow" aria-label="从资源库导入图像工作流">
      <option value="">从资源库导入…</option>
      <option v-for="w in library.data.value" :key="w.id" :value="w.id">{{ w.name }}</option>
    </select>
    <button class="btn small" type="button" :disabled="!importing" @click="importSource"><Import /> 导入</button>
  </div>

  <ModalDialog v-if="editing" title="本聊天的图像工作流" width="860px" @close="editing = null">
    <WorkflowEditor :id="editing.id" :chat-id="chatId" @saved="(id) => (editing = { id })" @deleted="editing = null" />
  </ModalDialog>
</template>

<style scoped>
.list-item.card { width: 100%; text-align: left; font: inherit; color: inherit; border: 1px solid var(--border); background: var(--bg-elev); }
.ic { width: 16px; height: 16px; color: var(--text-faint); flex-shrink: 0; }
.small { font-size: 12px; }
</style>
