<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { EditorState, StateEffect, StateField, type Extension } from '@codemirror/state'
import { Decoration, EditorView, keymap, lineNumbers, highlightActiveLine, drawSelection, type DecorationSet } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { bracketMatching, indentOnInput, syntaxHighlighting, HighlightStyle, StreamLanguage } from '@codemirror/language'
import { tags as t } from '@lezer/highlight'
import { javascript } from '@codemirror/lang-javascript'
import { python } from '@codemirror/lang-python'
import { json } from '@codemirror/lang-json'
import { jinja2 } from '@codemirror/legacy-modes/mode/jinja2'

export type EditorLanguage = 'javascript' | 'python' | 'json' | 'jinja' | 'text'

const props = withDefaults(
  defineProps<{ modelValue: string; language?: EditorLanguage; minHeight?: string; maxHeight?: string; errorLine?: number | null; readonly?: boolean }>(),
  { language: 'text', minHeight: '160px', maxHeight: '70vh', errorLine: null, readonly: false },
)
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const host = ref<HTMLDivElement>()
let view: EditorView | null = null

const setError = StateEffect.define<number | null>()
const errorField = StateField.define<DecorationSet>({
  create: () => Decoration.none,
  update(deco, tr) {
    for (const e of tr.effects) {
      if (!e.is(setError)) continue
      const line = e.value
      if (!line || line > tr.state.doc.lines) return Decoration.none
      const pos = tr.state.doc.line(line).from
      return Decoration.set([Decoration.line({ class: 'cm-error-line' }).range(pos)])
    }
    return deco.map(tr.changes)
  },
  provide: (f) => EditorView.decorations.from(f),
})

function languageExtension(lang: EditorLanguage): Extension {
  switch (lang) {
    case 'javascript': return javascript()
    case 'python': return python()
    case 'json': return json()
    case 'jinja': return StreamLanguage.define(jinja2)
    default: return []
  }
}

// Colors come from CSS variables so highlighting follows the light/dark theme.
const highlight = HighlightStyle.define([
  { tag: [t.keyword, t.operatorKeyword, t.modifier, t.controlKeyword], color: 'var(--syn-keyword)' },
  { tag: [t.string, t.special(t.string), t.regexp], color: 'var(--syn-string)' },
  { tag: [t.number, t.bool, t.null, t.atom], color: 'var(--syn-number)' },
  { tag: [t.comment, t.lineComment, t.blockComment], color: 'var(--syn-comment)', fontStyle: 'italic' },
  { tag: [t.function(t.variableName), t.function(t.propertyName), t.definition(t.function(t.variableName))], color: 'var(--syn-function)' },
  { tag: [t.propertyName, t.attributeName], color: 'var(--syn-property)' },
  { tag: [t.typeName, t.className, t.definition(t.typeName)], color: 'var(--syn-type)' },
  { tag: [t.bracket, t.punctuation, t.operator], color: 'var(--text-muted)' },
  { tag: [t.meta, t.processingInstruction], color: 'var(--syn-keyword)' },
])

const theme = EditorView.theme({
  '&': { backgroundColor: 'var(--bg-sunken)', color: 'var(--text)', fontSize: '13px', borderRadius: 'var(--radius-s)' },
  '.cm-content': { fontFamily: 'var(--font-mono)', caretColor: 'var(--accent)', padding: '8px 0' },
  '.cm-gutters': { backgroundColor: 'var(--bg-sunken)', color: 'var(--text-faint)', border: 'none' },
  '.cm-activeLine': { backgroundColor: 'color-mix(in srgb, var(--accent) 7%, transparent)' },
  '.cm-activeLineGutter': { backgroundColor: 'transparent', color: 'var(--text-muted)' },
  '&.cm-focused': { outline: 'none' },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground, ::selection': { backgroundColor: 'var(--bg-active) !important' },
  '.cm-cursor': { borderLeftColor: 'var(--accent)' },
  '.cm-error-line': { backgroundColor: 'var(--danger-soft)' },
  '.cm-scroller': { overflow: 'auto' },
})

onMounted(() => {
  view = new EditorView({
    parent: host.value!,
    state: EditorState.create({
      doc: props.modelValue,
      extensions: [
        lineNumbers(), history(), drawSelection(), highlightActiveLine(), indentOnInput(), bracketMatching(),
        syntaxHighlighting(highlight),
        keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
        EditorView.lineWrapping, theme, errorField, languageExtension(props.language),
        EditorState.readOnly.of(props.readonly),
        EditorView.updateListener.of((u) => {
          if (u.docChanged) emit('update:modelValue', u.state.doc.toString())
        }),
      ],
    }),
  })
  if (props.errorLine) view.dispatch({ effects: setError.of(props.errorLine) })
})

watch(() => props.modelValue, (value) => {
  if (view && value !== view.state.doc.toString()) {
    view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: value } })
  }
})
watch(() => props.errorLine, (line) => view?.dispatch({ effects: setError.of(line) }))
onBeforeUnmount(() => view?.destroy())
</script>

<template>
  <div ref="host" class="code-editor" :style="{ '--min-h': minHeight, '--max-h': maxHeight }" />
</template>

<style scoped>
.code-editor { border: 1px solid var(--border); border-radius: var(--radius-s); overflow: hidden; }
.code-editor:focus-within { border-color: var(--accent); }
.code-editor :deep(.cm-editor) { min-height: var(--min-h); max-height: var(--max-h); }
.code-editor :deep(.cm-scroller) { min-height: var(--min-h); }
</style>
