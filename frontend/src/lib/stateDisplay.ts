/**
 * Plans how a state is shown: `世界` as the scene, then one card per other top-level object.
 * Display hints come from the chat Schema's JSON Schema (`display`, `max`, `title`,
 * `description`); without one, the value's type decides. Plain data only; components render it.
 */

type Json = null | boolean | number | string | Json[] | { [key: string]: Json }
type SchemaNode = Record<string, any>

export type Item =
  | { kind: 'text'; key: string; label: string; hint?: string; value: string }
  | { kind: 'dot'; key: string; label: string; hint?: string; value: boolean }
  | { kind: 'bar'; key: string; label: string; hint?: string; value: number; max: number; ratio: number }
  | { kind: 'tags'; key: string; label: string; hint?: string; value: string[] }
  | { kind: 'group'; key: string; label: string; hint?: string; items: Item[] }

export interface Card { key: string; title: string; hint?: string; items: Item[] }

export interface StateDisplay {
  scene: { date: string; weekday: string; time: string; place: string } | null
  /** `世界` fields beyond the four contract keys. */
  world: Item[]
  cards: Card[]
}

const WORLD_KEYS = ['日期', '星期', '时间', '地点']
const isObject = (v: unknown): v is Record<string, Json> => !!v && typeof v === 'object' && !Array.isArray(v)
const isScalar = (v: unknown) => v === null || ['string', 'number', 'boolean'].includes(typeof v)

/** Follows `$ref` and single-entry `allOf`, keeping sibling keys such as `display`. */
function resolve(node: SchemaNode | undefined, root: SchemaNode | null): SchemaNode {
  let current: SchemaNode = node ?? {}
  for (let depth = 0; depth < 8; depth++) {
    const { $ref, allOf, ...rest } = current
    let target: SchemaNode | undefined
    if (typeof $ref === 'string' && $ref.startsWith('#/') && root) {
      target = $ref.slice(2).split('/').reduce<any>((at, part) => at?.[part], root)
    } else if (Array.isArray(allOf) && allOf.length === 1) {
      target = allOf[0]
    }
    if (!target) return current
    // A referenced model's title is its class name, not this field's label.
    current = { ...target, title: undefined, ...rest }
  }
  return current
}

function child(node: SchemaNode, key: string, root: SchemaNode | null): SchemaNode {
  const props = node.properties?.[key]
  if (props) return resolve(props, root)
  if (isObject(node.additionalProperties)) return resolve(node.additionalProperties, root)
  return {}
}

/** Pydantic fills `title` from the field name; only a different title is the author's label. */
function label(key: string, node: SchemaNode): string {
  const auto = key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  return typeof node.title === 'string' && node.title !== auto && node.title !== key ? node.title : key
}

const hint = (node: SchemaNode) => (typeof node.description === 'string' ? node.description : undefined)
const isEmpty = (v: Json) => v === null || v === '' || (Array.isArray(v) && !v.length) || (isObject(v) && !Object.keys(v).length)

function item(key: string, value: Json, node: SchemaNode, root: SchemaNode | null): Item | null {
  const display = node.display
  if (display === 'hidden' || isEmpty(value)) return null
  const base = { key, label: label(key, node), hint: hint(node) }
  if (display === 'bar' && typeof value === 'number') {
    const max = typeof node.max === 'number' && node.max > 0 ? node.max : 100
    return { kind: 'bar', ...base, value, max, ratio: Math.max(0, Math.min(1, value / max)) }
  }
  if (typeof value === 'boolean') return { kind: 'dot', ...base, value }
  if (Array.isArray(value)) {
    if (value.every(isScalar)) return { kind: 'tags', ...base, value: value.map((v) => String(v)) }
    const items = value.map((v, i) => item(String(i + 1), v, resolve(node.items, root), root)).filter((x): x is Item => !!x)
    return items.length ? { kind: 'group', ...base, items } : null
  }
  if (isObject(value)) {
    const items = fields(value, node, root)
    return items.length ? { kind: 'group', ...base, items } : null
  }
  return { kind: 'text', ...base, value: String(value) }
}

function fields(value: Record<string, Json>, node: SchemaNode, root: SchemaNode | null, skip: string[] = []): Item[] {
  return Object.entries(value)
    .filter(([key]) => !skip.includes(key))
    .map(([key, v]) => item(key, v, child(node, key, root), root))
    .filter((x): x is Item => !!x)
}

export function planStateDisplay(state: Record<string, unknown> | null | undefined, schema: SchemaNode | null): StateDisplay {
  const root = schema ? resolve(schema, schema) : {}
  const content = (state ?? {}) as Record<string, Json>
  const world = isObject(content['世界']) ? content['世界'] : null
  const text = (v: Json | undefined) => (typeof v === 'string' ? v : '')
  const cards: Card[] = []
  const loose: Record<string, Json> = {}
  for (const [key, value] of Object.entries(content)) {
    if (key === '世界') continue
    const node = child(root, key, schema)
    if (node.display === 'hidden') continue
    if (isObject(value)) {
      const items = fields(value, node, schema)
      if (items.length) cards.push({ key, title: label(key, node), hint: hint(node), items })
    } else {
      loose[key] = value
    }
  }
  const rest = fields(loose, root, schema)
  if (rest.length) cards.push({ key: '', title: '其他', items: rest })
  return {
    scene: world ? { date: text(world['日期']), weekday: text(world['星期']), time: text(world['时间']), place: text(world['地点']) } : null,
    world: world ? fields(world, child(root, '世界', schema), schema, WORLD_KEYS) : [],
    cards,
  }
}
