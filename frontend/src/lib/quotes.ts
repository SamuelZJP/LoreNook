/**
 * Quotation recognition for main prose. Presentation only: the source text is never rewritten.
 *
 * A line made up only of quotations becomes a standalone "slip"; any other recognized quotation
 * is an inline span. Quotations normally stay within one line. A quotation may span several
 * lines only when it opens at the start of a line and closes at the end of a later one, which
 * makes those lines a single slip. Unmatched delimiters are left alone.
 */

/** Opening delimiter → closing delimiter. `《》` and `（）` are deliberately absent. */
const PAIRS: Record<string, string> = {
  '“': '”', '「': '」', '『': '』', '‘': '’', '"': '"', '[': ']', '【': '】',
}
const CLOSERS = new Map(Object.entries(PAIRS).map(([open, close]) => [close, open]))
const BRACKETS = new Set(['[', '【'])
/** Brackets count as dialogue only when their text ends like a sentence. */
const SENTENCE_END = /[。！？!?…～~”」』’"]$/u
const HAN = /\p{Script=Han}/u
const LATIN_WORD = /[A-Za-z0-9À-ɏ]/

/** Stands in for content that is never scanned (inline code, links). Not whitespace. */
export const OPAQUE = '￼'

export interface QuoteSpan {
  start: number
  /** Exclusive; the closing delimiter is at `end - 1`. */
  end: number
  bracket: boolean
}

export interface QuoteSlip {
  /** First and last line index covered. */
  fromLine: number
  toLine: number
  /** Character range of those lines, excluding the surrounding newlines. */
  from: number
  to: number
  bracket: boolean
}

export interface QuoteLayout {
  inline: QuoteSpan[]
  slips: QuoteSlip[]
}

interface Line { start: number; end: number; first: number; last: number }

function lineRanges(s: string): Line[] {
  const lines: Line[] = []
  let start = 0
  for (let i = 0; i <= s.length; i++) {
    if (i === s.length || s[i] === '\n') {
      let first = start
      while (first < i && /\s/.test(s[first])) first++
      let last = i - 1
      while (last >= first && /\s/.test(s[last])) last--
      lines.push({ start, end: i, first, last })
      start = i + 1
    }
  }
  return lines
}

function lastIndexOf<T>(list: T[], test: (item: T) => boolean): number {
  for (let i = list.length - 1; i >= 0; i--) if (test(list[i])) return i
  return -1
}

const isLatin = (c: string | undefined) => !!c && LATIN_WORD.test(c)
const isSpace = (c: string | undefined) => !c || /\s/.test(c)

/** Every balanced pair, nested ones included, in closing order. */
function scanPairs(s: string): QuoteSpan[] {
  const stack: { ch: string; idx: number }[] = []
  const pairs: QuoteSpan[] = []
  const close = (at: number, i: number) => {
    const open = stack[at]
    stack.length = at
    const body = s.slice(open.idx + 1, i).trim()
    if (!body) return
    const bracket = BRACKETS.has(open.ch)
    if (bracket && !(HAN.test(body) && SENTENCE_END.test(body))) return
    pairs.push({ start: open.idx, end: i + 1, bracket })
  }
  for (let i = 0; i < s.length; i++) {
    const c = s[i]
    if (c === '"') {
      // Straight quotes are symmetric: decide by the neighbours, so 5'11" or a"b do not pair.
      const at = lastIndexOf(stack, (o) => o.ch === '"')
      if (at !== -1 && !isSpace(s[i - 1]) && !isLatin(s[i + 1])) close(at, i)
      else if (!isLatin(s[i - 1]) && !isSpace(s[i + 1])) stack.push({ ch: c, idx: i })
      continue
    }
    if (c === '’' && isLatin(s[i - 1]) && isLatin(s[i + 1])) continue // apostrophe: don’t
    const opener = CLOSERS.get(c)
    if (opener) {
      const at = lastIndexOf(stack, (o) => o.ch === opener)
      if (at !== -1) close(at, i)
    } else if (c in PAIRS) {
      stack.push({ ch: c, idx: i })
    }
  }
  return pairs
}

/**
 * Lays out the quotations of `s`, where lines are separated by `\n`.
 * `canSlip(fromLine, toLine)` may veto a slip; its quotations then render inline.
 */
export function layoutQuotes(s: string, canSlip: (from: number, to: number) => boolean = () => true): QuoteLayout {
  const lines = lineRanges(s)
  const lineAt = (i: number) => lines.findIndex((l) => i >= l.start && i <= l.end)

  // A multi-line pair is acceptable only as whole lines of speech.
  const candidates = scanPairs(s)
    .map((p) => ({ ...p, a: lineAt(p.start), b: lineAt(p.end - 1) }))
    .filter((p) => p.a === p.b || (p.start === lines[p.a].first && p.end - 1 === lines[p.b].last))
    .sort((x, y) => x.start - y.start || y.end - x.end)

  const selected: typeof candidates = []
  for (const p of candidates) {
    const outer = selected[selected.length - 1]
    if (!outer || p.start >= outer.end) selected.push(p)
  }

  const inline: QuoteSpan[] = []
  const slips: QuoteSlip[] = []
  let k = 0
  for (let li = 0; li < lines.length; ) {
    while (k < selected.length && selected[k].a < li) k++
    const line = lines[li]
    const multi = selected[k]?.a === li && selected[k].b > li ? selected[k] : null
    if (multi) {
      if (canSlip(li, multi.b)) {
        slips.push({ fromLine: li, toLine: multi.b, from: lines[li].start, to: lines[multi.b].end, bracket: multi.bracket })
      } else {
        inline.push(multi)
      }
      li = multi.b + 1
      continue
    }
    const own: QuoteSpan[] = []
    for (let j = k; j < selected.length && selected[j].a === li; j++) own.push(selected[j])
    const covered = own.length > 0 && own[0].start === line.first && own[own.length - 1].end - 1 === line.last
      && own.every((p, j) => j === 0 || !s.slice(own[j - 1].end, p.start).trim())
    if (covered && canSlip(li, li)) {
      slips.push({ fromLine: li, toLine: li, from: line.start, to: line.end, bracket: own.every((p) => p.bracket) })
    } else {
      inline.push(...own)
    }
    li++
  }
  return { inline, slips }
}

export type PlainSegment =
  | { kind: 'text'; text: string }
  | { kind: 'quote'; text: string }
  | { kind: 'slip'; text: string; bracket: boolean }

/** Segments for prose rendered without Markdown. Line breaks next to a slip are absorbed. */
export function plainQuoteSegments(text: string): PlainSegment[] {
  const { inline, slips } = layoutQuotes(text)
  const marks = [
    ...inline.map((q) => ({ from: q.start, to: q.end, slip: null as QuoteSlip | null })),
    ...slips.map((q) => ({ from: q.from, to: q.to, slip: q })),
  ].sort((a, b) => a.from - b.from)

  const out: PlainSegment[] = []
  const pushText = (t: string) => { if (t) out.push({ kind: 'text', text: t }) }
  let pos = 0
  for (const m of marks) {
    if (m.slip) {
      pushText(text.slice(pos, m.from > 0 ? m.from - 1 : m.from))
      out.push({ kind: 'slip', text: text.slice(m.from, m.to).trim(), bracket: m.slip.bracket })
      pos = m.to < text.length ? m.to + 1 : m.to
    } else {
      pushText(text.slice(pos, m.from))
      out.push({ kind: 'quote', text: text.slice(m.from, m.to) })
      pos = m.to
    }
  }
  pushText(text.slice(pos))
  return out
}
