<script setup lang="ts">
import { computed, ref, shallowRef } from 'vue'
import { RefreshCw, Plus, Pencil, Trash2, Undo2, Send, AlertTriangle, Check } from 'lucide-vue-next'
import { api, type AdminTableInfo, type AdminSnapshot } from '@/api/endpoints'
import { ApiError } from '@/api/client'
import TopBar from '@/components/TopBar.vue'
import ErrorBox from '@/components/ErrorBox.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import JsonField, { jsonProblem } from '@/components/editors/JsonField.vue'
import { toast } from '@/composables/toast'
import { pretty } from '@/lib/format'
import {
  SUMMARY_FIELDS, TABLE_LABELS, changedValues, findConflicts, keyLabel, keyOf, preview, sameKey,
  stagedRows, stripReadOnly, templateFromSchema, toOperations, type Conflict, type PendingOp, type Row, type StagedRow,
} from '@/lib/admin'

const schema = shallowRef<AdminTableInfo[]>([])
const snapshot = shallowRef<AdminSnapshot | null>(null)
const loadError = ref<unknown>(null)
const loading = ref(false)
const table = ref('chats')
const filter = ref('')
const chatFilter = ref('')
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
const info = computed(() => schema.value.find((t) => t.name === table.value))
const pk = computed(() => info.value?.primary_key ?? ['id'])
const rows = computed(() => ((snapshot.value?.tables[table.value] ?? []) as Row[]))
const chats = computed(() => (snapshot.value?.tables.chats ?? []) as Row[])
const hasChatColumn = computed(() => rows.value.some((r) => 'chat_id' in r))

const staged = computed(() => {
  const q = filter.value.trim().toLowerCase()
  return stagedRows(rows.value, pk.value, table.value, pending.value).filter((s) => {
    if (chatFilter.value && s.row.chat_id !== chatFilter.value && s.row.id !== chatFilter.value) return false
    return !q || JSON.stringify(s.row).toLowerCase().includes(q)
  })
})
const pendingCount = (name: string) => pending.value.filter((p) => p.table === name).length
const conflictFor = (op?: PendingOp) => (op ? conflicts.value.find((c) => c.uid === op.uid) : undefined)

// ---- Row editing ----
const editing = ref<{ target: StagedRow | null; text: string; error?: string } | null>(null)

