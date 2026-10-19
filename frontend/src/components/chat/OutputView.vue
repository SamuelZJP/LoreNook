<script setup lang="ts">
import { computed } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import { parseSections } from '@/lib/sections'
import { prefs, sectionRule, type RenderCategory, type SectionMode } from '@/lib/prefs'
import { renderMarkdown } from '@/lib/markdown'
import { plainQuoteSegments, type PlainSegment } from '@/lib/quotes'
import SectionBody from './SectionBody.vue'

/** Presentation of stored AI output. The `text` prop is never modified. */
const props = defineProps<{ text: string; raw?: boolean }>()

interface ViewSection {
  name: string
  label: string
  category: RenderCategory
  mode: SectionMode
  closed: boolean
  body: string
  html: string | null
  segments: PlainSegment[] | null
}

const sections = computed<ViewSection[]>(() =>
  parseSections(props.text).map((s) => {
    const rule = s.kind === 'text' ? prefs.looseText : sectionRule(s.name)
    const body = s.body.trim()
    const prose = rule.category === 'prose'
    return {
      name: s.name,
      label: s.kind === 'tag' ? s.name : '标签外文本',
      category: rule.category,
      mode: rule.mode,
      closed: s.closed,
      body,
      html: prefs.markdown ? renderMarkdown(body, { quotes: prose }) : null,
      segments: !prefs.markdown && prose ? plainQuoteSegments(body) : null,
    }
  }),
)
const visible = computed(() => sections.value.filter((s) => s.mode !== 'hide'))
const hiddenCount = computed(() => sections.value.length - visible.value.length)
const hasPrimary = computed(() => visible.value.some((s) => s.mode === 'show'))

const bodyClass: Record<RenderCategory, string> = {
  prose: 'reading-prose',
  thought: 'reading-thought',
  other: 'reading-other',
}

/** First line of a thought, shown while it is folded. */
function preview(body: string): string {
  const line = body.split('\n').find((l) => l.trim()) ?? ''
  return line.replace(/^[#>*\-\s]+/, '').trim()
}
function charCount(body: string): number {
  return [...body.replace(/\s/g, '')].length
}
</script>

<template>
  <pre v-if="raw" class="plain mono raw">{{ text }}</pre>
  <div v-else class="output">
    <template v-for="(s, i) in visible" :key="i">
      <!-- Chain of thought: always a folded note; "show" only opens it initially -->
      <details v-if="s.category === 'thought'" class="thought" :class="{ unclosed: !s.closed }" :open="s.mode === 'show'">
        <summary>
          <ChevronRight class="chev" />
          <span class="chip">{{ s.label }}</span>
          <span class="peek">{{ preview(s.body) }}</span>
          <span class="count">{{ s.closed ? `${charCount(s.body)} 字` : '未闭合' }}</span>
        </summary>
        <SectionBody class="thought-body" :s="s" :cls="bodyClass[s.category]" />
      </details>

      <details v-else-if="s.mode === 'collapse'" class="folded" :class="[s.category, { unclosed: !s.closed }]">
        <summary><ChevronRight class="chev" /><span class="chip">{{ s.label }}</span><span v-if="!s.closed" class="count">未闭合</span></summary>
        <div class="fold-body"><SectionBody :s="s" :cls="bodyClass[s.category]" /></div>
      </details>

      <div v-else class="section" :class="[s.category, { unclosed: !s.closed }]">
        <span v-if="s.category === 'other'" class="chip">{{ s.label }}</span>
        <SectionBody :s="s" :cls="bodyClass[s.category]" />
        <div v-if="!s.closed" class="warn-note">⚠ &lt;{{ s.name }}&gt; 未闭合</div>
      </div>
    </template>
    <div v-if="!hasPrimary" class="faint note">（没有默认显示的区段{{ hiddenCount ? `，${hiddenCount} 个已隐藏` : '' }}）</div>
  </div>
</template>

<style scoped>
.output { display: flex; flex-direction: column; gap: 12px; }
summary { cursor: pointer; list-style: none; display: flex; align-items: center; gap: 8px; user-select: none; min-width: 0; }
summary::-webkit-details-marker { display: none; }
details[open] > summary .chev { transform: rotate(90deg); }
.chev { width: 14px; height: 14px; flex-shrink: 0; transition: transform 0.15s; }
.chip {
  font-family: var(--font-mono); font-size: 12px; line-height: 1.6; padding: 0 6px; flex-shrink: 0;
  border: 1px solid var(--page-border); border-radius: 6px; color: var(--page-muted); align-self: flex-start;
}
.count { font-size: 12px; color: var(--page-muted); flex-shrink: 0; font-variant-numeric: tabular-nums; }

.thought { border: 1px dashed var(--page-border); border-radius: 10px; padding: 6px 12px; color: var(--page-muted); font-size: 13px; }
.thought .peek {
  flex: 1; min-width: 0; font-family: var(--font-reading); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.thought[open] .peek { visibility: hidden; }
.thought-body { margin: 8px 2px 4px; }

.folded { color: var(--page-muted); font-size: 13px; }
.fold-body { margin-top: 8px; }
.folded.prose > .fold-body { color: var(--page-text); }
.section.other, .folded.other { border-top: 1px solid var(--page-rule); padding-top: 8px; }
.section.other { display: flex; gap: 10px; align-items: flex-start; }
.section.other > :not(.chip) { flex: 1; min-width: 0; }

.unclosed { border-color: var(--warn); }
.section.unclosed, .folded.unclosed { border-left: 2px solid var(--warn); padding-left: 10px; }
.warn-note { font-size: 12px; color: var(--warn); margin-top: 4px; }
.note { font-size: 13px; }
.raw { font-size: 13px; }
</style>
