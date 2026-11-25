import { ref, watch } from 'vue'
import { prefs, resolvedTheme } from '@/lib/prefs'

/** What the status bar code receives through `lorenook.onData`. */
export interface StatusBarData {
  /** The full state the round ended in. */
  state: Record<string, unknown>
  /** `null` in the editor preview. */
  round_no: number | null
  character: { name: string }
  identity: { name: string }
  theme: Theme
}

export interface Theme {
  dark: boolean
  /** The app's CSS variables, also set on the frame's root so its CSS can use `var(--page-text)`. */
  vars: Record<string, string>
}

const THEME_VARS = [
  '--page-bg', '--page-text', '--page-muted', '--page-em', '--page-border', '--page-rule',
  '--text', '--text-muted', '--border', '--accent', '--danger', '--warn', '--font-reading', '--reading-size',
]

function readTheme(): Theme {
  const root = document.documentElement
  const style = getComputedStyle(root)
  const dark = root.dataset.theme === 'dark'
  return { dark, vars: Object.fromEntries(THEME_VARS.map((name) => [name, style.getPropertyValue(name).trim()])) }
}

/** The current theme, refreshed when the app's theme or reading font changes. */
export function useTheme() {
  const theme = ref(readTheme())
  const refresh = () => { theme.value = readTheme() }
  // `prefs` is applied to the root by its own watcher; read after it.
  watch(() => [resolvedTheme.value, prefs.fontSize, prefs.zhFont, prefs.enFont], refresh, { flush: 'post' })
  return theme
}

const escapeStyle = (value: string) => value.replace(/[<>]/g, '')

/**
 * The frame document: a fixed preamble, then the author's code. The frame is sandboxed without
 * same-origin, and the CSP blocks requests and form posts, so the code can draw but not reach the app.
 */
export function frameDocument(code: string, theme: Theme): string {
  const vars = Object.entries(theme.vars).filter(([, v]) => v).map(([k, v]) => `${k}:${escapeStyle(v)}`).join(';')
  return `<!doctype html>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="connect-src 'none'; form-action 'none'">
<style>:root{${vars};color-scheme:${theme.dark ? 'dark' : 'light'}}html,body{margin:0;background:transparent}body{color:var(--page-text);font-family:var(--font-reading);font-size:14px}</style>
<script>${PREAMBLE}</script>
${code}`
}

const PREAMBLE = `(() => {
  let data = null
  const listeners = []
  // Measured directly: a frame that starts at zero height isn't rendered, so ResizeObserver alone never fires.
  let last = -1
  const report = () => {
    const height = Math.ceil(document.documentElement.getBoundingClientRect().height)
    if (height !== last) parent.postMessage({ type: 'lorenook:height', height: last = height }, '*')
  }
  window.lorenook = {
    get data() { return data },
    onData(callback) { listeners.push(callback); if (data) { callback(data); report() } },
  }
  addEventListener('message', (event) => {
    if (event.source !== parent || event.data?.type !== 'lorenook:data') return
    data = event.data.data
    for (const callback of listeners) try { callback(data) } catch (error) { console.error(error) }
    report()
  })
  new MutationObserver(report).observe(document, { subtree: true, childList: true, attributes: true, characterData: true })
  new ResizeObserver(report).observe(document.documentElement)
  addEventListener('load', report, true)
  parent.postMessage({ type: 'lorenook:ready' }, '*')
})()`
