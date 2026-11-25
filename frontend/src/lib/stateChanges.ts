/**
 * Plans what the latest round changed in the state, grouped like the state display: `世界`,
 * then one group per top-level object, then loose fields under 其他. Labels follow the chat
 * Schema; the clock (世界.时间 / 星期) and hidden fields are left out, since they change every
 * round or are not for the reader. Plain data only; components render it.
 */
import { child, isObject, isScalar, label, resolve, type Json, type SchemaNode } from './stateDisplay'

export type Change =
  | { kind: 'number'; label: string; from: number | null; to: number }
  | { kind: 'text'; label: string; to: string }
  | { kind: 'flag'; label: string; to: boolean }
  | { kind: 'list'; label: string; added: string[]; removed: string[] }
  | { kind: 'cleared'; label: string }

export interface ChangeGroup { key: string; title: string; changes: Change[] }

export interface LatestChanges {
  /** The round that made these changes; 0 never appears, since the opening has nothing before it. */
  roundNo: number
  groups: ChangeGroup[]
}

const SKIP_WORLD = ['时间', '星期']
const same = (a: Json | undefined, b: Json | undefined) => JSON.stringify(a) === JSON.stringify(b)
const isEmpty = (v: Json | undefined) => v === undefined || v === null || v === '' || (Array.isArray(v) && !v.length)
const asObject = (v: Json | undefined): Record<string, Json> => (isObject(v) ? v : {})
const keys = (a: Record<string, Json>, b: Record<string, Json>) => [...new Set([...Object.keys(a), ...Object.keys(b)])]

function diff(path: string[], before: Json | undefined, after: Json | undefined, node: SchemaNode, root: SchemaNode | null, out: Change[]) {
  if (node.display === 'hidden' || same(before, after)) return
  const name = path.join(' · ')
  if (isObject(after) || isObject(before)) {
    const a = asObject(before)
    const b = asObject(after)
    for (const key of keys(a, b)) {
      const sub = child(node, key, root)
      diff([...path, label(key, sub)], a[key], b[key], sub, root, out)
    }
    return
  }
  if (isEmpty(after)) {
    if (!isEmpty(before)) out.push({ kind: 'cleared', label: name })
    return
  }
  if (typeof after === 'number') {
    out.push({ kind: 'number', label: name, from: typeof before === 'number' ? before : null, to: after })
  } else if (typeof after === 'boolean') {
    out.push({ kind: 'flag', label: name, to: after })
  } else if (Array.isArray(after)) {
    // Lists of records only report that they changed; scalar lists report what came and went.
    const prev = Array.isArray(before) ? before : []
    if (after.every(isScalar) && prev.every(isScalar)) {
      const was = prev.map(String)
      const now = after.map(String)
      const added = now.filter((v) => !was.includes(v))
      const removed = was.filter((v) => !now.includes(v))
      if (added.length || removed.length) out.push({ kind: 'list', label: name, added, removed })
    } else {
      out.push({ kind: 'text', label: name, to: `${after.length} 项` })
    }
  } else {
    out.push({ kind: 'text', label: name, to: String(after) })
  }
}

/** Changes between the last two snapshots (oldest first), or null before the first round. */
export function planLatestChanges(
  history: { round_no: number; content: Record<string, unknown> }[],
  schema: SchemaNode | null,
): LatestChanges | null {
  if (history.length < 2) return null
  const root = schema ? resolve(schema, schema) : {}
  const before = history.at(-2)!.content as Record<string, Json>
  const after = history.at(-1)!.content as Record<string, Json>
  const groups: ChangeGroup[] = []
  const loose: Change[] = []
  for (const key of keys(before, after)) {
    const node = child(root, key, schema)
    if (node.display === 'hidden') continue
    if (isObject(before[key]) || isObject(after[key])) {
      const a = asObject(before[key])
      const b = asObject(after[key])
      const changes: Change[] = []
      for (const field of keys(a, b)) {
        if (key === '世界' && SKIP_WORLD.includes(field)) continue
        const sub = child(node, field, schema)
        diff([label(field, sub)], a[field], b[field], sub, schema, changes)
      }
      if (changes.length) groups.push({ key, title: label(key, node), changes })
    } else {
      diff([label(key, node)], before[key], after[key], node, schema, loose)
    }
  }
  // The world leads, as in the state display; loose fields close.
  groups.sort((a, b) => Number(b.key === '世界') - Number(a.key === '世界'))
  if (loose.length) groups.push({ key: '', title: '其他', changes: loose })
  return { roundNo: history.at(-1)!.round_no, groups }
}
