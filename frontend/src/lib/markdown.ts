import MarkdownIt from 'markdown-it'
import type { StateCore, Token } from 'markdown-it'
import { layoutQuotes, OPAQUE } from './quotes'

// Raw HTML is disabled, so model text is escaped and never becomes executable markup.
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })
md.disable(['image'])

const defaultLink = md.renderer.rules.link_open ?? ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))
md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  tokens[idx].attrSet('target', '_blank')
  tokens[idx].attrSet('rel', 'noopener noreferrer nofollow')
  return defaultLink(tokens, idx, options, env, self)
}

export interface RenderOptions {
  /** Mark dialogue quotations (main prose only). */
  quotes?: boolean
}

export function renderMarkdown(text: string, options: RenderOptions = {}): string {
  return md.render(text, { ...options })
}

const FORMAT_OPEN = /_open$/
const FORMAT_CLOSE = /_close$/

/**
 * Wraps recognized quotations in `<span class="q">` and standalone quotation lines in
 * `<span class="q-slip">`. Only plain text is scanned: inline code and link text are opaque, and
 * fenced or indented code blocks have no inline children to scan.
 */
function quoteRule(state: StateCore) {
  if (!state.env?.quotes) return
  state.tokens.forEach((block, bi) => {
    if (block.type !== 'inline' || !block.children?.length) return
    const inParagraph = state.tokens[bi - 1]?.type === 'paragraph_open'
    block.children = markQuotes(block.children, inParagraph, state)
  })
}

function markQuotes(children: Token[], allowSlips: boolean, state: StateCore): Token[] {
  // Flatten the line into scannable text, remembering where every character came from.
  let s = ''
  const tokAt: number[] = []
  const offAt: number[] = []
  const container: number[] = [] // innermost open formatting token per character
  const breaks: number[] = [] // child index of each line break
  const openAtBreak: boolean[] = [] // formatting still open across that break
  const open: number[] = []
  let linkDepth = 0
  const push = (ch: string, tok: number, off: number) => {
    s += ch
    tokAt.push(tok)
    offAt.push(off)
    container.push(open[open.length - 1] ?? -1)
  }
  children.forEach((t, i) => {
    if (t.type === 'link_open') {
      if (linkDepth++ === 0) push(OPAQUE, i, -1)
    } else if (t.type === 'link_close') {
      linkDepth--
    } else if (linkDepth > 0) {
      // link text is never dialogue
    } else if (t.type === 'text') {
      for (let k = 0; k < t.content.length; k++) push(t.content[k], i, k)
    } else if (t.type === 'softbreak' || t.type === 'hardbreak') {
      breaks.push(i)
      openAtBreak.push(open.length > 0)
      push('\n', i, -1)
    } else if (t.type === 'code_inline') {
      push(OPAQUE, i, -1)
    } else if (FORMAT_OPEN.test(t.type)) {
      open.push(i)
    } else if (FORMAT_CLOSE.test(t.type)) {
      open.pop()
    }
  })
  if (!/[“「『‘"\[【]/.test(s)) return children

  // A slip wraps whole lines, so formatting must not cross the line breaks around it.
  const canSlip = (from: number, to: number) =>
    allowSlips && (from === 0 || !openAtBreak[from - 1]) && (to === breaks.length || !openAtBreak[to])
  const { inline, slips } = layoutQuotes(s, canSlip)

  const cuts = new Map<number, { off: number; open: boolean }[]>()
  for (const q of inline) {
    // Skip spans whose ends sit in different formatting elements; wrapping them would misnest.
    if (container[q.start] !== container[q.end - 1]) continue
    const list = (t: number) => cuts.get(t) ?? cuts.set(t, []).get(t)!
    list(tokAt[q.start]).push({ off: offAt[q.start], open: true })
    list(tokAt[q.end - 1]).push({ off: offAt[q.end - 1] + 1, open: false })
  }

  const firstTok = (line: number) => (line === 0 ? 0 : breaks[line - 1] + 1)
  const lastTok = (line: number) => (line === breaks.length ? children.length - 1 : breaks[line] - 1)
  const slipBefore = new Map<number, boolean>()
  const slipAfter = new Set<number>()
  const dropped = new Set<number>()
  for (const slip of slips) {
    slipBefore.set(firstTok(slip.fromLine), slip.bracket)
    slipAfter.add(lastTok(slip.toLine))
    if (slip.fromLine > 0) dropped.add(breaks[slip.fromLine - 1])
    if (slip.toLine < breaks.length) dropped.add(breaks[slip.toLine])
  }

  const marker = (opening: boolean, cls: string) => {
    const t = new state.Token(opening ? 'quote_open' : 'quote_close', 'span', opening ? 1 : -1)
    if (opening) t.attrSet('class', cls)
    return t
  }
  const out: Token[] = []
  children.forEach((t, i) => {
    if (slipBefore.has(i)) out.push(marker(true, slipBefore.get(i) ? 'q-slip q-bracket' : 'q-slip'))
    const tokCuts = cuts.get(i)
    if (dropped.has(i)) {
      // line break absorbed by an adjacent slip
    } else if (tokCuts && t.type === 'text') {
      tokCuts.sort((a, b) => a.off - b.off || Number(a.open) - Number(b.open))
      let pos = 0
      for (const c of tokCuts) {
        if (c.off > pos) out.push(textToken(state, t.content.slice(pos, c.off)))
        out.push(marker(c.open, 'q'))
        pos = c.off
      }
      if (pos < t.content.length) out.push(textToken(state, t.content.slice(pos)))
    } else {
      out.push(t)
    }
    if (slipAfter.has(i)) out.push(marker(false, ''))
  })
  return out
}

function textToken(state: StateCore, content: string): Token {
  const t = new state.Token('text', '', 0)
  t.content = content
  return t
}

md.core.ruler.push('quotes', quoteRule)
