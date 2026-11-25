<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  RefreshCw, Plus, Pencil, Trash2, Undo2, Send, AlertTriangle, Check, ArrowLeft, ArrowDownWideNarrow, ArrowUpNarrowWide, Copy, Library,
} from 'lucide-vue-next'
import { api, type AdminTableInfo, type AdminSnapshot } from '@/api/endpoints'
import { ApiError } from '@/api/client'
import TopBar from '@/components/TopBar.vue'
import ErrorBox from '@/components/ErrorBox.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import JsonField, { jsonProblem } from '@/components/editors/JsonField.vue'
import { toast } from '@/composables/toast'
import { pretty } from '@/lib/format'
import { prefs } from '@/lib/prefs'
import { STEP_LABELS } from '@/lib/archive'
import {
  CHAT_TABLE_GROUPS, LIBRARY, LIBRARY_TABLES, ROUND_ORDERED, TABLE_LABELS, buildLookup, changedValues, findConflicts, keyLabel, keyOf,
  rowDetails, rowTitle, roundOrder, sameKey, scopeOf, stagedRows, stripReadOnly, templateFromSchema, toOperations,
  type Conflict, type PendingOp, type Row, type StagedRow,
} from '@/lib/admin'

const route = useRoute()
const router = useRouter()

const schema = shallowRef<AdminTableInfo[]>([])
const snapshot = shallowRef<AdminSnapshot | null>(null)
const loadError = ref<unknown>(null)
const loading = ref(false)
const filter = ref('')
const limit = ref(50)

const pending = ref<PendingOp[]>([])
const conflicts = ref<Conflict[]>([])
let uid = 1

async function load(keepPending = false) {
  loading.value = true
  loadError.value = null
  try {
    const [s, d] = await Promise.all([schema.value.length ? Promise.resolve(schema.value) : api.adminSchema(), api.adminData()])
    schema.value = s
    snapshot.value = d
    if (!keepPending) pending.value = []
    conflicts.value = findConflicts(pending.value, d.tables as Record<string, Row[]>, pks.value)
  } catch (e) {
    loadError.value = e
  } finally {
    loading.value = false
  }
}
load()

const pks = computed(() => Object.fromEntries(schema.value.map((t) => [t.name, t.primary_key])))
const pkOf = (name: string) => pks.value[name] ?? ['id']

/** Every table as it would look after the pending operations. */
const allStaged = computed<Record<string, StagedRow[]>>(() => Object.fromEntries(schema.value.map((t) => [
  t.name, stagedRows((snapshot.value?.tables[t.name] ?? []) as Row[], t.primary_key, t.name, pending.value),
])))
const lookup = computed(() => buildLookup(allStaged.value))

// ---- Scope and table (from the route) ----
const scope = computed(() => (route.params.scope as string) || null)
const isLibrary = computed(() => scope.value === LIBRARY)
const scopeTables = computed(() => (isLibrary.value ? LIBRARY_TABLES : CHAT_TABLE_GROUPS.flatMap((g) => g.tables)))
const table = computed(() => {
  const t = route.params.table as string
  return scopeTables.value.includes(t) ? t : scopeTables.value[0]
})
const tableGroups = computed(() => (isLibrary.value ? [{ label: '资源库', tables: LIBRARY_TABLES }] : CHAT_TABLE_GROUPS))

function go(nextScope: string | null, nextTable?: string) {
  router.push(nextScope ? `/data/${nextScope}${nextTable ? `/${nextTable}` : ''}` : '/data')
}
watch([scope, table], () => {
  limit.value = 50
  filter.value = ''
})

const info = computed(() => schema.value.find((t) => t.name === table.value))
const pk = computed(() => info.value?.primary_key ?? ['id'])
const inScope = (name: string, row: Row) => scopeOf(name, row, lookup.value) === scope.value

