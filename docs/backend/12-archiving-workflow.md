# LoreNook Archiving Workflow

[中文](../zh-CN/backend/12-archiving-workflow.md) | [Backend overview](README.md)

Updated: 2026-10-19

## 1. Responsibilities and implementation

Confirmation first saves approved dialogue, then runs state update, round summary, episode decision, and any required episode summary. Stop on failure while preserving committed text/results. Retry resumes at the current step.

Paths below are relative to `backend/`.

| File | Responsibility |
| --- | --- |
| `schemas/archive.py` | Confirmation, retry, round reads, progress contracts |
| `workflows/archive.py` | Confirmation, sequencing, recovery |
| `api/archive.py` | Confirmation, retry, round queries |
| `repository/archive.py` | Atomic step result/transition saves |

Reuse the four step workflows and existing tables without migration/dependencies. Model calls hold no database session. Confirmation does not execute a writing preset.

## 2. Confirmation

`POST /api/chats/{chat_id}/archive` accepts three fields from the writing result:

```json
{
  "user_input": "Approved input",
  "ai_output": "<content>Approved AI body</content>",
  "based_on_round_id": null
}
```

`based_on_round_id` is required explicitly: null for round 1, otherwise the latest archived ID captured at generation. Empty user input is allowed. Complete output must contain a unique, closed, nonblank `<content>` body. Preserve input, tags, other sections, and line endings.

1. Validate body tags.
2. In a short write transaction, require the chat and a completed latest round matching `based_on_round_id`.
3. Require character, identity, and initial/previous state. Save the next official round at `state_update`.
4. Commit dialogue, then run remaining steps sequentially.
5. Return 201 and final progress on completion.

The client submits an approved candidate. The server neither stores unconfirmed candidates nor reparses old candidates with a new preset. `based_on_round_id` validates round ordering, not every resource's content version. State update reads its resources and previous state when it executes.

Duplicate confirmation returns 409 because the old predecessor no longer matches, even if the first archive completed. Concurrent confirmations serialize in the write transaction. If the first response was lost, query archive progress before retrying; use recovery for the existing round.

## 3. Steps and transactions

```text
Save text → State update → Round summary → Episode decision → Episode summary → Complete
                                                └─ Not needed ─────────────→ Complete
```

The coordinator calls existing step workflows with the same state validator and summary-window settings. State update and round summary each invoke once. Decision uses no model. A required episode adds one call.

Dialogue and each result commit separately. Later failure does not undo earlier state, summary, or range. Episode summarization keeps the saved range without redeciding or advancing coverage early.

Orchestration continues only from the next step returned by its own successful call. It does not take over progress advanced by another request. Every step checks prerequisites and rechecks inputs when saving. Concurrent requests may both call the current model step, but only one result can be committed; the later request conflicts and does not overwrite or continue subsequent steps.

Incomplete archiving blocks writing and confirmation of another round. Completion enables the next round or manual editing of the latest summary/state/created episode; the entire archive cannot be executed again.

## 4. Failure, recovery, and errors

Validation or transaction failure before saving dialogue creates no round. After saving, model, parse, validation, and decision errors are recorded by the relevant step as `archive_error`.

Prerequisite failures such as missing configuration, changed inputs, or step conflicts do not overwrite archive errors. Once dialogue is saved, known errors return current progress so configuration can be corrected and the archive resumed. Database/process interruptions are recovered by reading persisted progress rather than guessing from client state.

`POST /api/chats/{chat_id}/rounds/{round_id}/archive/retry` accepts:

```json
{"expected_step": "round_summary"}
```

Accept only the four incomplete steps, with no replacement dialogue, state, or range. The target must be the latest incomplete chat round, and its step must exactly match `expected_step`. Retry runs that step and continues forward, returning 200 on success.

Recovery also supports steps without an error record, such as interruption after saving dialogue or between steps. It does not need a manufactured failure flag. There are no automatic model retries or background archive jobs; clients explicitly request recovery.

Recognized business/model errors retain their HTTP status and `detail`, adding an `archive` progress object. Errors before dialogue persistence omit `archive`.

| Status | Meaning |
| --- | --- |
| 404 | Missing/out-of-scope chat or round |
| 409 | Stale candidate, incomplete prior archive, nonlatest target, changed step, missing resources/configuration, concurrency conflict |
| 422 | Invalid input/body/state/configuration/generated content or failed episode decision |
| 502/504 | Upstream failure/timeout |

Existing redaction rules omit credentials and upstream bodies. Official dialogue and generated results retain original text.

## 5. Query contract

| Endpoint | Result |
| --- | --- |
| `GET /api/chats/{chat_id}/archive` | Latest round progress, or null before any official round |
| `GET /api/chats/{chat_id}/rounds` | All official rounds in order, including unfinished ones |
| `GET /api/chats/{chat_id}/rounds/{round_id}` | Progress for a specified historical/current round |

Progress contains:

- `round`: ID, chat, number, input, complete AI output, summary, step, error, episode decision/endpoints, and timestamp.
- `state`: this round's saved state or null, with no initial/previous-state fallback.
- `episode`: the episode created by this round, or null if absent/unneeded; not a different episode covering the round.

Reads enforce ownership but require no currently executable preset, model, or Schema. They make no calls and modify no data.

## 6. Validation

Tests cover candidate confirmation, original text, full flows with/without episodes, failure/recovery at all four steps, repaired bindings/APIs/Schemas, committed-result preservation, fixed ranges, interruptions between steps, rollback, concurrent confirmation/retry, stale and out-of-scope requests, exact-step checks, queries, and blocked writing while incomplete.

An archive uses two model calls without an episode and three with one. Retry does not rerun successful model steps. All network tests use mocked transport.
