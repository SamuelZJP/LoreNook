# LoreNook Data Management

[中文](../zh-CN/backend/13-data-management.md) | [Backend overview](README.md)

Updated: 2026-10-19

## 1. Responsibilities and implementation

Provide full business-data reads and atomic batch creation, updates, and deletion. Historical dialogue, states, summaries, episodes, archive progress, primary keys, ownership, and timestamps are editable, independently of the chat interface's latest-result restriction. Changes take effect immediately without regenerating other results.

Paths below are relative to `backend/`.

| File | Responsibility |
| --- | --- |
| `schemas/admin.py` | Ten-table field contracts, operations, results |
| `repository/admin.py` | Fixed registry, parameterized reads/writes, foreign-key checks |
| `modules/admin/service.py` | Snapshots, revisions, batches |
| `modules/admin/consistency.py` | Final cross-record validation |
| `api/admin.py` | HTTP endpoints |

Existing structure is reused without migrations/dependencies. Alembic and SQLite internal tables are excluded. The API does not execute client SQL.

## 2. Full reads

| Endpoint | Result |
| --- | --- |
| `GET /api/admin/schema` | Table names, primary-key fields, complete-row JSON Schemas |
| `GET /api/admin/data` | `revision` and full `tables` snapshot |
| `GET /api/admin/data?include_secrets=true` | Same snapshot including raw model `api_key` |

Tables: `chats`, `characters`, `user_identities`, `definitions`, `writing_presets`, `model_configs`, `chat_model_bindings`, `rounds`, `state_snapshots`, `episodes`. Rows sort stably by primary key. Reads do not execute Schemas, templates, presets, or models.

Default model records omit `api_key` and expose `has_api_key`. Explicit secret reads include `api_key` without that derived field. Both views use the same revision. On update, omitting `api_key` preserves it; an empty string clears it. `has_api_key` is not writable.

Timestamps use timezone-aware ISO strings and read back as UTC. Preserve source, dialogue, whitespace, newlines, and JSON types.

## 3. Batch contract

`POST /api/admin/data` requires the latest read revision as `expected_revision` and at least one operation:

```json
{
  "expected_revision": "last-read-revision",
  "operations": [
    {
      "action": "update",
      "table": "rounds",
      "key": {"id": "target-round-id"},
      "values": {"summary": "Edited historical summary"}
    }
  ]
}
```

| Action | Fields and behavior |
| --- | --- |
| `create` | `table`, `values`; optionally specify ID/time, otherwise generate defaults |
| `update` | `table`, `key`, `values`; modify supplied fields, including primary keys |
| `delete` | `table`, `key`; delete and apply database cascades |

`key` must contain exactly the complete primary key: usually `{"id":"record-id"}`, or `{"chat_id":"chat-id","purpose":"writing"}` for bindings. After changing a primary key, later operations use the new key.

Success returns 200:

```json
{
  "revision": "committed-revision",
  "changes": [
    {"action": "update", "table": "rounds", "key": {"id": "target-round-id"}}
  ]
}
```

`changes` lists explicit targets in request order, using final keys for created/renamed records. It omits secrets and full rows. Reread the snapshot to observe cascades.

## 4. Transactions and revisions

The entire batch runs in one `BEGIN IMMEDIATE` transaction. First check a content revision of the whole business database. Any change, including archive results or credentials, invalidates an old revision. Revisions are computed from deterministically serialized complete fields without a persistent version column. Identical content does not change the revision.

Execute operations in order. Foreign keys may temporarily dangle within the batch and are checked before commit, allowing relationship/ID rebuilding. Uniqueness, non-null, and single-row checks apply immediately. To swap round numbers, first use an unoccupied positive temporary number.

After operations and cascades, reread final data and validate fields, foreign keys, and business consistency. Missing targets, invalid fields/references, stale revisions, or consistency failures roll back everything. Relationship repairs beyond database cascades must be explicit operations.

Concurrent different edits from the same revision allow only the first committed writer to succeed; the other receives 409 and must reread before deciding what to submit.

## 5. Validation rules

Historical states preserve supplied JSON. Validate finite JSON objects, the [universal world contract](08-state-updates.md), and relationships without executing character Schemas or automatic correction. Check the world contract only for created or updated state rows; reads and untouched legacy states require no migration. Unfinished source drafts and arbitrary AI output text may be stored. Normal chat edits and state generation retain their own Schema/body checks.

Field types are strict: numeric fields reject strings and booleans; non-nullable fields reject null; IDs are nonempty and at most 36 characters; timestamps require timezone information. Reject NaN, Infinity, unencodable text, and unknown tables/fields/actions.

Final data must satisfy:

- Every chat retains a character, identity, and character initial state. Source resources may exist independently.
- Round numbers are continuous from 1; only the latest round may be incomplete.
- `state_update` has no current-round state, summary, or decision; `round_summary` has state only; `episode_decision` has state and summary but no decision.
- `episode_summary` has state, summary, and a required saved range without its episode. `complete` has state, summary, decision, and any required episode.
- Episode endpoints/creator share a chat; ranges are forward, continuous, cover archived rounds, and end before the creating round. Imported historical episodes may have a null `created_by_round_id` and cover through the latest completed round.
- Saved episodes with a creator exactly match that round's decision. In coverage order, every episode begins at the earliest uncovered round without overlaps or skipped history; creating rounds, when present, retain their chronological order.
- Pending ranges likewise start at the earliest uncovered round without advancing coverage.
- Preset selection, model purposes, definition ownership, and state ownership satisfy database references, uniqueness, and field constraints.

For example, shortening an episode requires updating its record and the creating round's decision endpoints together. Deleting a historical round also requires adjusting referencing episodes/decisions and later numbers. Deleting a chat cascades to copies/history while keeping sources.

Editing historical text, states, or summaries does not recompute downstream results or rerun day-boundary decisions. Final validation checks the consistency of stored results, not whether manually edited decisions reproduce today's built-in calculation.

## 6. Errors and validation coverage

- 404: target missing.
- 409: stale revision, database constraint, relationship, or archive consistency failure.
- 422: invalid action, key shape, field type, JSON, or timestamp.

Errors omit submitted values, credentials, and SQL parameters. Failure preserves the original snapshot and revision.

Tests cover full creation across ten tables, forward references, defaults/timestamps, historical originals without Schema execution, ID/ownership rebuilding, coordinated ranges, cascades, historical deletion/renumbering, matching results, sequential episodes and pending ranges, cross-chat references, strict JSON, secret views/edits, stale revisions, concurrent writes, and rollback.