const chatItems = computed(() => {
  const rounds = allStaged.value.rounds ?? []
  const characters = allStaged.value.characters ?? []
  return (allStaged.value.chats ?? []).map((s) => {
    const id = String(s.row.id)
    const own = rounds.filter((r) => r.row.chat_id === id && r.state !== 'deleted').map((r) => r.row)
    const last = own.reduce<Row | null>((a, r) => (!a || Number(r.round_no) > Number(a.round_no) ? r : a), null)
    const character = characters.find((c) => c.row.chat_id === id)?.row
    return {
      id, state: s.state, title: rowTitle('chats', s.row, lookup.value),
      sub: [character?.name, `${own.length} 回合`].filter(Boolean).join(' · '),
      step: last && last.archive_step !== 'complete' ? STEP_LABELS[last.archive_step as keyof typeof STEP_LABELS] : null,
      activity: String(last?.created_at ?? s.row.created_at ?? ''),
    }
  }).sort((a, b) => b.activity.localeCompare(a.activity))
})
const scopeTitle = computed(() => (isLibrary.value ? '资源库原始数据' : chatItems.value.find((c) => c.id === scope.value)?.title ?? '未知聊天'))

const staged = computed(() => {
  if (!scope.value) return []
  const q = filter.value.trim().toLowerCase()
  const name = table.value
  const out = (allStaged.value[name] ?? []).filter((s) => inScope(name, s.row) && (!q || JSON.stringify(s.row).toLowerCase().includes(q)))
  if (ROUND_ORDERED.includes(name)) {
    const dir = prefs.dataNewestFirst ? -1 : 1
    out.sort((a, b) => dir * (roundOrder(name, a.row, lookup.value) - roundOrder(name, b.row, lookup.value)))
  } else if (name === 'definitions' || name === 'character_scenes') {
    out.sort((a, b) => rowTitle(name, a.row, lookup.value).localeCompare(rowTitle(name, b.row, lookup.value), undefined, { numeric: true }))
  }
  return out
})

/** The row a pending operation targets, as staged. */
const opRow = (p: PendingOp): Row => (p.action === 'create' ? p.values ?? {} : { ...p.base, ...p.values })
const opScope = (p: PendingOp) => scopeOf(p.table, opRow(p), lookup.value)
const pendingIn = (s: string, name?: string) => pending.value.filter((p) => opScope(p) === s && (!name || p.table === name)).length
const tableCount = (name: string) => (allStaged.value[name] ?? []).filter((s) => inScope(name, s.row)).length
const conflictFor = (op?: PendingOp) => (op ? conflicts.value.find((c) => c.uid === op.uid) : undefined)
const scopeName = (s: string) => (s === LIBRARY ? '资源库' : chatItems.value.find((c) => c.id === s)?.title ?? '未知聊天')

// ---- Row editing ----
const editing = ref<{ target: StagedRow | null; text: string; error?: string } | null>(null)
const editingKey = computed(() => {
  const t = editing.value?.target
  return t ? keyLabel(keyOf(t.original ?? t.row, pk.value)) : ''
})

/** Table of the row in the edit dialog; fixed when it opens. */
const editTable = ref('')

