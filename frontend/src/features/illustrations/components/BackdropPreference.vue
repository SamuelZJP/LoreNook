<script setup lang="ts">
import { illustrationPrefs } from '../lib'
import InfoTip from '@/components/InfoTip.vue'
import Segmented from '@/components/Segmented.vue'

const choices = [
  { value: 'off' as const, label: '关闭' },
  { value: 'subtle' as const, label: '淡' },
  { value: 'strong' as const, label: '浓' },
]
</script>

<template>
  <section class="card backdrop">
    <span class="name">插图氛围背景 <InfoTip>把最新一张插图模糊后铺在聊天背后。手机上不显示。</InfoTip></span>
    <Segmented v-model="illustrationPrefs.backdrop" :options="choices" label="插图氛围背景" />
  </section>
</template>

<style scoped>
.backdrop {
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: var(--space-2) var(--space-4);
  min-height: 56px; padding: var(--space-2) var(--space-4);
}
.name { display: inline-flex; align-items: center; gap: var(--space-1); font-weight: 500; }
</style>
