<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ChevronDown } from 'lucide-vue-next'
import AvatarBadge from './AvatarBadge.vue'

interface Profile { id: string; name: string; avatar?: string | null; description?: string | null }

const props = defineProps<{ items: Profile[]; label?: string }>()
const model = defineModel<string>({ required: true })

const open = ref(false)
const active = ref(-1)
const trigger = ref<HTMLButtonElement>()
const list = ref<HTMLUListElement>()
const pos = ref<Record<string, string>>({})
const listId = `profile-picker-${Math.random().toString(36).slice(2, 8)}`

const selected = computed(() => props.items.find((i) => i.id === model.value))
const sub = (p?: Profile) => p?.description?.replace(/\s+/g, ' ').trim() || '—'

// The list is teleported to <body> so the modal's scrolling body cannot clip it.
function place() {
  const r = trigger.value?.getBoundingClientRect()
  if (!r) return
  const below = window.innerHeight - r.bottom - 8
  const up = below < 200 && r.top > below
  const max = Math.min(320, (up ? r.top : below) - 8)
  pos.value = {
    left: `${r.left}px`, width: `${r.width}px`, maxHeight: `${max}px`,
    ...(up ? { bottom: `${window.innerHeight - r.top + 4}px` } : { top: `${r.bottom + 4}px` }),
  }
}

function show() {
  if (!props.items.length) return
  place()
  active.value = Math.max(0, props.items.findIndex((i) => i.id === model.value))
  open.value = true
  nextTick(scrollActive)
}
function hide(refocus = false) {
  open.value = false
  if (refocus) trigger.value?.focus()
}
function pick(i: number) {
  const it = props.items[i]
  if (it) model.value = it.id
  hide(true)
}
function scrollActive() {
  list.value?.children[active.value]?.scrollIntoView({ block: 'nearest' })
}

function onKey(e: KeyboardEvent) {
  const n = props.items.length
  if (!open.value) {
    if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) { e.preventDefault(); show() }
    return
  }
  if (e.key === 'ArrowDown') active.value = (active.value + 1) % n
  else if (e.key === 'ArrowUp') active.value = (active.value - 1 + n) % n
  else if (e.key === 'Home') active.value = 0
  else if (e.key === 'End') active.value = n - 1
  else if (e.key === 'Enter' || e.key === ' ') pick(active.value)
  else if (e.key === 'Escape') { e.stopPropagation(); hide(true) }
  else if (e.key === 'Tab') { hide(); return }
  else return
  e.preventDefault()
  nextTick(scrollActive)
}

function onOutside(e: PointerEvent) {
  const t = e.target as Node
  if (!trigger.value?.contains(t) && !list.value?.contains(t)) hide()
}
function onScroll(e: Event) {
  if (!list.value?.contains(e.target as Node)) place()
}

watch(open, (v) => {
  const fn = v ? 'addEventListener' : 'removeEventListener'
  document[fn]('pointerdown', onOutside as EventListener, true)
  window[fn]('scroll', onScroll, true)
  window[fn]('resize', place)
})
onBeforeUnmount(() => (open.value = false))
</script>

<template>
  <button
    ref="trigger" type="button" class="select picker" role="combobox"
    :aria-label="label" :aria-expanded="open" :aria-controls="listId"
    :aria-activedescendant="open && active >= 0 ? `${listId}-${active}` : undefined"
    @click="open ? hide() : show()" @keydown="onKey"
  >
    <template v-if="selected">
      <AvatarBadge :name="selected.name" :src="selected.avatar" :size="28" />
      <span class="text">
        <span class="ellipsis name">{{ selected.name }}</span>
        <span class="ellipsis sub">{{ sub(selected) }}</span>
      </span>
    </template>
    <span v-else class="text placeholder">（未选择）</span>
    <ChevronDown class="caret" aria-hidden="true" />
  </button>
  <Teleport to="body">
    <ul v-if="open" :id="listId" ref="list" class="picker-list" role="listbox" :style="pos">
      <li
        v-for="(it, i) in items" :id="`${listId}-${i}`" :key="it.id" role="option"
        :aria-selected="it.id === model" :class="{ active: i === active, selected: it.id === model }"
        @pointerenter="active = i" @click="pick(i)"
      >
        <AvatarBadge :name="it.name" :src="it.avatar" :size="28" />
        <span class="text">
          <span class="ellipsis name">{{ it.name }}</span>
          <span class="ellipsis sub">{{ sub(it) }}</span>
        </span>
      </li>
    </ul>
  </Teleport>
</template>

<style scoped>
.picker { display: flex; align-items: center; gap: 8px; padding: 5px 8px; text-align: left; cursor: pointer; min-height: 44px; }
.text { display: flex; flex-direction: column; min-width: 0; flex: 1; line-height: 1.3; }
.name { font-size: 14px; }
.sub { font-size: 12px; color: var(--text-faint); }
.placeholder { color: var(--text-faint); }
.caret { width: 16px; height: 16px; flex-shrink: 0; color: var(--text-muted); }

.picker-list {
  position: fixed; z-index: 110; margin: 0; padding: 4px; list-style: none; overflow-y: auto;
  background: var(--bg-elev); border: 1px solid var(--border); border-radius: var(--radius-m); box-shadow: var(--shadow-pop);
}
.picker-list li { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: var(--radius-s); cursor: pointer; }
.picker-list li.active { background: var(--bg-hover); }
.picker-list li.selected { background: var(--bg-active); }
</style>