function openEdit(s: StagedRow) {
  editTable.value = table.value
  editing.value = { target: s, text: pretty(s.row) }
}
function openCreate(name = table.value) {
  const tableInfo = schema.value.find((t) => t.name === name)
  const tpl = tableInfo ? templateFromSchema(tableInfo.row_schema as Record<string, unknown>) : {}
  const props = ((tableInfo?.row_schema as Record<string, any>)?.properties ?? {}) as Record<string, unknown>
  // A fixed id lets other staged rows reference the new one.
  if ('id' in props && !tpl.id) tpl.id = crypto.randomUUID()
  if (!isLibrary.value && scope.value && name !== 'chats') {
    if ('chat_id' in props) tpl.chat_id = scope.value
    if (name === 'definitions' || name === 'state_snapshots' || name === 'character_scenes') {
      const character = (allStaged.value.characters ?? []).find((c) => c.row.chat_id === scope.value)
      if (character) tpl.character_id = character.row.id
    }
  }
  editTable.value = name
  editing.value = { target: null, text: pretty(tpl) }
}
function applyEdit() {
  const e = editing.value
  const name = editTable.value
  if (!e || jsonProblem(e.text)) return
  const values = JSON.parse(e.text) as Row
  const t = e.target
  if (!t) {
    pending.value.push({ uid: uid++, action: 'create', table: name, values: stripReadOnly(name, values) })
  } else if (t.state === 'created') {
    t.op!.values = stripReadOnly(name, values)
  } else {
    const original = t.original ?? t.row
    const changed = changedValues(name, original, values)
    const existing = t.op
    if (existing && existing.action === 'update') {
      if (Object.keys(changed).length) existing.values = changed
      else pending.value = pending.value.filter((p) => p !== existing)
    } else if (Object.keys(changed).length) {
      pending.value.push({ uid: uid++, action: 'update', table: name, key: keyOf(original, pkOf(name)), values: changed, base: original })
    }
  }
  pending.value = [...pending.value]
  if (!t && name === 'chats' && values.id) go(String(values.id), 'chats')
  editing.value = null
}
function stageDelete(s: StagedRow) {
  if (s.state === 'created') {
    pending.value = pending.value.filter((p) => p !== s.op)
    return
  }
  const key = keyOf(s.original ?? s.row, pk.value)
  pending.value = pending.value.filter((p) => !(p.table === table.value && sameKey(p.key, key)))
  pending.value.push({ uid: uid++, action: 'delete', table: table.value, key, base: s.original ?? s.row })
}
function unstage(op?: PendingOp) {
  if (!op) return
  pending.value = pending.value.filter((p) => p !== op)
  conflicts.value = conflicts.value.filter((c) => c.uid !== op.uid)
}
/** Accept the newer row as the base for a conflicting operation. */
function rebase(op: PendingOp) {
  const row = ((snapshot.value?.tables[op.table] ?? []) as Row[]).find((r) => sameKey(keyOf(r, pkOf(op.table)), op.key))
  if (row) op.base = row
  conflicts.value = conflicts.value.filter((c) => c.uid !== op.uid)
}
async function copyKey() {
  try {
    await navigator.clipboard.writeText(editingKey.value)
    toast('已复制')
  } catch {
    toast('复制失败', 'error')
  }
}

// ---- Submit ----
const submitting = ref(false)
const submitError = ref<unknown>(null)
const lastResult = ref<{ count: number; revision: string } | null>(null)
const stale = ref(false)

async function submit() {
  if (!snapshot.value || !pending.value.length || conflicts.value.length) return
  if (!confirm(`提交 ${pending.value.length} 项更改？整批原子执行，任何一项失败都会全部回滚。`)) return
  submitting.value = true
  submitError.value = null
  stale.value = false
  try {
    const result = await api.adminBatch({ expected_revision: snapshot.value.revision, operations: toOperations(pending.value) as never })
    lastResult.value = { count: result.changes.length, revision: result.revision }
    toast(`已提交 ${result.changes.length} 项更改`)
    await load(false)
  } catch (e) {
    submitError.value = e
    // 409 can be a stale revision; re-read and let the user reconcile.
    if (e instanceof ApiError && e.status === 409) stale.value = true
  } finally {
    submitting.value = false
  }
}
async function reloadKeeping() {
  stale.value = false
  submitError.value = null
  await load(true)
  if (conflicts.value.length) toast(`${conflicts.value.length} 项待提交更改与最新数据冲突，请处理`, 'error')
}
function opLabel(p: PendingOp) {
  return { create: '新建', update: '修改', delete: '删除' }[p.action]
}
</script>

