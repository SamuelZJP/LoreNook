# LoreNook Episode Decisions

[中文](../zh-CN/backend/10-episode-decisions.md) | [Backend overview](README.md)

Updated: 2026-10-19

## 1. Responsibilities and implementation

After saving a round summary, decide whether an episode is needed and select a continuous range. No model call, story/summary analysis, or episode generation occurs here.

Paths below are relative to `backend/`.

| File | Responsibility |
| --- | --- |
| `schemas/episode_decision.py` | Candidate/date inputs, ranges, results |
| `modules/episode_decision/service.py` | Scope, step checks, input collection |
| `modules/episode_decision/dispatcher.py` | Method selection, candidate validation, range construction |
| `modules/episode_decision/methods/day_boundary.py` | First day-boundary and count rule |
| `workflows/episode_decision.py` | Read/compute/save/advance in one short transaction |
| `api/episode_decision.py` | HTTP endpoint |

Existing rounds, episodes, and states are reused without migrations/dependencies. Decisions are independent of presets, model bindings, X/Y, and whether writing memory has selected an episode.

## 2. Candidate and date queries

Only the latest chat round at `episode_decision` may be processed. Candidates are all rounds outside saved episode coverage, including the current round, in round order. Earlier candidates must be archived.

Covered rounds are entirely excluded from candidates and extra state context. Coverage follows actual saved ranges rather than writing selection. A saved decision without an episode does not advance coverage.

| Repository query | Result |
| --- | --- |
| `round_header(chat_id, round_id)` | Scoped ID/number/step |
| `latest_round_header(chat_id)` | Latest metadata |
| `unrepresented_round_headers(chat_id)` | Uncovered metadata in order |
| `round_dates(chat_id, round_ids)` | Exact state projection of `世界.日期`, without fallback |

Method input contains only the current ID, candidate IDs/numbers, and dates from the latest two candidates. A sole current candidate needs no date query. Preserve date value types; missing snapshots, fields, and invalid values are not guessed into dates.

## 3. First-version rule

The built-in `day_boundary` method:

1. Temporarily exclude the latest round.
2. If fewer than five candidates remain, return no episode without requiring valid dates.
3. At the threshold, require valid calendar date strings in strict `YYYY-MM-DD` format for `世界.日期`, parsed into date values in the latest and preceding candidate states.
4. Equal values mean no episode.
5. Different values select all candidates before the latest, ending at its predecessor. Leave the latest for future decisions.

Use the shared strict calendar parser and compare date values. Weekday suffixes, whitespace, and other formats are rejected. Any date change triggers, including a backward change. Weekday, time, and location do not participate. Missing, mistyped, malformed, or impossible dates at the threshold fail; legacy formats require manual correction.

Candidates 13–20 select 13–19 when the rule triggers, leaving 20. Candidates 13–17 have only four earlier rounds and never trigger, regardless of date changes.

## 4. Methods and ranges

`dispatcher.DEFAULT_METHOD` selects code from `METHODS`, a registry of synchronous functions. Internal calls may supply `method`; HTTP requests cannot override method or range.

Each method receives a detached `EpisodeDecisionContext` copy and returns an ending round ID or `None`. The dispatcher:

- Sorts candidates and checks unique IDs, consecutive numbers, and inclusion of the current latest round.
- Starts a required range at the earliest candidate and requires its end among candidates before the current round, with inclusive continuous coverage.
- Rejects unknown methods and invalid endpoints without a fallback.

For candidates 13–20, returning 17 selects 13–17. A method cannot select the current round or an outside ID. Calculation does not mutate callers or receive repositories, dialogue, or historical text.

## 5. Saving and retry

Read inputs, compute, and call `ArchiveRepository.save_decision` in one `BEGIN IMMEDIATE` transaction. With no external work, no cross-transaction generation comparison is needed.

- No episode: save `episode_required=false`, null endpoints, clear error, advance to `complete`.
- Episode needed: save `true` and endpoints, clear error, advance to `episode_summary`.
- Method/required-date error: record the error, stay at `episode_decision`, commit, then return the error.
- Missing records, scope/step mismatch, or candidate conflict: return the relevant error without changes.

Persistence rechecks that coverage starts at the earliest uncovered round, contains continuous archived rounds, and ends before the current round. Commit failure rolls back everything. Duplicates and later concurrent requests fail step checks without overwriting the range.

No episode record is created. Retry of episode summarization uses the saved range without rerunning this decision. Coverage advances only after saving the episode.

## 6. HTTP contract

`POST /api/chats/{chat_id}/rounds/{round_id}/episode-decision` uses stored inputs and needs no body.

| Response field | Meaning |
| --- | --- |
| `chat_id`, `round_id` | Chat and round producing the decision |
| `episode_required` | Whether an episode is needed |
| `start_round_id`, `end_round_id` | Endpoints; null when not needed |
| `start_round_no`, `end_round_no` | Numbers; null when not needed |
| `archive_step` | `complete` or `episode_summary` |

- 404: missing records or wrong ownership.
- 409: not latest, wrong step, noncontinuous/duplicate/incomplete candidate structure, or unfinished earlier candidates.
- 422: unknown method, invalid endpoint, or missing/invalid required dates at the threshold.

## 7. Validation

Coverage includes the five-round threshold, same/different dates, strict calendar parsing and comparison, missing/wrong dates, low-count behavior, sorting and isolation, method switches and bad endpoints, exclusion of covered history, next-range start, persistence and retry, unchanged coverage before episode saving, scopes, rollback, and only one concurrent success.

Projection tests verify that text/summaries are not loaded and covered states are not queried. Integration verifies no additional model call after round summary: a negative decision completes archiving, while a positive one waits for episode summarization.
