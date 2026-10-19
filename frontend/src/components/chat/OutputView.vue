<script setup lang="ts">
import { computed } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import { parseSections } from '@/lib/sections'
import { prefs, sectionMode, type SectionMode } from '@/lib/prefs'
import { renderMarkdown } from '@/lib/markdown'

/** Presentation of stored AI output. The `text` prop is never modified. */
const props = defineProps<{ text: string; raw?: boolean }>()

const sections = computed(() =>
  parseSections(props.text).map((s) => {
    const mode: SectionMode = s.kind === 'text' ? prefs.looseText : sectionMode(s.name)
    return { ...s, mode, html: prefs.markdown ? renderMarkdown(s.body.trim()) : null }
  }),
)
const visible = computed(() => sections.value.filter((s) => s.mode !== 'hide'))
const hiddenCount = computed(() => sections.value.length - visible.value.length)
const hasPrimary = computed(() => visible.value.some((s) => s.mode === 'show'))
</script>

<template>
  <pre v-if="raw" class="plain mono raw">{{ text }}</pre>
  <div v-else class="output">
    <template v-for="(s, i) in visible" :key="i">
      <div v-if="s.mode === 'show'" class="section" :class="{ unclosed: !s.closed }">
        <div v-if="s.kind === 'tag' && s.name !== 'content'" class="tag-label">{{ s.name }}</div>
        <div v-if="s.html !== null" class="prose" v-html="s.html" />
        <div v-else class="plain">{{ s.body.trim() }}</div>
        <div v-if="!s.closed" class="warn-note">⚠ &lt;{{ s.name }}&gt; 未闭合</div>
      </div>
      <details v-else class="section folded" :class="{ unclosed: !s.closed }">
        <summary><ChevronRight class="chev" />{{ s.kind === 'tag' ? s.name : '标签外文本' }}<span v-if="!s.closed" class="faint">（未闭合）</span></summary>
        <div v-if="s.html !== null" class="prose" v-html="s.html" />
        <div v-else class="plain">{{ s.body.trim() }}</div>
      </details>
    </template>
    <div v-if="!hasPrimary" class="faint note">（没有默认显示的区段{{ hiddenCount ? `，${hiddenCount} 个已隐藏` : '' }}）</div>
  </div>
</template>

<style scoped>
.output { display: flex; flex-direction: column; gap: 8px; }
.tag-label, .folded summary { font-size: 12px; font-weight: 600; color: var(--text-muted); font-family: var(--font-mono); }
.tag-label { margin-bottom: 2px; }
.folded { border-left: 2px solid var(--border-strong); padding-left: 10px; }
.folded summary { cursor: pointer; list-style: none; display: flex; align-items: center; gap: 4px; user-select: none; }
.folded summary::-webkit-details-marker { display: none; }
.folded[open] .chev { transform: rotate(90deg); }
.chev { width: 14px; height: 14px; transition: transform 0.15s; }
.folded > .prose, .folded > .plain { margin-top: 6px; font-size: calc(var(--reading-size) - 1px); color: var(--text-muted); }
.unclosed { border-left: 2px solid var(--warn); padding-left: 10px; }
.warn-note { font-size: 12px; color: var(--warn); margin-top: 4px; }
.note { font-size: 13px; }
.raw { font-size: 13px; }
</style>