function openEdit(s: StagedRow) {
  editing.value = { target: s, text: pretty(s.row) }
}
function openCreate() {
  const tpl = info.value ? templateFromSchema(info.value.row_schema as Record<string, unknown>) : {}
  if (chatFilter.value && 'chat_id' in tpl) tpl.chat_id = chatFilter.value
  editing.value = { target: null, text: pretty(tpl) }
}
function applyEdit() {
  const e = editing.value
  if (!e || jsonProblem(e.text)) return
  const values = JSON.parse(e.text) as Row
  const t = e.target
  if (!t) {
    pending.value.push({ uid: uid++, action: 'create', table: table.value, values: stripReadOnly(table.value, values) })
  } else if (t.state === 'created') {
    t.op!.values = stripReadOnly(table.value, values)
  } else {
    const original = t.original ?? t.row
    const changed = changedValues(table.value, original, values)
    const existing = t.op
    if (existing && existing.action === 'update') {
      if (Object.keys(changed).length) existing.values = changed
      else pending.value = pending.value.filter((p) => p !== existing)
    } else if (Object.keys(changed).length) {
      pending.value.push({ uid: uid++, action: 'update', table: table.value, key: keyOf(original, pk.value), values: changed, base: original })
    }
  }
  pending.value = [...pending.value]
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
  const row = ((snapshot.value?.tables[op.table] ?? []) as Row[]).find((r) => sameKey(keyOf(r, pks.value[op.table] ?? ['id']), op.key))
  if (row) op.base = row
  conflicts.value = conflicts.value.filter((c) => c.uid !== op.uid)
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
      <h1 class="grow">数据管理</h1>
      <button class="btn ghost icon" type="button" title="重新读取" :disabled="loading" @click="pending.length ? reloadKeeping() : load()"><RefreshCw /></button>
    </TopBar>
    <div class="page">
      <div class="page-inner stack">
        <p class="hint">
          高级功能：直接读取和批量修改全部业务数据，包括历史回合、状态、摘要、情节和归档字段。提交时会校验整体一致性并原子执行，不会调用模型、执行 Schema 或重新计算其他结果。模型密钥默认隐藏。
        </p>
        <ErrorBox v-if="loadError" :error="loadError" title="读取失败" />
        <template v-if="snapshot">
          <div class="row wrap tables">
            <button
              v-for="t in schema" :key="t.name" type="button" class="btn small" :class="{ primary: table === t.name }"
              @click="table = t.name; limit = 50"
            >
              {{ TABLE_LABELS[t.name] ?? t.name }}
              <span class="count">{{ (snapshot.tables[t.name] ?? []).length }}</span>
              <span v-if="pendingCount(t.name)" class="badge warn">{{ pendingCount(t.name) }}</span>
            </button>
          </div>

          <div class="row wrap">
            <input v-model="filter" class="input grow search" placeholder="在当前表中搜索" />
            <select v-if="hasChatColumn || table === 'chats'" v-model="chatFilter" class="select chat-pick">
              <option value="">全部聊天</option>
              <option v-for="c in chats" :key="String(c.id)" :value="c.id">{{ c.title }}</option>
            </select>
            <button class="btn" type="button" @click="openCreate"><Plus /> 新建行</button>
          </div>
          <p class="faint small">主键：<code>{{ pk.join(', ') }}</code> · 修订号 <code>{{ snapshot.revision.slice(0, 12) }}</code></p>

          <div v-if="!staged.length" class="empty">没有记录</div>
          <div class="rows">
            <div v-for="(s, i) in staged.slice(0, limit)" :key="i" class="row-card card" :class="s.state">
              <div class="row">
                <code class="key grow ellipsis">{{ keyLabel(keyOf(s.row, pk)) }}</code>
                <span v-if="s.state === 'created'" class="badge ok">将新建</span>
                <span v-else-if="s.state === 'updated'" class="badge warn">已修改</span>
                <span v-else-if="s.state === 'deleted'" class="badge danger">将删除</span>
                <span v-if="conflictFor(s.op)" class="badge danger"><AlertTriangle /> 冲突</span>
                <button v-if="s.state !== 'clean'" class="btn ghost icon small" type="button" title="撤销" @click="unstage(s.op)"><Undo2 /></button>
                <button v-if="s.state !== 'deleted'" class="btn ghost icon small" type="button" title="编辑" @click="openEdit(s)"><Pencil /></button>
                <button v-if="s.state !== 'deleted'" class="btn ghost icon small danger" type="button" title="删除" @click="stageDelete(s)"><Trash2 /></button>
              </div>
              <dl class="fields">
                <template v-for="f in SUMMARY_FIELDS[table] ?? []" :key="f">
                  <template v-if="f in s.row">
                    <dt>{{ f }}</dt><dd>{{ preview(s.row[f]) }}</dd>
                  </template>
                </template>
              </dl>
            </div>
          </div>
          <button v-if="staged.length > limit" class="btn" type="button" @click="limit += 100">显示更多（剩余 {{ staged.length - limit }}）</button>
        </template>
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
              <span class="grow ellipsis">{{ TABLE_LABELS[p.table] ?? p.table }} <code>{{ keyLabel(p.key) || '新记录' }}</code>
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

    <ModalDialog v-if="editing" :title="editing.target ? `编辑 ${TABLE_LABELS[table] ?? table}` : `新建 ${TABLE_LABELS[table] ?? table}`" width="820px" @close="editing = null">
      <div class="stack">
        <p class="hint">编辑完整行 JSON。只有变化的字段会作为修改提交；修改主键会同时改变记录键。<template v-if="table === 'model_configs'"> <code>has_api_key</code> 只读；要设置或清除密钥，请添加 <code>api_key</code> 字段（空字符串表示清除）。</template></p>
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
.data-view .page { flex: 1; }
.tables { gap: 6px; }
.count { opacity: 0.7; font-size: 12px; }
.search { min-width: 180px; }
.chat-pick { width: auto; max-width: 240px; }
.small { font-size: 12px; }
.rows { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 8px; }
.row-card { padding: 8px 10px; display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.row-card.updated { border-color: var(--warn); }
.row-card.created { border-color: var(--ok); }
.row-card.deleted { border-color: var(--danger); opacity: 0.7; }
.row-card.deleted .fields { text-decoration: line-through; }
.key { font-size: 12px; }
.badge svg { width: 12px; height: 12px; }
.fields { display: grid; grid-template-columns: auto 1fr; gap: 2px 10px; margin: 0; font-size: 12px; }
.fields dt { color: var(--text-faint); font-family: var(--font-mono); }
.fields dd { margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tray { flex-shrink: 0; border-top: 1px solid var(--border); background: var(--bg-elev); box-shadow: var(--shadow-pop); max-height: 50dvh; overflow-y: auto; }
.tray-inner { max-width: 1080px; margin: 0 auto; padding: 10px 16px calc(10px + env(safe-area-inset-bottom)); }
.pending summary { cursor: pointer; }
.pending ul { list-style: none; margin: 6px 0 0; padding: 0; display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
.stale { margin-top: 6px; font-size: 13px; }
.ok-line { color: var(--ok); }
.ok-line svg { width: 16px; height: 16px; }
.warn-text { color: var(--warn); }
@media (max-width: 640px) { .rows { grid-template-columns: 1fr; } }
</style>
