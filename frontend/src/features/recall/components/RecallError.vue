<script setup lang="ts">
import type { RoundFlow } from '@/composables/roundFlow'
import ErrorBox from '@/components/ErrorBox.vue'

/** Recall failed: nothing has been written yet, so the user chooses how to go on. */
defineProps<{ error: unknown; flow: RoundFlow }>()
</script>

<template>
  <ErrorBox :error="error" title="记忆召回失败">
    <p class="hint">还没有开始写作，输入内容已保留。</p>
    <p class="row wrap">
      <button class="btn primary small" type="button" @click="flow.generate()">重试召回</button>
      <button class="btn small" type="button" @click="flow.generate({ skipPrepare: true })">不召回，直接写作</button>
    </p>
  </ErrorBox>
</template>
