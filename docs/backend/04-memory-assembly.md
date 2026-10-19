# LoreNook Memory Assembly

[中文](../zh-CN/backend/04-memory-assembly.md) | [Backend overview](README.md)

Updated: 2026-10-19

## 1. Responsibilities and implementation

Select historical representations using the chat's recent full-round count X, minimum round-summary count Y, and saved episode ranges. Every archived round appears exactly once, ordered by round number, preserving stored text.

Paths below are relative to `backend/`.

| File | Responsibility |
| --- | --- |
| `schemas/memory.py` | Archived-round inputs, three representations, result contracts |
| `modules/memory/assembler.py` | Database-independent `assemble_memory` function |
| `modules/memory/service.py` | Repository reads and assembly |
| `api/memory.py` | Read-only preview |

This module performs selection without model calls, persistence, tag extraction, or request construction. The writing workflow separately collects definitions, First Message, current input, and state.

## 2. Inputs and queries

`MemoryService(repository).assemble(chat_id)` runs in the caller's read transaction:

1. Read `recent_rounds` and `min_summaries`.
2. Read completed rounds with `Repository.rounds(chat_id, completed_only=True)`.
3. Read episodes using `Repository.episodes(chat_id)` and map endpoint IDs to round numbers without per-endpoint queries.
4. Build detached Pydantic inputs, invoke selection, and return `ChatMemory`.

Existing tables and queries are reused without migration. Round numbers determine chronology; IDs and creation times do not.

The pure function accepts `ArchivedRound` and `EpisodeMemory` lists and nonnegative integer X/Y values. Booleans, strings, and fractions are rejected. Current user input is outside historical total T.

Preview excludes every round whose `archive_step != complete`, even if it already has a state or summary. Preview availability does not authorize sending; the writing workflow checks archive completion.

## 3. Selection

1. Sort rounds. Keep the latest `min(T, X)` in full; initially represent the rest as round summaries.
2. Sort episodes by starting round and try folding their entire ranges, oldest first.
3. Stop if the next episode touches the full-round region or would leave fewer than Y round summaries. Do not split or skip it.
4. Return episodes, remaining summaries, and full rounds chronologically.

`T <= X` yields full text only. `X < T <= X + Y` yields summaries plus full text. With no episodes, all earlier rounds remain summaries. Y limits compression rather than requiring additional history. X=0 allows no full rounds; Y=0 allows all older summaries to become episodes.

Example: T=20, X=5, Y=6, episodes 1–4, 5–8, 9–12. Use the first two episodes, summaries 9–15, and full rounds 16–20.

Gaps between episode ranges remain summaries at their actual chronological positions. Normal episode archiving still requires the earliest uncovered round as its starting point.

## 4. Response contract

| `ChatMemory` field | Meaning |
| --- | --- |
| `chat_id` | Current chat |
| `recent_rounds`, `min_summaries` | X/Y used |
| `total_rounds` | Archived total T |
| `items` | Chronological discriminated union |
| `uses_compressed_history` | Whether selected history actually uses episodes or summaries |

| `kind` | Item fields |
| --- | --- |
| `episode` | `id`, `start_round_id`, `end_round_id`, `start_round_no`, `end_round_no`, `title`, `summary` |
| `summary` | `id`, `round_no`, `summary` |
| `round` | `id`, `round_no`, `user_input`, `ai_output` |

Items contain only their chosen representation. Full-round items omit summaries; episodes omit underlying text. Empty chats return T=0, empty items, and `uses_compressed_history=false`.

The compression flag reflects the selection, not the mere existence of saved summaries or episodes. Presets can use it to omit First Message; the workflow always supplies that opening separately.

Do not trim, normalize line endings, or filter tags from summaries, inputs, or AI outputs. Whitespace checks only determine summary validity. Returned values are detached from mutable inputs and the ORM session.

## 5. HTTP and errors

`GET /api/chats/{chat_id}/memory` previews stored X/Y settings without temporary overrides. Configuration edits affect the next read.

- 404: chat missing.
- 409: duplicate rounds, episode endpoints outside completed history, reversed or internally incomplete ranges, overlaps, blank episode summaries, or missing summaries needed by the selection.

Validate all episode ranges before folding, even ones not yet selected. Do not silently ignore invalid ranges or replace missing summaries with full text. Failure returns no partial result and changes no archive progress.

## 6. Validation

Coverage includes the design example, T/X/Y boundaries and zero values, absent episodes, exactly Y remaining summaries, a large episode blocking later ones, full-text boundaries, no splitting or duplicate coverage, gaps and ordering, invalid ranges, original tags/text, detached results, chat isolation, exclusion of incomplete archives, configuration edits, and HTTP 404/409.
