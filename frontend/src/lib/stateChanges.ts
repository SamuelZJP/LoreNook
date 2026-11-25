/**
 * Plans the "最近变化" list: what changed between consecutive state snapshots.
 * Labels follow the chat Schema like the state display; the clock (世界.时间 / 星期) and hidden
 * fields are left out, since they change every round or are not for the reader. Plain data only.
 */
import { child, isObject, isScalar, label, resolve, type Json, type SchemaNode } from './stateDisplay'

export type Change =
  | { kind: 'number'; label: string; from: number | null; to: number }
  | { kind: 'text'; label: string; to: string }
  | { kind: 'flag'; label: string; to: boolean }
  | { kind: 'list'; label: string; added: string[]; removed: string[] }
  | { kind: 'cleared'; label: string }

export interface RoundChanges { roundNo: number; changes: Change[] }

const SKIP_WORLD = ['时间', '星期']
const same = (a: Json | undefined, b: Json | undefined) => JSON.stringify(a) === JSON.stringify(b)
const isEmpty = (v: Json | undefined) => v === undefined || v === null || v === '' || (Array.isArray(v) && !v.length)

function diff(path: string[], before: Json | undefined, after: Json | undefined, node: SchemaNode, root: SchemaNode | null, out: Change[]) {
  if (node.display === 'hidden' || same(before, after)) return
  const name = path.join(' · ')
  if (isObject(after) || isObject(before)) {
    const a = isObject(before) ? before : {}
    const b = isObject(after) ? after : {}
    for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) {
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
      out.push({ kind: 'list', label: name, added: now.filter((v) => !was.includes(v)), removed: was.filter((v) => !now.includes(v)) })
    } else {
      out.push({ kind: 'text', label: name, to: `${after.length} 项` })
    }
  } else {
    out.push({ kind: 'text', label: name, to: String(after) })
  }
}

/** Changes per round, newest first, for at most `rounds` rounds and `limit` lines in all. */
export function planStateChanges(
  history: { round_no: number; content: Record<string, unknown> }[],
  schema: SchemaNode | null,
  { rounds = 3, limit = 8 } = {},
): RoundChanges[] {
  const root = schema ? resolve(schema, schema) : {}
  const out: RoundChanges[] = []
  let left = limit
  for (let i = history.length - 1; i > 0 && out.length < rounds && left > 0; i--) {
    const before = history[i - 1].content as Record<string, Json>
    const after = history[i].content as Record<string, Json>
    const changes: Change[] = []
    for (const key of new Set([...Object.keys(before), ...Object.keys(after)])) {
      const node = child(root, key, schema)
      if (key === '世界') {
        const a = isObject(before[key]) ? before[key] : {}
        const b = isObject(after[key]) ? after[key] : {}
        for (const field of new Set([...Object.keys(a), ...Object.keys(b)])) {
          if (SKIP_WORLD.includes(field)) continue
          const sub = child(node, field, schema)
          diff([label(field, sub)], a[field], b[field], sub, schema, changes)
        }
      } else {
        diff([label(key, node)], before[key], after[key], node, schema, changes)
      }
    }
    const list = changes.filter((c) => c.kind !== 'list' || c.added.length || c.removed.length)
    if (!list.length) continue
    out.push({ roundNo: history[i].round_no, changes: list.slice(0, left) })
    left -= Math.min(list.length, left)
  }
  return out
}