<template>
  <div class="data-view">
    <TopBar>
      <RouterLink to="/settings/advanced" class="btn ghost icon small" aria-label="返回设置"><ArrowLeft /></RouterLink>
      <h1 class="grow">聊天数据</h1>
      <button class="btn ghost icon" type="button" title="重新读取" :disabled="loading" @click="pending.length ? reloadKeeping() : load()"><RefreshCw /></button>
    </TopBar>
    <ErrorBox v-if="loadError" :error="loadError" title="读取失败" class="load-error" />
    <div class="split" :class="{ detail: !!scope }">
      <div class="master">
        <div class="row master-head">
          <span class="faint grow">{{ chatItems.length }} 个聊天</span>
          <button class="btn small" type="button" title="新建聊天行" :disabled="!snapshot" @click="openCreate('chats')"><Plus /> 新建</button>
        </div>
        <div v-if="snapshot && !chatItems.length" class="empty">还没有聊天</div>
        <div class="stack tight">
          <button
            v-for="c in chatItems" :key="c.id" type="button" class="list-item" :class="[{ active: scope === c.id }, c.state]"
            @click="go(c.id)"
          >
            <div class="grow">
              <div class="ellipsis name">{{ c.title }}</div>
              <div class="faint ellipsis sub">{{ c.sub }}</div>
            </div>
            <span v-if="c.step" class="badge warn" title="归档未完成">{{ c.step }}</span>
            <span v-if="pendingIn(c.id)" class="badge accent" title="待提交更改">{{ pendingIn(c.id) }}</span>
          </button>
        </div>
        <div class="library-entry">
          <button type="button" class="list-item" :class="{ active: isLibrary }" @click="go(LIBRARY)">
            <Library class="lib-icon" />
            <div class="grow">
              <div class="ellipsis name">资源库原始数据</div>
              <div class="faint ellipsis sub">不属于任何聊天的记录</div>
            </div>
            <span v-if="pendingIn(LIBRARY)" class="badge accent">{{ pendingIn(LIBRARY) }}</span>
          </button>
          <p v-if="snapshot" class="faint revision">修订号 <code>{{ snapshot.revision.slice(0, 12) }}</code></p>
        </div>
      </div>

      <div class="detail-pane">
        <div v-if="!scope" class="page-inner stack">
          <p class="hint">
            高级功能：直接读取和批量修改全部业务数据，包括历史回合、状态、摘要、情节和归档字段。提交时会校验整体一致性并原子执行，不会调用模型、执行 Schema 或重新计算其他结果。模型密钥默认隐藏。
          </p>
          <div class="empty">选择左侧的聊天查看和编辑其数据。</div>
        </div>
        <div v-else-if="snapshot" class="page-inner stack">
          <button class="btn ghost small back" type="button" @click="go(null)"><ArrowLeft /> 返回列表</button>
          <h2 class="scope-title ellipsis">{{ scopeTitle }}</h2>
          <p v-if="isLibrary" class="hint">资源库中的角色、身份、预设和模型通常在「资源库」页面编辑。这里提供原始行级编辑，修改不会影响已创建的聊天。</p>

          <div class="groups">
            <div v-for="g in tableGroups" :key="g.label" class="group">
              <span class="group-label faint">{{ g.label }}</span>
              <div class="row wrap tables">
                <button
                  v-for="t in g.tables" :key="t" type="button" class="btn small" :class="{ primary: table === t }"
                  @click="go(scope, t)"
                >
                  {{ TABLE_LABELS[t] ?? t }}
                  <span class="count">{{ tableCount(t) }}</span>
                  <span v-if="pendingIn(scope, t)" class="badge warn">{{ pendingIn(scope, t) }}</span>
                </button>
              </div>
            </div>
          </div>

          <div class="row wrap">
            <input v-model="filter" class="input grow search" :placeholder="`在${TABLE_LABELS[table] ?? table}中搜索`" />
            <button
              v-if="ROUND_ORDERED.includes(table)" class="btn" type="button" :title="prefs.dataNewestFirst ? '当前：最新在前' : '当前：最早在前'"
              @click="prefs.dataNewestFirst = !prefs.dataNewestFirst"
            >
              <ArrowDownWideNarrow v-if="prefs.dataNewestFirst" /><ArrowUpNarrowWide v-else />
              {{ prefs.dataNewestFirst ? '倒序' : '正序' }}
            </button>
            <button v-if="table !== 'chats'" class="btn" type="button" @click="openCreate()"><Plus /> 新建{{ TABLE_LABELS[table] ?? '' }}</button>
          </div>

          <div v-if="!staged.length" class="empty">没有记录</div>
          <div class="rows">
            <div v-for="s in staged.slice(0, limit)" :key="s.op?.uid ?? keyLabel(keyOf(s.row, pk))" class="row-card card" :class="s.state">
              <div class="row">
                <strong class="title grow ellipsis">{{ rowTitle(table, s.row, lookup) }}</strong>
                <span v-if="s.state === 'created'" class="badge ok">将新建</span>
                <span v-else-if="s.state === 'updated'" class="badge warn">已修改</span>
                <span v-else-if="s.state === 'deleted'" class="badge danger">将删除</span>
                <span v-if="conflictFor(s.op)" class="badge danger"><AlertTriangle /> 冲突</span>
                <button v-if="s.state !== 'clean'" class="btn ghost icon small" type="button" title="撤销" @click="unstage(s.op)"><Undo2 /></button>
                <button v-if="s.state !== 'deleted'" class="btn ghost icon small" type="button" title="编辑" @click="openEdit(s)"><Pencil /></button>
                <button v-if="s.state !== 'deleted'" class="btn ghost icon small danger" type="button" title="删除" @click="stageDelete(s)"><Trash2 /></button>
              </div>
              <dl v-if="rowDetails(table, s.row, lookup).length" class="fields">
                <template v-for="f in rowDetails(table, s.row, lookup)" :key="f.label">
                  <dt>{{ f.label }}</dt><dd>{{ f.value }}</dd>
                </template>
              </dl>
            </div>
          </div>
          <button v-if="staged.length > limit" class="btn" type="button" @click="limit += 100">显示更多（剩余 {{ staged.length - limit }}）</button>
        </div>
      </div>
    </div>

    <div v-if="pending.length || submitError || lastResult" class="tray">
      <div class="tray-inner stack tight">
        <ErrorBox v-if="submitError" :error="submitError" title="提交失败，已全部回滚">
          <div v-if="stale" class="row wrap stale">
            <span>数据可能已在别处被修改。重新读取最新数据后，待提交的更改会保留，并标记出受影响的项。</span>
            <button class="btn small" type="button" @click="reloadKeeping"><RefreshCw /> 重新读取并核对</button>
          </div>
        </ErrorBox>
        <div v-if="lastResult && !pending.length" class="row ok-line"><Check /> 上次提交成功：{{ lastResult.count }} 项更改。<button class="btn ghost small" type="button" @click="lastResult = null">关闭</button></div>
        <details v-if="pending.length" class="pending">
          <summary class="row">
            <strong class="grow">{{ pending.length }} 项待提交更改</strong>
          </summary>
          <ul>
            <li v-for="p in pending" :key="p.uid" class="row">
              <span class="badge" :class="p.action === 'delete' ? 'danger' : p.action === 'create' ? 'ok' : 'warn'">{{ opLabel(p) }}</span>
              <span class="grow ellipsis">
                <span class="faint">{{ scopeName(opScope(p)) }} · {{ TABLE_LABELS[p.table] ?? p.table }} · </span>{{ rowTitle(p.table, opRow(p), lookup) }}
                <span v-if="p.action === 'update'" class="faint"> · {{ Object.keys(p.values ?? {}).join(', ') }}</span>
              </span>
              <template v-if="conflictFor(p)">
                <span class="badge danger">{{ conflictFor(p)!.reason === 'missing' ? '目标已不存在' : '目标已被修改' }}</span>
                <button v-if="conflictFor(p)!.reason === 'changed'" class="btn small" type="button" @click="rebase(p)">基于最新数据保留</button>
              </template>
              <button class="btn ghost icon small" type="button" title="撤销" @click="unstage(p)"><Undo2 /></button>
            </li>
          </ul>
        </details>
        <div v-if="pending.length" class="row">
          <span v-if="conflicts.length" class="hint warn-text">请先处理 {{ conflicts.length }} 项冲突</span>
          <span class="spacer" />
          <button class="btn" type="button" @click="pending = []; conflicts = []">全部撤销</button>
          <button class="btn primary" type="button" :disabled="submitting || !!conflicts.length" @click="submit"><Send /> {{ submitting ? '提交中…' : '提交批次' }}</button>
        </div>
      </div>
    </div>

    <ModalDialog
      v-if="editing" width="820px" @close="editing = null"
      :title="editing.target ? `编辑${TABLE_LABELS[editTable] ?? editTable}：${rowTitle(editTable, editing.target.row, lookup)}` : `新建${TABLE_LABELS[editTable] ?? editTable}`"
    >
      <div class="stack">
        <div v-if="editingKey" class="row key-line">
          <span class="faint">主键（{{ pk.join(', ') }}）</span>
          <code class="grow ellipsis">{{ editingKey }}</code>
          <button class="btn ghost icon small" type="button" title="复制主键" @click="copyKey"><Copy /></button>
        </div>
        <p class="hint">编辑完整行 JSON。只有变化的字段会作为修改提交；修改主键会同时改变记录键。<template v-if="editTable === 'model_configs'"> <code>has_api_key</code> 只读；要设置或清除密钥，请添加 <code>api_key</code> 字段（空字符串表示清除）。</template></p>
        <JsonField v-model="editing.text" min-height="320px" max-height="60vh" />
      </div>
      <template #footer>
        <button class="btn" type="button" @click="editing = null">取消</button>
        <button class="btn primary" type="button" :disabled="!!jsonProblem(editing.text)" @click="applyEdit">暂存更改</button>
      </template>
    </ModalDialog>
  </div>
