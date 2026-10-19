# LoreNook Characters and Chats

[中文](../zh-CN/backend/02-characters-and-chats.md) | [Backend overview](README.md)

Updated: 2026-10-19

## 1. Responsibilities

Services manage source characters, user identities, and independent chat copies. Chat creation copies resources, remaps relationships, and saves initial state in one transaction.

Implementation paths in module references are relative to `backend/` unless they explicitly begin with `backend/`.

| File | Responsibility |
| --- | --- |
| `modules/characters/service.py` | Characters, First Message, state configuration, definition lists, copying |
| `modules/users/service.py` | Identity management and copying |
| `modules/definitions/storage.py` | Read and replace owner-scoped definition lists |
| `modules/chats/service.py` | Chat lists, details, settings, deletion |
| `modules/state/initial.py` | Initial-state factory protocol and result checks |
| `workflows/create_chat.py` | Creation transaction, copying, relationship remapping |
| `api/catalog.py`, `api/chats.py` | HTTP endpoints |

Services receive a Repository and participate in the caller's transaction without committing. Synchronous HTTP entry points open and close their database transaction and Session in the same thread.

## 2. Sources and copies

Characters, identities, presets, and model configurations with null `chat_id` belong to source libraries. Chat creation accepts only source IDs, not copies owned by another chat.

Copies get new IDs, ownership, and creation timestamps. Original text, ordering, enabled/template flags, First Message, state settings, model parameters, and credentials are preserved. Copying does not render definitions or execute presets.

Each chat receives its own copies. Editing or deleting a source does not affect them, and editing one chat does not affect another. Source endpoints cannot read or change chat-owned resources.

First Message is stored in the chat character's `first_message`. It is entry 0 and creates no `rounds` record. A newly created chat has initial state but no official round.

## 3. Resource endpoints

All paths below have the `/api` prefix.

| Path | Methods | Behavior |
| --- | --- | --- |
| `/characters` | GET, POST | List or create source characters |
| `/characters/{id}` | GET, PATCH, DELETE | Read, edit, or delete a source character |
| `/user-identities` | GET, POST | List or create source identities |
| `/user-identities/{id}` | GET, PATCH, DELETE | Read, edit, or delete a source identity |
| `/chats/{id}/character` | GET, PATCH | Read or edit the chat character |
| `/chats/{id}/user-identity` | GET, PATCH | Read or edit the chat identity |

Writable character fields are `name`, `avatar`, `description`, `first_message`, `state_schema`, `state_reference`, `state_update_rules`, and `definitions`. Identity fields are `name`, `avatar`, `description`, and `definitions`. Character creation requires a nonblank name and a `state_schema` that generates compliant initial state; identity creation requires only a nonblank name. Other text defaults to empty strings, avatar to null, and definitions to an empty list.

Each definition input has `order`, `enabled`, `has_template`, and `content`; clients cannot set its ID or owner. Reads return IDs and ownership in order/ID sequence.

PATCH changes only supplied fields. Omitting `definitions` preserves them; supplying a list replaces them with new IDs, and an empty list clears them. Use [definition endpoints](03-definition-rendering.md) for ID-preserving entry edits or sorting. `avatar: null` clears the avatar. Non-nullable fields reject null; unknown fields, negative order, and wrong types return 422.

Creating a character or changing its `state_schema` executes default generation and checks universal world fields; failure returns 422 and rolls back the change. Other profile edits do not revalidate legacy Schemas. Editing First Message or state configuration does not regenerate existing states, summaries, or episodes. The state module owns Schema execution and state-edit validation.

## 4. Chat creation

`POST /api/chats` accepts:

| Field | Meaning |
| --- | --- |
| `title` | Required nonblank title |
| `character_id`, `user_identity_id` | Required source IDs |
| `writing_preset_ids` | Source presets to copy; defaults to an empty list |
| `writing_preset_id` | Optional selected source preset, automatically included in copying |
| `model_config_ids` | Source configurations to copy; defaults to an empty list |
| `model_bindings` | Purpose-to-source-configuration mapping; referenced configurations are automatically included |
| `recent_rounds`, `min_summaries` | Nonnegative X/Y; defaults 5/6 |

Purposes are `writing`, `state_update`, `round_summary`, and `episode_summary`. Duplicate source references copy once. Purposes sharing one source configuration bind to the same chat copy.

Creation proceeds in one write transaction:

1. Create the chat.
2. Copy its source character, identity, and all their definitions.
3. Copy presets, remap IDs, and set the selection.
4. Copy configurations, remap IDs, and create bindings.
5. Generate initial state from the copied Schema and save a snapshot with null `round_id`.
6. Commit and return chat details.

Missing or out-of-scope sources, initialization failure, and persistence failure roll back everything. It is valid to create a chat before selecting a preset or binding models. [Preset](05-writing-presets.md) and [model](06-model-calls.md) endpoints can configure them later; writing and archive workflows check their own prerequisites.

### Initial-state integration

`InitialStateFactory` is synchronous pure computation: Schema source in, default-filled and validated/corrected JSON object out. Inject it through `create_app(..., initial_state_factory=...)` or directly into the creation workflow.

The default executes Python/Pydantic source exporting `Schema`; blank source fails because it cannot generate required world fields. Invalid source, defaults, or validation returns 422 and rolls back creation. Nonblank source is not a JSON default value, and chat creation does not accept a replacement initial-state object. See [state updates](08-state-updates.md).

Before storage, results must be top-level objects containing finite JSON values without NaN or infinity, and are detached from the factory's mutable objects. Factories should avoid model calls, network, and file I/O to keep the transaction short.

## 5. Chat reads and configuration

| Path | Method | Behavior |
| --- | --- | --- |
| `/chats` | GET | Basic chat records by descending creation time |
| `/chats` | POST | Create independent copies; return 201 |
| `/chats/{id}` | GET | Chat, character, identity, definitions, presets, configurations, bindings, latest state |
| `/chats/{id}` | PATCH | Title, X/Y, preset selection, or model bindings |
| `/chats/{id}` | DELETE | Cascade-delete chat and copies; return 204 |

PATCH requires IDs owned by this chat. `writing_preset_id: null` clears selection. Supplied `model_bindings` replaces the complete mapping; `{}` clears it. Unreferenced chat configurations remain stored.

Details expose `has_api_key`, not `api_key`; copied credentials remain available internally for invocation. Latest state follows round number, falling back to initial state.

Deleting a chat does not affect source libraries or other chats. Deleting a source character/identity deletes its source definitions without changing copies.

## 6. Errors and validation

- 404: missing record or an ID outside the requested source/chat scope.
- 409: existing chat lacks required resources/state, or database relationship/uniqueness conflict.
- 422: invalid request fields or state initialization failure.

Constraint errors omit SQL parameters to avoid exposing credentials. Unexpected exceptions remain server errors and roll back writes.

Tests cover CRUD, PATCH omission/null behavior, strict request types, HTTP mappings, source/copy scope, complete copying and deduplication, chat isolation, independence after source deletion, rollback during creation, initialization injection, and same-chat configuration checks.
