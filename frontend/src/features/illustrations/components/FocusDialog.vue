<script setup lang="ts">
import { ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import ModalDialog from '@/components/ModalDialog.vue'
import ErrorBox from '@/components/ErrorBox.vue'
import { illustrationApi } from '../api'
import FocusPicker from './FocusPicker.vue'

/** Pick main characters for one new attempt, without changing the chat's setting. */
const props = defineProps<{ chatId: string; current: { [key: string]: unknown }[] }>()
const emit = defineEmits<{ close: []; confirm: [focus: string[]] }>()
const options = useQuery({
  queryKey: ['focus-options', props.chatId],
  queryFn: () => illustrationApi.focusOptions(props.chatId),
})
const focus = ref(props.current.map((p) => String(p.id)))
</script>

<template>
  <ModalDialog title="换人物重新生成" width="420px" @close="emit('close')">
    <ErrorBox v-if="options.error.value" :error="options.error.value" title="读取失败" />
    <FocusPicker v-else-if="options.data.value" v-model="focus" :options="options.data.value" />
    <template #footer>
      <button class="btn" type="button" @click="emit('close')">取消</button>
      <button class="btn primary" type="button" :disabled="!options.data.value" @click="emit('confirm', focus)">生成</button>
    </template>
  </ModalDialog>
</template>
