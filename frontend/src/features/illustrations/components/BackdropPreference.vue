<script setup lang="ts">
import { illustrationPrefs } from '../lib'
import InfoTip from '@/components/InfoTip.vue'
</script>

<template>
  <section class="card card-pad stack">
    <h2>插图</h2>
    <div class="field">
      <div class="row tip-row"><label class="label">氛围背景</label><InfoTip>把最新一张插图模糊后铺在聊天背后。手机上不显示。</InfoTip></div>
      <div class="row wrap seg">
        <label class="check"><input v-model="illustrationPrefs.backdrop" type="radio" value="off" /> 关闭</label>
        <label class="check"><input v-model="illustrationPrefs.backdrop" type="radio" value="subtle" /> 淡</label>
        <label class="check"><input v-model="illustrationPrefs.backdrop" type="radio" value="strong" /> 浓</label>
      </div>
    </div>
  </section>
</template>

<style scoped>
.seg { gap: var(--space-4); }
.tip-row { gap: var(--space-1); }
</style>
