<script setup lang="ts" generic="T extends string | number | null">
/** A row of mutually exclusive choices shown as one pill. */
defineProps<{ options: { value: T; label: string }[]; label?: string }>()
const model = defineModel<T>({ required: true })
</script>

<template>
  <div class="segmented" role="radiogroup" :aria-label="label">
    <button
      v-for="o in options" :key="String(o.value)" type="button" role="radio"
      :aria-checked="model === o.value" :class="{ on: model === o.value }" @click="model = o.value"
    >{{ o.label }}</button>
  </div>
</template>

<style scoped>
.segmented { display: inline-flex; flex-wrap: wrap; gap: 2px; padding: 3px; border-radius: var(--radius-pill); background: var(--bg-sunken); }
button {
  border: 0; background: none; color: var(--text-muted); font: inherit; font-size: var(--text-sm); font-weight: 500;
  padding: var(--space-1-5) var(--space-3); border-radius: var(--radius-pill); cursor: pointer; white-space: nowrap;
}
button:hover { color: var(--text); }
button.on { background: var(--bg-elev); color: var(--text); box-shadow: 0 1px 2px rgb(0 0 0 / 8%), 0 0 0 1px var(--border); }
</style>
