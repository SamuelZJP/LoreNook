# LoreNook Backend Overview

[中文](../zh-CN/backend/README.md) | [Documentation](../README.md)

Updated: 2026-10-19

The backend manages chats, writing generation, memory assembly, and sequential archiving. See [product design](../design/product-design.md) for behavior and [data model](../design/data-model.md) for logical fields and ownership.

## 1. Technology

| Component | Choice | Purpose |
| --- | --- | --- |
| Language | Python | Text processing, model calls, and workflows |
| API | FastAPI + Pydantic 2 | HTTP endpoints, validation, and API documentation |
| Database | SQLite | Lightweight persistence for personal use |
| Data access | SQLAlchemy 2 + Alembic | Models, transactions, and versioned migrations |
| Model invocation | HTTPX + API-specific adapters | Send complete requests and preserve response structure |
| Validation | pytest | Module, persistence, and workflow checks |

### Definition templates

Jinja2 resolves variables, conditions, and loops in definitions. Every send supplies a full JSON state copy, accessed as needed, for example `state["世界"]["时间"]`. `ImmutableSandboxedEnvironment` and `StrictUndefined` reject missing variables and rendering failures. Plain definitions bypass Jinja2. Rendered text is never stored over the original.

### Writing presets

JavaScript source is stored in `writing_presets.source` and executed by QuickJS through `quickjs-ng`.

| Entry point | Input | Output |
| --- | --- | --- |
| `build(materials)` | Resolved definitions, history, First Message, current input, and state | `{api_type, body}` |
| `parse(response)` | Complete API JSON response | Validated full AI output string |

Each invocation uses an independent runtime, JSON data exchange, and CPU/memory limits. The runtime exposes no network, filesystem, or database interfaces. A preset handles transformations; the LLM layer performs the model call. See [writing presets](05-writing-presets.md).

Definition rendering and preset construction are independent stages. The current HTTPX implementation supports `google_generate_content`, configuration management, purpose bindings, recursive default merging, and one call per invocation. See [model calls](06-model-calls.md).

### State and transactions

State Schemas are character-owned Python/Pydantic source. Defaults generate initial state; validators check and correct results. State updates apply model-generated JSON Patch and save complete snapshots. See [state updates](08-state-updates.md).

Use short database transactions: chat creation and copying commit together; each archive result commits with its step transition. Model calls hold no database transaction.

## 2. Layers and directories

See [project layout](../architecture/project-layout.md) for the maintained directory guide.

| Layer | Responsibility |
| --- | --- |
| `api` | Receive and validate requests, invoke services or workflows, return responses |
| `schemas` | API and intermodule contracts |
| `workflows` | Coordinate modules, step order, persistence, and recovery |
| `modules` | Business rules: management, rendering, selection, and generation |
| `repository` | Storage models, reads, and writes |
| `llm` | Model requests, parameter merging, and API-specific handling |
| `shared` | Common errors and content extraction |
| `migrations`, `tests` | Database versions and validation |

```text
API → Service                         # Reads and edits
API → Workflow → Services             # Creation, writing, archiving
Service / Workflow → Repository       # Database operations
Workflow / generation module → LLM    # Model calls
```

## 3. Chat creation

`workflows/create_chat.py` creates the chat, copies selected source characters, identities, definitions, presets, and model configurations, assigns new IDs, and remaps relationships. It generates initial state from Schema defaults and saves preset selection and model bindings, all in one transaction.

First Message travels with the character as entry 0. Every chat then uses independent copies.

## 4. Writing

```text
Read chat materials and latest state
  → Render enabled definitions
  → Assemble episodes, summaries, and recent full rounds
  → Include First Message, current input, and state
  → Build a request with the preset
  → Invoke the model once
  → Parse and validate with the same preset source
  → Return an unconfirmed candidate
```

History selection belongs to memory assembly; message organization and First Message inclusion belong to the preset. The LLM layer checks compatibility, merges parameters, connects, and authenticates. Explicit preset values override defaults.

`POST /api/chats/{id}/writing` handles both generation and regeneration before confirmation. Materials and configuration are read in one snapshot; rendering, preset execution, and network work happen after closing the session. Candidates are not persisted. Confirmation saves the official round. See [writing workflow](07-writing-workflow.md).

## 5. Archiving

```text
Save confirmed text → Update state → Round summary → Episode decision → Episode summary → Complete
                                                        └─ Not needed ────────────────→ Complete
```

| Step | Stored result |
| --- | --- |
| State update | Complete JSON snapshot for the round |
| Round summary | Summary using the round's updated state |
| Episode decision | Whether an episode is needed and its selected endpoints |
| Episode summary | Summary, range, and creating round |

Archive modules consume only the `<content>` body of AI output, with user input supplied separately. The first episode method needs at least five uncovered rounds before the latest, then compares `世界.日期` in the latest two candidate states. A date change selects all earlier candidates. It does not call a model.

Each successful step advances `archive_step` and clears its error atomically. Failure records `archive_error` at the current step. Recovery resumes that step and continues; episode summary retries keep the saved range. Coverage advances only after an episode is saved. [Archiving workflow](12-archiving-workflow.md) coordinates the individual steps, confirmation, and recovery.

The next round is blocked until archiving completes. The chat interface can then edit the latest round's summary, state, and created episode without regeneration. [Data management](13-data-management.md) offers separate full reads and atomic historical edits with final consistency checks; it preserves historical JSON without Schema execution.

## 6. Module reference

| Document | Scope |
| --- | --- |
| [01 — Data access](01-data-access.md) | Models, constraints, queries, transactions, migrations |
| [02 — Characters and chats](02-characters-and-chats.md) | Source libraries, chat copies, creation, configuration |
| [03 — Definition rendering](03-definition-rendering.md) | Entry management, ordering, and state templates |
| [04 — Memory assembly](04-memory-assembly.md) | History representation and X/Y selection |
| [05 — Writing presets](05-writing-presets.md) | JavaScript runtime, construction, parsing, preview |
| [06 — Model calls](06-model-calls.md) | Configuration, defaults, adapters, HTTP errors |
| [07 — Writing workflow](07-writing-workflow.md) | Full generation and regeneration |
| [08 — State updates](08-state-updates.md) | Initial state, Schema, Patch, editing |
| [09 — Round summaries](09-round-summaries.md) | Generation, persistence, editing |
| [10 — Episode decisions](10-episode-decisions.md) | Methods, threshold, dates, ranges |
| [11 — Episode summaries](11-episode-summaries.md) | Range-based generation and episode management |
| [12 — Archiving workflow](12-archiving-workflow.md) | Confirmation, progress, step persistence, recovery |
| [13 — Data management](13-data-management.md) | Full reads and database-wide atomic batches |
