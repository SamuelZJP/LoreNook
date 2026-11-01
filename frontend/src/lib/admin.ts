import { PURPOSE_LABELS, STEP_LABELS } from './archive'

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

export const TABLE_LABELS: Record<string, string> = {
  chats: '聊天', characters: '角色', character_scenes: '开场', user_identities: '用户身份', definitions: '定义', writing_presets: '写作预设',
  model_configs: '模型配置', chat_model_bindings: '模型绑定', image_workflows: '图像工作流', chat_illustration_settings: '插图设置', chat_recall_settings: '记忆召回设置',
  cast_members: '画像人物', identity_appearances: '身份外貌',
  rounds: '回合', state_snapshots: '状态快照', episodes: '情节', illustrations: '插图',
}

export function preview(value: unknown, max = 80): string {
  if (value === null || value === undefined) return '—'
  const text = typeof value === 'string' ? value : JSON.stringify(value)
  return text.length > max ? `${text.slice(0, max)}…` : text
}

// ---- Scopes and display ----

/** A chat id, or `LIBRARY` for rows not owned by any chat. */
export const LIBRARY = 'library'

export const CHAT_TABLE_GROUPS: { label: string; tables: string[] }[] = [
  { label: '历史', tables: ['rounds', 'state_snapshots', 'episodes', 'illustrations'] },
  { label: '聊天副本', tables: ['chats', 'characters', 'character_scenes', 'user_identities', 'definitions', 'writing_presets', 'model_configs', 'chat_model_bindings', 'image_workflows', 'chat_illustration_settings', 'chat_recall_settings', 'cast_members', 'identity_appearances'] },
]
export const LIBRARY_TABLES = ['characters', 'character_scenes', 'user_identities', 'definitions', 'writing_presets', 'model_configs', 'image_workflows', 'cast_members', 'identity_appearances']

/** Tables whose rows are ordered by round and can be sorted either way. */
export const ROUND_ORDERED = ['rounds', 'state_snapshots', 'episodes', 'illustrations']

/** Rows of every table as staged, used to resolve references for titles and scopes. */
export type Lookup = Record<string, Map<string, Row>>

export function buildLookup(tables: Record<string, StagedRow[]>): Lookup {
  const out: Lookup = {}
  for (const [name, rows] of Object.entries(tables)) {
    out[name] = new Map(rows.filter((s) => s.row.id != null).map((s) => [String(s.row.id), s.row]))
  }
  return out
}

const lookupRow = (lookup: Lookup, table: string, id: unknown) => (id == null ? undefined : lookup[table]?.get(String(id)))

/** The chat id a row belongs to, or `LIBRARY`. Definitions and scenes belong to their owner's chat. */
export function scopeOf(table: string, row: Row, lookup: Lookup): string {
  if (table === 'chats') return String(row.id)
  if (table === 'character_scenes') {
    const owner = lookupRow(lookup, 'characters', row.character_id)
    return owner?.chat_id != null ? String(owner.chat_id) : LIBRARY
  }
  if (table === 'definitions' || table === 'cast_members' || table === 'identity_appearances') {
    const owner = lookupRow(lookup, 'characters', row.character_id) ?? lookupRow(lookup, 'user_identities', row.user_identity_id)
    return owner?.chat_id != null ? String(owner.chat_id) : LIBRARY
  }
  return row.chat_id != null ? String(row.chat_id) : LIBRARY
}

const roundNo = (lookup: Lookup, id: unknown) => lookupRow(lookup, 'rounds', id)?.round_no as number | undefined
const nameOf = (row: Row | undefined) => (row ? String(row.name ?? '') : '')
const firstLine = (text: unknown) => String(text ?? '').trim().split('\n')[0]

/** Position used to sort round-ordered tables. */
export function roundOrder(table: string, row: Row, lookup: Lookup): number {
  if (table === 'rounds') return Number(row.round_no ?? 0)
  if (table === 'state_snapshots') return row.round_id == null ? 0 : (roundNo(lookup, row.round_id) ?? 0)
  if (table === 'episodes') return roundNo(lookup, row.start_round_id) ?? 0
  if (table === 'illustrations') return roundNo(lookup, row.round_id) ?? 0
  return 0
}

function roundRange(lookup: Lookup, start: unknown, end: unknown): string {
  const a = roundNo(lookup, start)
  const b = roundNo(lookup, end)
  return `第 ${a ?? '?'}–${b ?? '?'} 回合`
}

