<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { frameDocument, useTheme, type StatusBarData } from '../frame'

/** Runs status bar code in a sandboxed frame and keeps it fed with data and sized to its content. */
const props = defineProps<{ code: string; data: Omit<StatusBarData, 'theme'> }>()

const frame = ref<HTMLIFrameElement>()
const height = ref(0)
const theme = useTheme()
// A theme change rebuilds the document, so the code never has to handle it.
const doc = computed(() => frameDocument(props.code, theme.value))

function send() {
  const data: StatusBarData = { ...props.data, theme: theme.value }
  // Plain JSON: reactive proxies can't be cloned across frames.
  frame.value?.contentWindow?.postMessage({ type: 'lorenook:data', data: JSON.parse(JSON.stringify(data)) }, '*')
}
function onMessage(event: MessageEvent) {
  if (!frame.value || event.source !== frame.value.contentWindow) return
  if (event.data?.type === 'lorenook:ready') send()
  else if (event.data?.type === 'lorenook:height' && Number.isFinite(event.data.height)) height.value = event.data.height
}
window.addEventListener('message', onMessage)
onBeforeUnmount(() => window.removeEventListener('message', onMessage))
watch(() => props.data, send, { deep: true })
</script>

<template>
  <iframe
    ref="frame" class="status-frame" sandbox="allow-scripts" :srcdoc="doc" title="状态栏"
    :style="{ height: `${height}px`, colorScheme: theme.dark ? 'dark' : 'light' }"
  />
</template>

<style scoped>
/* The inline color scheme matches the document's, or the browser paints the frame an opaque backdrop. */
.status-frame { display: block; width: 100%; max-height: 60vh; border: 0; background: transparent; }
</style>