</template>

<style scoped>
.data-view { display: flex; flex-direction: column; height: 100%; }
.load-error { margin: var(--space-3) var(--space-4) 0; }
.split { flex: 1; min-height: 0; display: flex; }
.master { width: 300px; flex-shrink: 0; border-right: 1px solid var(--border); overflow-y: auto; padding: var(--space-3) var(--space-3); display: flex; flex-direction: column; }
.master-head { margin-bottom: var(--space-2); padding: 0 var(--space-1); }
.master .list-item { width: 100%; border: 0; background: none; text-align: left; font: inherit; color: inherit; }
.master .list-item.active { background: var(--bg-active); }
.master .list-item.created .name { color: var(--ok); }
.master .list-item.updated .name { color: var(--warn); }
.master .list-item.deleted .name { color: var(--danger); text-decoration: line-through; }
.name { font-weight: 500; }
.sub { font-size: var(--text-xs); }
.library-entry { margin-top: auto; padding-top: var(--space-3); border-top: 1px solid var(--border); }
.lib-icon { width: 18px; height: 18px; color: var(--text-muted); flex-shrink: 0; }
.revision { font-size: var(--text-xs); margin: var(--space-1-5) var(--space-3) 0; }
.detail-pane { flex: 1; min-width: 0; overflow-y: auto; }
.back { display: none; align-self: flex-start; }
.scope-title { margin: 0; font-size: var(--text-xl); }
.groups { display: flex; flex-direction: column; gap: var(--space-2); }
.group { display: flex; align-items: baseline; gap: var(--space-3); }
.group-label { font-size: var(--text-xs); width: 56px; flex-shrink: 0; }
.tables { gap: var(--space-1-5); }
.count { opacity: 0.7; font-size: var(--text-xs); }
.search { min-width: 180px; }
.small { font-size: var(--text-xs); }
.rows { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: var(--space-2); }
.row-card { padding: var(--space-2) var(--space-3); display: flex; flex-direction: column; gap: var(--space-1-5); min-width: 0; }
.row-card.updated { border-color: var(--warn); }
.row-card.created { border-color: var(--ok); }
.row-card.deleted { border-color: var(--danger); opacity: 0.7; }
.row-card.deleted .fields, .row-card.deleted .title { text-decoration: line-through; }
.title { font-size: var(--text-md); font-weight: 600; }
.badge svg { width: 12px; height: 12px; }
.fields { display: grid; grid-template-columns: auto 1fr; gap: var(--space-0-5) var(--space-3); margin: 0; font-size: var(--text-xs); }
.fields dt { color: var(--text-faint); }
.fields dd { margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.key-line { font-size: var(--text-xs); padding: var(--space-1-5) var(--space-3); background: var(--bg-sunken); border-radius: var(--radius-s); }
.tray { flex-shrink: 0; border-top: 1px solid var(--border); background: var(--bg-elev); box-shadow: var(--shadow-pop); max-height: 50dvh; overflow-y: auto; }
.tray-inner { max-width: 1080px; margin: 0 auto; padding: var(--space-3) var(--space-4) calc(var(--space-3) + env(safe-area-inset-bottom)); }
.pending summary { cursor: pointer; }
.pending ul { list-style: none; margin: var(--space-1-5) 0 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-1); font-size: var(--text-sm); }
.stale { margin-top: var(--space-1-5); font-size: var(--text-sm); }
.ok-line { color: var(--ok); }
.ok-line svg { width: 16px; height: 16px; }
.warn-text { color: var(--warn); }
@media (max-width: 899px) {
  .master { width: 100%; border-right: 0; }
  .detail-pane { display: none; }
  .split.detail .master { display: none; }
  .split.detail .detail-pane { display: block; }
  .back { display: inline-flex; }
}
@media (max-width: 640px) {
  .rows { grid-template-columns: 1fr; }
  .group { flex-direction: column; gap: var(--space-1); }
}
</style>