/** Human-readable card title. */
export function rowTitle(table: string, row: Row, lookup: Lookup): string {
  switch (table) {
    case 'chats': return String(row.title || '未命名聊天')
    case 'definitions': {
      const owner = lookupRow(lookup, 'characters', row.character_id) ?? lookupRow(lookup, 'user_identities', row.user_identity_id)
      return `#${row.order ?? 0} · ${nameOf(owner) || '未知所有者'}`
    }
    case 'character_scenes':
      return `#${row.order ?? 0} · ${nameOf(lookupRow(lookup, 'characters', row.character_id)) || '未知角色'} · ${row.name || '未命名'}`
    case 'chat_model_bindings':
      return `${PURPOSE_LABELS[row.purpose as keyof typeof PURPOSE_LABELS] ?? row.purpose} → ${nameOf(lookupRow(lookup, 'model_configs', row.model_config_id)) || '未知模型'}`
    case 'rounds': return `第 ${row.round_no ?? '?'} 回合`
    case 'state_snapshots': {
      if (row.round_id == null) return '初始状态'
      const n = roundNo(lookup, row.round_id)
      return n == null ? '未知回合后' : `第 ${n} 回合后`
    }
    case 'episodes': return String(row.title || '未命名情节')
    case 'illustrations': return `第 ${roundNo(lookup, row.round_id) ?? '?'} 回合插图`
    case 'chat_illustration_settings': return '插图设置'
    case 'chat_recall_settings': return '记忆召回设置'
    case 'identity_appearances': return nameOf(lookupRow(lookup, 'user_identities', row.user_identity_id)) || '未知身份'
    default: return String(row.name || '未命名')
  }
}

export interface Detail { label: string; value: string }

function worldLine(content: unknown): string {
  const w = (content as Record<string, any> | null)?.['世界']
  if (!w || typeof w !== 'object') return '—'
  return [[w['日期'], w['星期'], w['时间']].filter(Boolean).join(' '), w['地点']].filter(Boolean).join(' · ') || '—'
}

/** A few short fields shown under the title. */
export function rowDetails(table: string, row: Row, lookup: Lookup): Detail[] {
  const d = (label: string, value: unknown): Detail => ({ label, value: preview(value) })
  switch (table) {
    case 'chats': return [d('近期回合', row.recent_rounds), d('最少摘要', row.min_summaries), d('写作预设', nameOf(lookupRow(lookup, 'writing_presets', row.writing_preset_id)) || null)]
    case 'characters':
    case 'user_identities': return [d('描述', firstLine(row.description) || null)]
    case 'definitions': return [d('状态', [row.enabled ? '启用' : '停用', row.has_template ? '模板' : ''].filter(Boolean).join(' · ')), d('内容', firstLine(row.content) || null)]
    case 'character_scenes': return [d('开场', firstLine(row.first_message) || null), d('初始变量', row.initial_state)]
    case 'writing_presets': return [d('长度', `${String(row.source ?? '').length} 字符`)]
    case 'model_configs': return [d('接口', `${row.api_type} · ${row.model}`), d('密钥', row.has_api_key ? '已设置' : '未设置')]
    case 'chat_model_bindings': return []
    case 'rounds': return [
      d('归档', STEP_LABELS[row.archive_step as keyof typeof STEP_LABELS] ?? row.archive_step),
      ...(row.archive_error ? [d('错误', row.archive_error)] : []),
      d('输入', firstLine(row.user_input) || null),
      d('摘要', row.summary),
    ]
    case 'state_snapshots': return [d('世界', worldLine(row.content)), d('角色', nameOf(lookupRow(lookup, 'characters', row.character_id)) || null)]
    case 'episodes': return [d('范围', roundRange(lookup, row.start_round_id, row.end_round_id)), d('摘要', row.summary)]
    case 'image_workflows': return [d('地址', row.base_url), d('尺寸', `${row.width}×${row.height}`)]
    case 'chat_recall_settings': return [d('启用', row.enabled ? '是' : '否'), d('情节上限', row.episode_limit), d('摘要上限', row.summary_limit), d('模型', nameOf(lookupRow(lookup, 'model_configs', row.model_config_id)) || null), d('深度', row.depth)]
    case 'chat_illustration_settings': return [d('时机', row.mode), d('工作流', nameOf(lookupRow(lookup, 'image_workflows', row.image_workflow_id)) || null)]
    case 'cast_members': return [d('角色', nameOf(lookupRow(lookup, 'characters', row.character_id)) || null), d('外貌', firstLine(row.appearance) || null), d('参考图', row.reference_image ? '有' : '无')]
    case 'identity_appearances': return [d('外貌', firstLine(row.appearance) || null), d('参考图', row.reference_image ? '有' : '无')]
    case 'illustrations': return [d('状态', row.status), ...(row.error ? [d('错误', row.error)] : []), d('隐藏', row.hidden ? '是' : '否')]
    default: return []
  }
}
