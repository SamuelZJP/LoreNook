# LoreNook Data Access

[中文](../zh-CN/backend/01-data-access.md) | [Backend overview](README.md)

Updated: 2026-10-19

## 1. Responsibilities and implementation

Data access provides storage models, connections, queries, and persistence. Services and workflows decide when to call it and own transactions. Repository methods query, write, and `flush`; they do not `commit`, invoke models, render definitions, or execute state Schemas.

| File | Responsibility |
| --- | --- |
| `backend/config.py` | SQLite URL and connection timeout |
| `backend/repository/models.py` | Physical tables and constraints |
| `backend/repository/database.py` | Connections, read sessions, write transactions |
| `backend/repository/queries.py` | Basic operations and business queries |
| `backend/repository/archive.py` | Atomic archive persistence |
| `backend/migrations/` | Alembic schema versions |

## 2. Storage types

- Ordinary IDs are application-generated UUID strings, stored as `VARCHAR(36)`.
- Text and source code use `TEXT`. Avatars may be null; absent descriptions use empty strings.
- Counts and sequence numbers use `INTEGER`. Boolean columns enforce 0/1 values.
- Timestamps use UTC `DATETIME`; reads restore UTC timezone information. Written timestamps must be timezone-aware.
- State and default parameters use JSON columns that require valid top-level objects and preserve nested types.
- `state_schema` holds Python/Pydantic source; see [state updates](08-state-updates.md).

Assign a modified JSON copy back to the field. In-place nested dictionary edits do not automatically trigger ORM updates.

## 3. Tables and constraints

Business fields follow the [logical data model](../design/data-model.md).

| Table | Physical constraints and indexes |
| --- | --- |
| `chats` | X/Y nonnegative, editable defaults X=5/Y=6; selected preset belongs to the chat |
| `characters` | Non-null `chat_id` unique; multiple source records with null ownership allowed |
| `user_identities` | Same chat ownership uniqueness as characters |
| `definitions` | Exactly one character/identity owner; nonnegative order; owner indexes; ties ordered by ID |
| `writing_presets` | `chat_id` index and unique `id + chat_id` for same-chat composite references |
| `model_configs` | `chat_id` index, unique `id + chat_id`, defaults must be a JSON object |
| `chat_model_bindings` | Composite primary key `chat_id + purpose`; four permitted purposes; same-chat configuration |
| `rounds` | Unique chat-local number starting at 1; partial unique index permits one unfinished archive per chat |
| `state_snapshots` | Additional non-null `chat_id`; composite foreign keys enforce character/round/chat agreement; at most one snapshot per round and one initial snapshot per character |
| `episodes` | Endpoints and creating round belong to the chat; at most one episode per creating round; nonblank summary |

Archive steps are `state_update`, `round_summary`, `episode_decision`, `episode_summary`, and `complete`. Database checks enforce summary progress, valid decision-field combinations, and no error on completed rounds. Undecided means null; no episode means `false` with null endpoints; a required episode means `true` with both endpoints.

Database constraints enforce references, uniqueness, and single-row consistency. Chat creation checks required resources; state services perform normal Schema validation. Archive persistence ensures required state and episode results, ordered continuous ranges, and no overlapping coverage. [Data management](13-data-management.md) independently validates final cross-row rules and does not execute historical Schemas.

## 4. Queries and changes

`Repository` provides:

| Method | Behavior |
| --- | --- |
| `get(model, key)` | Fetch by primary key or raise `NotFoundError`; bindings use a composite key |
| `add(record)`, `delete(record)` | Write/delete and flush; caller commits |
| `list_chats()` | Chats by descending creation time |
| `list_owned(model, chat_id)` | Chat-owned copies, or the source library for null ownership |
| `definitions(...)` | Definitions for a character/identity, optionally enabled only, ordered by order and ID |
| `rounds(chat_id, completed_only=...)` | Rounds in sequence, optionally completed only |
| `latest_round(chat_id)` | Latest round or null |
| `round_header(chat_id, round_id)`, `latest_round_header(chat_id)` | Chat-scoped ID, number, and step without loading text |
| `latest_state(character_id)` | Saved snapshot at the greatest round number, then initial state as fallback |
| `state_for_round(chat_id, round_id)` | Exact same-chat round state; no fallback |
| `states_for_rounds(chat_id, round_ids)` | Batch exact states; no fallback |
| `round_summaries_in_range(chat_id, start_no, end_no)` | Ordered ID/number/summary projection without full text |
| `round_dates(chat_id, round_ids)` | Projection of `世界.日期`; IDs without snapshots omitted |
| `summaries_before(chat_id, round_no, limit)` | Nearest preceding archived summaries, returned in order |
| `episodes(chat_id)` | Episodes sorted by starting round |
| `episode_for_round(chat_id, round_id)` | Episode created by that round, or null |
| `unrepresented_rounds(chat_id)` | Rounds outside all saved episode ranges, in sequence |
| `unrepresented_round_headers(chat_id)` | Same coverage filter returning metadata only |

