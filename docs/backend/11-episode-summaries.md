# LoreNook Episode Summaries

[中文](../zh-CN/backend/11-episode-summaries.md) | [Backend overview](README.md)

Updated: 2026-10-20

## 1. Responsibilities and implementation

Generate a summary for the continuous range already saved by episode decision. Save the episode and complete the creating round's archive. Retries retain the range without rerunning the decision.

Paths below are relative to `backend/`.

| File | Responsibility |
| --- | --- |
| `schemas/episode_summary.py` | Range materials, results, reads, edits |
| `modules/episode_summary/prompts.py` | Built-in episode prompt and range material structure |
| `modules/episode_summary/generate.py` | Built-in prompts, model request, response extraction |
| `modules/episode_summary/service.py` | Episode listing, reads, edits |
| `workflows/episode_summary.py` | Material collection, generation, rechecks, atomic persistence |
| `api/episode_summary.py` | HTTP endpoints |

Migration `d49c370021ae` adds a non-null `episodes.title` with an empty default for legacy episodes. Existing summaries remain unchanged; no new runtime dependencies.

## 2. Materials

Use the saved continuous range. In round order supply each source summary, user input, `<content>` body, and corresponding end-state, plus names resolving the protagonist and “I.” The latest reference state is the last covered round, not the later deciding round. Do not apply later state retroactively.

The range starts at the earliest uncovered round; source rounds must be complete and have nonblank summaries, valid bodies, and matching-character states. Do not execute Schemas, templates, or writing presets. Preserve source text and exclude reports/outside-body sections.

- Include First Message when coverage starts at round 1; do not repeat it in later episodes. Tagged openings contribute only their body; plain-text openings are used directly.
- The last covered round of the nearest previous saved episode may provide a summary/input/body bridge. It is reference only, never a candidate or additional coverage, and must not duplicate the previous event.
- Exclude other covered rounds, previous episode text, and rounds/states after the selected range. X/Y and writing selection do not affect these materials.

Read actual range rounds and states in batches plus the single bridge. Recheck dialogue, summaries, states, First Message, and bridge content before saving to reject stale generation results.

## 3. Model call and original text

`modules/episode_summary/prompts.py` organizes context, optional bridge, included rounds, task, summary format, and JSON output. Require factual third-person observer narration preserving key events, dialogue, interactions, causality, and results. Distinguish plans from facts; add no evaluation, speculation, previews, or closing conclusion.

Request a title of at most 20 characters, plus a summary starting with `start(yyyy/mm/dd)-end(yyyy/mm/dd)—location` and one paragraph of about 200–300 Chinese characters. Use supported state dates/locations without invention. Exclude the next event's opening and use the bridge only for relevant continuity.

Use the `episode_summary` binding with Google single-candidate `responseMimeType=application/json` or DeepSeek non-streaming `response_format={"type":"json_object"}`. Defaults fill remaining parameters. Require one normally completed text candidate, rejecting tools/refusals/truncation and excluding native reasoning. Complete requests/replies are recorded before parsing.

Output exactly `{"title":"Event title","summary":"Date range—location\nEvent summary"}`. Both fields must be nonblank strings; title length is at most 20 characters. Reject missing/extra/duplicate fields, wrong types, multiple objects, nonfinite numbers, and invalid Unicode. Accept one outer JSON code fence, but do not search mixed explanatory text for an object. Persist field strings separately with their whitespace/newlines intact. Invalid JSON fails at the current step without fallback to plain text or an old summary.

Generated narrative must reach `min(100, max(1, ceil(N / 5)))` effective characters, using the [round summary counting rules](09-round-summaries.md). N sums user input and extracted AI body for the selected range, plus First Message when supplied (body only if tagged). Exclude states, round summaries, bridge material, and all material outside the range; output title and a separate date/location header cannot compensate for a short narrative. The 100-character cap is half the 200-character lower prompt target; the 20% source rule accommodates short input without invented padding. No upper limit or rewriting is imposed. Failure returns 422 through existing error/retry handling, preserving prior results and frozen coverage. Manual edits/imports and historical episodes are not retroactively checked.

After parsing and length validation, the trimmed `summary` field must start with two ASCII digits (`[0-9]{2}`), independently of the title and JSON wrapper. This is a prefix check, not full date validation; preserve the original field text. Failure returns 422 through existing error/retry handling, retaining prior results and frozen coverage. The prompt requires a numeric date opening; historical/imported/manual text is unaffected.

## 4. Saving, failures, and concurrency

Only the latest round at `episode_summary` can run. Its saved decision must require an episode, and no episode may already exist for that creating round.

1. Read detached materials/configuration and close the transaction.
2. Call the model outside the transaction.
3. Reopen a short write transaction and compare range, source dialogue/summaries/states, First Message, bridge content, names, and configuration.
4. If unchanged, create the episode using the saved endpoints, record its creating round, advance to `complete`, and clear error. Persistence rechecks continuous coverage and its starting boundary.

Failure similarly rechecks inputs before recording only the current `archive_error`, retaining the step/range. Failure or rollback creates no episode and does not advance coverage. Retry uses the same range. Covered rounds leave future candidates only after success.

Changed inputs/progress return conflicts; stale results and errors are not written. A later concurrent result cannot replace a saved episode or its successful state. Repeating a completed step conflicts.

## 5. HTTP contract

| Endpoint | Behavior |
| --- | --- |
| `POST /api/chats/{chat_id}/rounds/{round_id}/episode-summary` | No body; generate/save and return `chat_id`, `round_id`, `archive_step=complete`, `episode` |
| `GET /api/chats/{chat_id}/episodes` | List by starting round |
| `GET /api/chats/{chat_id}/episodes/{episode_id}` | Read one |
| `PUT /api/chats/{chat_id}/episodes/{episode_id}` | Accept `{"summary":"Episode summary text","title":"Optional new title"}`; omitting title preserves it, save immediately, return the episode |

Episode fields: `id`, `chat_id`, `start_round_id`, `end_round_id`, `title`, `summary`, `created_by_round_id`, `created_at`. All endpoints enforce chat ownership.

Imported historical episodes have a null `created_by_round_id`; they remain readable and participate in memory and coverage, but are edited through data management. Normal generation always records its creating round.

Editing can change only the title and summary of an episode created by the latest completed round. It cannot change ranges/creator or trigger generation. Saving another round ends that edit scope.

- 404: missing or out-of-scope record.
- 409: wrong step, missing range/source state/configuration, changed input, or noneditable episode.
- 422: invalid input, unsupported API type, or invalid response.
- 502/504: upstream failure/timeout, without secrets or upstream bodies.

## 6. Validation

Tests cover ordering/range isolation, body/report separation, First Message only in the first episode, reference-only previous-end bridges, JSON field validation and preservation, native JSON modes, parse failures and fixed-range retry, changed dialogue/opening/bridge rejection, rollback, title editing and memory selection, and legacy migration preserving original history.

The round-summary → decision → episode-summary chain uses two model calls. Writing remains blocked until episode saving completes. The full coordinator is described in [archiving workflow](12-archiving-workflow.md).
