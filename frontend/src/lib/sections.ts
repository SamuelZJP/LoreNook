/**
 * Split AI output into display sections. Presentation only: the stored text is never rewritten.
 *
 * Top-level `<name>...</name>` blocks become tag sections; text between them becomes text
 * sections. An opening tag without a matching close becomes an `unclosed` section holding the
 * rest of the text, so malformed output is still fully visible.
 */
export interface Section {
  kind: 'tag' | 'text'
  name: string
  body: string
  closed: boolean
}

const OPEN = /<([A-Za-z_][\w\-~.:]*)(\s[^<>]*)?>/g

export function parseSections(text: string): Section[] {
  const sections: Section[] = []
  let cursor = 0
  OPEN.lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = OPEN.exec(text))) {
    const name = match[1]
    const start = match.index
    const bodyStart = start + match[0].length
    const close = `</${name}>`
    const end = text.indexOf(close, bodyStart)
    pushText(sections, text.slice(cursor, start))
    if (end === -1) {
      sections.push({ kind: 'tag', name, body: text.slice(bodyStart), closed: false })
      cursor = text.length
      break
    }
    sections.push({ kind: 'tag', name, body: text.slice(bodyStart, end), closed: true })
    cursor = end + close.length
    OPEN.lastIndex = cursor
  }
  pushText(sections, text.slice(cursor))
  return sections
}

function pushText(sections: Section[], text: string) {
  if (text.trim()) sections.push({ kind: 'text', name: '', body: text, closed: true })
}

/** Mirrors the archive requirement: exactly one closed, nonblank `<content>` section. */
export function contentProblem(text: string): string | null {
  const opens = text.match(/<content(\s[^<>]*)?>/g)?.length ?? 0
  const closes = text.match(/<\/content>/g)?.length ?? 0
  if (opens === 0) return '缺少 <content> 区段'
  if (opens > 1 || closes > 1) return '<content> 区段出现多次'
  if (closes === 0) return '<content> 区段未闭合'
  const body = parseSections(text).find((s) => s.kind === 'tag' && s.name === 'content')
  if (!body || !body.body.trim()) return '<content> 区段为空'
  return null
}

/** Body of the `<content>` section, for compact previews. */
export function contentBody(text: string): string {
  return parseSections(text).find((s) => s.kind === 'tag' && s.name === 'content')?.body ?? text
}
