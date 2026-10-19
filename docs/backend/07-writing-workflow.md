# LoreNook Writing Workflow

[中文](../zh-CN/backend/07-writing-workflow.md) | [Backend overview](README.md)

Updated: 2026-10-19

## 1. Responsibilities and implementation

For one send or preconfirmation regeneration, read chat materials and configuration, render definitions, build with a preset, invoke a model once, then parse and validate the response into complete unconfirmed AI output.

Paths below are relative to `backend/`.

| File | Responsibility |
| --- | --- |
| `workflows/writing_materials.py` | Shared snapshot/material collection and rendering |
| `workflows/preview_writing.py` | Request preview without a call |
| `workflows/writing.py` | Materials/build/invoke/parse orchestration |
| `schemas/writing.py` | Send and candidate contracts |
| `api/writing.py` | Chat writing endpoint |
| `api/dependencies.py` | Database and client dependencies |

The workflow does not save candidates, maintain a server candidate cache, or perform archive steps. Success means the current preset accepted the reply. [Confirmation and archiving](12-archiving-workflow.md) persist official text. No schema migration is needed.

## 2. HTTP contract

`POST /api/chats/{chat_id}/writing` accepts:

```json
{"user_input": "Current user input"}
```

Input must be a string; whitespace and newlines are preserved. Clients cannot replace definitions, state, history, presets, model configuration, or stored rounds, nor directly submit replacement AI output through this endpoint.

Success returns 200:

| Field | Meaning |
| --- | --- |
| `chat_id` | Chat used |
| `preset_id` | Chat-owned preset used |
| `model_config_id` | Chat-owned `writing` configuration used |
| `state_snapshot_id` | State underlying the materials |
| `based_on_round_id` | Latest completed round at snapshot time; null before round 1 |
| `status` | `awaiting_confirmation` |
| `user_input` | Original input |
| `ai_output` | Complete accepted text, preserving tags, whitespace, and newlines |

No credential, complete upstream response, intermediate request, or persisted candidate ID is returned. Use `writing-preview` to inspect request construction.

## 3. Execution order

1. Open one read transaction; require the chat and completion of its latest archive.
2. Read the selected same-chat preset source.
3. Read detached character/identity resources, First Message, definitions, latest state, and X/Y-selected history.
4. In the same transaction, read the `writing` binding and copy URL, key, model, and defaults.
5. Close the session.
6. Render every enabled definition against this state and construct JSON/YAML materials.
7. Execute `build(materials)`.
8. Check compatibility, merge defaults, and make one HTTP call.
9. Execute `parse(response)` with the same source snapshot.
10. Return the candidate.

History follows [memory assembly](04-memory-assembly.md). Current input is outside history; each round has one representation. The workflow does not reorder history, strip tags, or choose First Message inclusion; those request transformations belong to the preset.

Only the current preset and `writing` model binding must be ready. Archive bindings can be configured later. Writing reads saved state without executing its Schema; state generation and validation belong to [state updates](08-state-updates.md).

## 4. Snapshots and transactions

Resources, definitions, history, state, source, and configuration come from one read transaction. Detached snapshots carry no ORM session. Rendering, JavaScript, and network execution occur after it closes.

An in-flight request keeps its original materials and source even if they are edited. The next request reads new values; a request never builds with old source and parses with new source.

`state_snapshot_id` and `based_on_round_id` describe the candidate's basis rather than a saved candidate or locked archive. Confirmation submits `user_input`, `ai_output`, and `based_on_round_id`. It checks that the latest round matches and is complete before persisting text. This rejects stale or duplicate confirmations; it is not a version check for every resource's content.

Preview shares collection and rendering, while omitting model-binding requirements and invocation.

## 5. Regeneration and failure

Regeneration uses this same endpoint with unchanged or edited input. Each request rereads and renders everything, then invokes once. The client displays/replaces candidates; old candidates are absent from the database and history. Candidate persistence/restoration is outside the first version.

Any saved unfinished step—`state_update`, `round_summary`, `episode_decision`, or `episode_summary`—blocks writing, even after state or summary is saved. This endpoint cannot regenerate or overwrite archived rounds.

A failed stage stops immediately without partial AI output, new rounds, state, summaries, episodes, or changes to existing archive errors. Rendering/build/configuration failures make no call. Network/parse failures may be retried by sending again; invocation does not automatically retry or append calls.

- 404: missing chat or out-of-scope reference.
- 409: unfinished archive, missing selection/binding/resources/state, or inconsistent memory ranges.
- 422: invalid input, template, preset build/parse/result, model API, or configuration.
- 502: upstream HTTP, transport, format, or size failure.
- 504: timeout.

Errors retain definition ID/line, preset stage, or invocation kind/upstream status as appropriate. Credentials and upstream error bodies are omitted.

## 6. Validation

Tests use migrated databases, real Jinja and QuickJS, and HTTPX MockTransport. Coverage includes generation, regeneration after edits, retry, definitions, layered history, input exclusion, state/round markers, all four blocking steps, missing configuration, stage failures, zero table writes, secret-free results, example tool round trips, and closed sessions during rendering/preset/network work.

Edits during execution to source, model/key, state, definitions, and First Message verify that the current request keeps its snapshot and the next request uses updated values. Preview and configuration checks remain covered.
