# LoreNook Round Summaries

[中文](../zh-CN/backend/09-round-summaries.md) | [Backend overview](README.md)

Updated: 2026-10-19

## 1. Responsibilities and implementation

After state update, summarize the approved input, AI body, and updated state into key events, interactions, and facts. Save the summary and advance to episode decision. This individual step does not itself decide or generate an episode; [archive orchestration](12-archiving-workflow.md) continues afterward.

Paths below are relative to `backend/`.

| File | Responsibility |
| --- | --- |
| `modules/round_summary/prompts.py` | Built-in summary prompt and material sections |
| `modules/round_summary/generate.py` | Requests and response validation |
| `modules/round_summary/service.py` | Reads and manual edits to the latest completed round |
| `workflows/round_summary.py` | Snapshots, generation outside transactions, saving, failure/retry |
| `schemas/round_summary.py` | Input, result, read, and edit contracts |
| `api/round_summary.py` | HTTP endpoints |
| `llm/generation.py`, `llm/text.py` | Native request building and visible-text extraction shared with state updates |

Reuse `rounds.summary`, states, and configuration without new tables/migrations/dependencies. Generation does not execute presets/templates or change stored dialogue, states, or episodes. The independent endpoint operates on a saved round at `round_summary`.

## 2. Inputs and prerequisites

Read in one transaction:

- Chat character and identity names.
- Latest round at `archive_step=round_summary`, without an existing summary.
- Approved input and complete AI output.
- Exact current-round state from `Repository.state_for_round(chat_id, round_id)`, with matching character ownership.
- The chat's `round_summary` model binding and configuration.
- Nearest preceding archived summaries in round order.

Use the state already updated and saved for this round. Missing state is a conflict, with no fallback to initial/previous state. State is read without Schema execution. Names identify participants; rendered definitions and First Message are excluded.

The default previous-summary window is 3, configured by `Settings.round_summary_recent_summaries`; nonpositive values omit it. `Repository.summaries_before` excludes this round but includes episode-covered rounds. These summaries support continuity rather than repeated summaries of old events.

AI body is only the inner text of the unique, closed, nonblank `<content>` section. Other sections and reports are excluded without modifying stored output.

## 3. Generation and validation

`modules/round_summary/prompts.py` defines the built-in structure: context, current state, recent summaries, dialogue to summarize, task, and output format. Context explicitly resolves the protagonist, “I,” and user character to the configured name.

Use this round's saved updated-state YAML, previous summaries only for continuity, and current user input plus the `<content>` body. Preserve key dialogue, facts, actions, emotional/state changes, and distinguish plans or guesses from completed events.

Request a date—time—location header followed by about 150 Chinese characters of factual third-person narration. Use supplied scene fields without inventing missing values. Do not add interpretation, evaluation, speculation, previews, or a closing conclusion; no JSON, tags, tools, or fences. Length and header are prompt requirements rather than mechanical rewriting rules. Runtime requires one normally completed nonblank text reply and preserves whitespace/newlines.

Support `google_generate_content` (one candidate, `text/plain`) and `deepseek_chat_completions` (system/user messages, non-streaming text mode). Defaults fill other fields. Reject tools, explicit refusals, and truncation; native reasoning remains only in complete call logs. See [model calls](06-model-calls.md).

## 4. Persistence, errors, and retry

Generation holds no database transaction. Reopen a short write transaction to compare round, step, dialogue, this round's state, names, previous summaries, and configuration. Changed inputs return 409 without storing a stale result, including JSON type changes.

`ArchiveRepository.save_summary` atomically saves nonblank text, clears the error, and advances to `episode_decision`. Save/commit failures roll back both summary and progress.

Body, invocation, or parsing failure records only the current-step error after snapshot/step rechecks in a separate write transaction, then returns the error. State and dialogue remain intact at `round_summary`. A concurrently completed step is not overwritten.

Retry uses the same endpoint and repeats only summarization. It never repeats state update or creates another round. Successful steps cannot be generated again. The next round stays blocked until the remaining archive steps complete.

## 5. HTTP interface

Prefix: `/api/chats/{chat_id}/rounds/{round_id}`.

| Method/suffix | Behavior |
| --- | --- |
| `POST /round-summary` | Generate from stored inputs, save, advance |
| `GET /summary` | Read saved summary, including historical or not-yet-complete rounds |
| `PUT /summary` | Replace the latest completed round's summary |

Generation requires no body and accepts no replacement state or output. Success:

```json
{
  "chat_id": "chat-id",
  "round_id": "round-id",
  "summary": "Original summary text",
  "archive_step": "episode_decision"
}
```

Reads/edits return `chat_id`, `round_id`, and `summary`. Editing accepts `{"summary": "Nonblank text"}`; null, wrong types, and extra fields are rejected. It changes only the summary without model/state/episode recomputation. Editing is blocked during archiving and after the round is no longer latest. Reading before a summary exists returns 409.

- 404: missing chat/round or wrong scope.
- 409: not latest, wrong step, summary already exists without progress, missing resources/current state/binding, stale inputs, or invalid edit scope.
- 422: invalid edit fields, AI body, model configuration, or response.
- 502/504: upstream errors/timeouts; omit key and upstream body.

## 6. Validation

Tests use migrated temporary databases and HTTPX MockTransport. Coverage includes exact current-round state, dates/locations, body isolation, names, parameter merging, original text, thinking filtering, invalid candidates/tools/truncation, failures/retry, summary-only writes, duplicate rejection, scopes, changed inputs/types, concurrent stale errors, rollback, edit bounds, and recent-context windows including episode-covered rounds.

State-update-to-summary tests verify use of the new state without rerunning state update. Shared-extractor state tests remain covered.
