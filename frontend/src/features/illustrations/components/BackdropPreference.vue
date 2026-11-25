<script setup lang="ts">
import { illustrationPrefs } from '../lib'
</script>

<template>
  <section class="card card-pad stack">
    <h2>插图</h2>
    <div class="field">
      <label>氛围背景</label>
      <div class="row wrap seg">
        <label class="check"><input v-model="illustrationPrefs.backdrop" type="radio" value="off" /> 关闭</label>
        <label class="check"><input v-model="illustrationPrefs.backdrop" type="radio" value="subtle" /> 淡</label>
        <label class="check"><input v-model="illustrationPrefs.backdrop" type="radio" value="strong" /> 浓</label>
      </div>
      <p class="hint">把最新一张插图模糊后铺在聊天背后。手机上始终关闭。是否生成插图在每个聊天的设置中选择。</p>
    </div>
  </section>
</template>

<style scoped>
.seg { gap: var(--space-4); }
</style>