The latest state is determined by round number, not save time. Editing an old snapshot does not make it current. Saved state from an unfinished archive participates in latest-state reads, while the writing workflow separately blocks the next send.

Read, modify, and commit existing objects in a write transaction; assign JSON fields as a whole. The basic Repository is an internal interface, not the data-management HTTP API.

`AdminRepository` uses a fixed business-table registry and parameterized SQL for full snapshots and batches. Foreign-key checks are deferred within the write transaction and checked before commit; uniqueness, non-null, and single-row checks remain immediate. Alembic and SQLite internal tables are excluded.

## 5. Transactions

All connections enable foreign keys and default to a five-second lock wait. SQLAlchemy explicitly issues `BEGIN` for consistent DDL, query, and save behavior.

The connection strategy follows the [SQLAlchemy SQLite documentation](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html).

`Database.read()` closes its session without committing. `Database.transaction()` issues `BEGIN IMMEDIATE`, takes the write lock before reading, commits on normal exit, and rolls back on exceptions. Database access is synchronous. FastAPI database entry points use synchronous functions; any asynchronous orchestration must run complete short transactions in a worker thread without sharing a Session across threads.

```python
with database.transaction() as session:
    repository = Repository(session)
    chat = repository.add(Chat(title="New chat"))
    repository.add(Character(chat_id=chat.id, name="Character"))
    # Creation must copy remaining resources and save initial state here too.
```

| Operation | Transaction boundary |
| --- | --- |
| Create chat | Chat, copies, definitions, bindings, and initial state together |
| Confirm archive | Save approved text separately, creating a `state_update` round |
| Save archive result | Result and step transition together |
| Record failure | Separate short transaction after failed result work |
| Manual edit | One transaction per edit |

Generation and model calls happen outside transactions. Reopen a write transaction to recheck inputs and the current step before saving. Concurrent writers serialize on SQLite's write lock; constraints provide final protection. Callers handle lock timeouts.

## 6. Archive persistence

`ArchiveRepository` methods run in caller-owned write transactions. Completed or stale step writes raise `ConflictError`.

| Method | Result |
| --- | --- |
| `create_round` | Check preceding completion, allocate next number, save approved text |
| `save_state` | Save full state and advance to round summary |
| `save_summary` | Save nonblank summary and advance to episode decision |
| `save_decision` | No episode: complete; required episode: save endpoints and advance |
| `pending_episode_range` | Check the pending step and load saved-range metadata |
| `save_episode` | Recheck range, create episode, complete the round |
| `save_error` | Recheck step and record its error without advancing |

Ranges must start at the earliest uncovered round, cover continuous completed rounds, and end before the round being archived. The decision module chooses whether and where to end. Episode failures leave the range saved without creating coverage. Successful steps clear errors. Interruptions before commit roll back; later failures preserve previously committed steps.

## 7. Deletion and migrations

Deleting a chat cascades to its character, identity, definitions, presets, model configurations, bindings, rounds, states, and episodes. Source resources remain. Deleting a source character or identity removes its source definitions.

Selected presets and range references use deferred foreign keys so relationships can be rebuilt within a transaction. Switch or clear the selected preset before deleting it. Adjust related ranges and decisions when deleting referenced rounds. Deleting a model configuration cascades to its bindings.

Alembic alone manages the schema. The initial migration defines tables, indexes, and constraints independently of runtime ORM table creation. Startup does not migrate. Commands are in the [project README](../../README.md).

Revision `d49c370021ae` adds `episodes.title TEXT NOT NULL DEFAULT ''`. Legacy episodes receive an empty title; their summaries, dialogue, state, coverage, and timestamps are unchanged. Newly generated titles and summaries save atomically. Data-management snapshots and episode memory items include the title. Back up existing databases before running `alembic upgrade head`.

## 8. Validation

Tests use temporary SQLite files built from migrations. Coverage includes foreign keys and ownership, ordering, JSON types, state uniqueness and latest-state selection, rollback, archive errors and retry, episode boundaries, duplicate submissions, concurrent creation, cascade deletion, migration/model agreement, downgrade rebuilding with data, application lifecycle, and health checks.
