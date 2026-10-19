<script setup lang="ts">
import type { PlainSegment } from '@/lib/quotes'

/** Body of one output section: Markdown HTML, plain text, or plain prose with quotations marked. */
defineProps<{ s: { html: string | null; segments: PlainSegment[] | null; body: string }; cls: string }>()
</script>

<template>
  <div v-if="s.html !== null" class="prose" :class="cls" v-html="s.html" />
  <div v-else-if="s.segments" class="plain" :class="cls"><template v-for="(seg, i) in s.segments" :key="i"
    ><template v-if="seg.kind === 'text'">{{ seg.text }}</template
    ><span v-else-if="seg.kind === 'quote'" class="q">{{ seg.text }}</span
    ><span v-else class="q-slip" :class="{ 'q-bracket': seg.bracket }">{{ seg.text }}</span
  ></template></div>
  <div v-else class="plain" :class="cls">{{ s.body }}</div>
</template>
