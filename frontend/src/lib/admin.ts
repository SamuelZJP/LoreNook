/**
 * Staging for data-management batches. Pure functions over snapshot rows so the
 * pending set can be shown, reconciled after a conflict, and turned into operations.
 */
export type Row = Record<string, unknown>
export type Key = Record<string, string>

export interface PendingOp {
  uid: number
  action: 'create' | 'update' | 'delete'
  table: string
  /** Original primary key of the target (update/delete). */
  key?: Key
  /** Create: full values. Update: changed fields only. */
  values?: Row
  /** Snapshot of the target row when staged, used to detect concurrent changes. */
  base?: Row
}

/** Fields that reads add but writes reject. */
const READ_ONLY: Record<string, string[]> = { model_configs: ['has_api_key'] }

export function keyOf(row: Row, pk: string[]): Key {
  return Object.fromEntries(pk.map((k) => [k, String(row[k])]))
}

export function sameKey(a: Key | undefined, b: Key | undefined): boolean {
  if (!a || !b) return false
  const keys = Object.keys(a)
  return keys.length === Object.keys(b).length && keys.every((k) => a[k] === b[k])
}

export function keyLabel(key: Key | undefined): string {
  return key ? Object.values(key).join(' / ') : ''
}

const stable = (v: unknown) => JSON.stringify(v)

/** Fields of `edited` that differ from `original`, minus read-only fields. */
export function changedValues(table: string, original: Row, edited: Row): Row {
  const out: Row = {}
  const skip = READ_ONLY[table] ?? []
  for (const [k, v] of Object.entries(edited)) {
    if (skip.includes(k)) continue
    if (!(k in original) || stable(original[k]) !== stable(v)) out[k] = v
  }
  return out
}

export function stripReadOnly(table: string, row: Row): Row {
  const skip = READ_ONLY[table] ?? []
  return Object.fromEntries(Object.entries(row).filter(([k]) => !skip.includes(k)))
}

/** Rows of a table as they would look after the pending operations. */
export interface StagedRow {
  row: Row
  state: 'clean' | 'updated' | 'deleted' | 'created'
  op?: PendingOp
  original?: Row
}

export function stagedRows(rows: Row[], pk: string[], table: string, pending: PendingOp[]): StagedRow[] {
  const ops = pending.filter((p) => p.table === table)
  const out: StagedRow[] = rows.map((row) => {
    const key = keyOf(row, pk)
    const op = ops.find((p) => p.action !== 'create' && sameKey(p.key, key))
    if (!op) return { row, state: 'clean' }
    if (op.action === 'delete') return { row, state: 'deleted', op, original: row }
    return { row: { ...row, ...op.values }, state: 'updated', op, original: row }
  })
  for (const op of ops.filter((p) => p.action === 'create')) out.push({ row: op.values ?? {}, state: 'created', op })
  return out
}

export function toOperations(pending: PendingOp[]) {
  return pending.map((p) => {
    if (p.action === 'create') return { action: 'create' as const, table: p.table, values: p.values ?? {} }
    if (p.action === 'update') return { action: 'update' as const, table: p.table, key: p.key!, values: p.values ?? {} }
    return { action: 'delete' as const, table: p.table, key: p.key! }
  })
}

export interface Conflict { uid: number; reason: 'missing' | 'changed' }

/** After re-reading, find staged operations whose target vanished or changed meanwhile. */
export function findConflicts(pending: PendingOp[], tables: Record<string, Row[]>, pks: Record<string, string[]>): Conflict[] {
  const out: Conflict[] = []
  for (const p of pending) {
    if (p.action === 'create') continue
    const row = (tables[p.table] ?? []).find((r) => sameKey(keyOf(r, pks[p.table] ?? ['id']), p.key))
    if (!row) out.push({ uid: p.uid, reason: 'missing' })
    else if (p.base && stable(row) !== stable(p.base)) out.push({ uid: p.uid, reason: 'changed' })
  }
  return out
}

/** A new-row template from a JSON Schema: defaults, or empty values for required fields. */
export function templateFromSchema(schema: Record<string, any>): Row {
  const out: Row = {}
  const required: string[] = schema.required ?? []
  for (const [name, prop] of Object.entries<Record<string, any>>(schema.properties ?? {})) {
    if ('default' in prop) out[name] = prop.default
    else if (required.includes(name)) {
      const type = prop.type ?? prop.anyOf?.[0]?.type
      out[name] = type === 'integer' || type === 'number' ? (prop.minimum ?? 0) : type === 'boolean' ? false : type === 'object' ? {} : type === 'array' ? [] : (prop.enum?.[0] ?? '')
    }
  }
  return out
}

/** Short, human-friendly fields to show per table. */
export const SUMMARY_FIELDS: Record<string, string[]> = {
  chats: ['title', 'recent_rounds', 'min_summaries'],
  characters: ['name', 'chat_id'],
  user_identities: ['name', 'chat_id'],
  definitions: ['order', 'enabled', 'has_template', 'content'],
  writing_presets: ['name', 'chat_id'],
  model_configs: ['name', 'api_type', 'model', 'has_api_key', 'chat_id'],
  chat_model_bindings: ['purpose', 'model_config_id'],
  rounds: ['round_no', 'archive_step', 'user_input', 'summary'],
  state_snapshots: ['round_id', 'content'],
  episodes: ['title', 'summary'],
}

export const TABLE_LABELS: Record<string, string> = {
  chats: '聊天', characters: '角色', user_identities: '用户身份', definitions: '定义', writing_presets: '写作预设',
  model_configs: '模型配置', chat_model_bindings: '模型绑定', rounds: '回合', state_snapshots: '状态快照', episodes: '情节',
}

export function preview(value: unknown, max = 80): string {
  if (value === null || value === undefined) return '—'
  const text = typeof value === 'string' ? value : JSON.stringify(value)
  return text.length > max ? `${text.slice(0, max)}…` : text
}
