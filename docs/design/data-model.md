# LoreNook Data Model

[中文](../zh-CN/design/data-model.md) | [Documentation](../README.md)

Updated: 2026-10-19

This document describes the logical model. SQLite types, additional ownership fields, indexes, and physical constraints are specified in [data access](../backend/01-data-access.md). `id` identifies a record; `*_id` fields express relationships.

## 1. Chats: `chats`

| Field | Meaning |
| --- | --- |
| `id` | Chat ID |
| `title` | Chat title |
| `writing_preset_id` | Selected chat-owned writing preset |
| `recent_rounds` | Recent full-round count X |
| `min_summaries` | Minimum retained round-summary count Y |
| `created_at` | Creation time |

## 2. Characters: `characters`

| Field | Meaning |
| --- | --- |
| `id` | Character ID |
| `chat_id` | Owning chat; null for a source-library character |
| `name` | Character name |
| `avatar` | Avatar reference |
| `description` | Descriptive metadata |
| `first_message` | Opening text shown as entry 0 |
| `state_schema` | Source defining state structure, defaults, validation, and corrections |
| `state_reference` | Reference information for state updates |
| `state_update_rules` | State update rules as text |
| `created_at` | Creation time |

Each chat owns an independent character record.

## 3. User identities: `user_identities`

| Field | Meaning |
| --- | --- |
| `id` | Identity ID |
| `chat_id` | Owning chat; null for a source-library identity |
| `name` | Identity name |
| `avatar` | Avatar reference |
| `description` | Descriptive metadata |
| `created_at` | Creation time |

A user identity is a roleplay persona. Each chat owns an independent identity record.

## 4. Definitions: `definitions`

| Field | Meaning |
| --- | --- |
| `id` | Definition ID |
| `character_id` | Owning character; null for identity definitions |
| `user_identity_id` | Owning identity; null for character definitions |
| `order` | Sort position |
| `enabled` | Whether the definition participates |
| `has_template` | Whether the content requires rendering |
| `content` | Original definition text |

Exactly one owner field must be populated. Rendering happens when sending, and the result is used only for that request.

## 5. Writing presets: `writing_presets`

| Field | Meaning |
| --- | --- |
| `id` | Preset ID |
| `chat_id` | Owning chat; null for a source preset |
| `name` | Preset name |
| `source` | Complete source for request construction, target API declaration, and response parsing |
| `created_at` | Creation time |

## 6. Model configuration and purpose bindings

### `model_configs`

| Field | Meaning |
| --- | --- |
| `id` | Configuration ID |
| `chat_id` | Owning chat; null for a source configuration |
| `name` | Configuration name |
| `api_type` | API type |
| `base_url` | API root URL |
| `api_key` | Authentication secret |
| `model` | Model name |
| `default_parameters` | Default request parameters as JSON |

### `chat_model_bindings`

| Field | Meaning |
| --- | --- |
| `chat_id` | Owning chat |
| `purpose` | `writing`, `state_update`, `round_summary`, or `episode_summary` |
| `model_config_id` | Chat-owned model configuration |

`chat_id + purpose` is unique. Several purposes may share a configuration. The first episode decision method does not use a model.

## 7. State snapshots: `state_snapshots`

| Field | Meaning |
| --- | --- |
| `id` | Snapshot ID |
| `character_id` | Owning chat character |
| `round_id` | Associated round; null for the initial state |
| `content` | Complete JSON state |
| `created_at` | Save time |

Chat creation generates an initial snapshot from Schema defaults. Each successful round state update saves its own snapshot. The latest state is the saved state of the greatest round number, falling back to the initial state when no round state exists. The physical table also stores `chat_id` to enforce ownership.

## 8. Rounds: `rounds`

| Field | Meaning |
| --- | --- |
| `id` | Round ID |
| `chat_id` | Owning chat |
| `round_no` | Chat-local round number, beginning at 1 |
| `user_input` | User-approved input |
| `ai_output` | Complete accepted AI output, including tags |
| `summary` | Round summary; null before generation |
| `archive_step` | Current archive step |
| `archive_error` | Current step error; null when absent |
| `episode_required` | Whether an episode is needed; null before a decision |
| `episode_start_round_id` | Selected starting round |
| `episode_end_round_id` | Selected ending round |
| `created_at` | Time the round text was saved |

`chat_id + round_no` is unique. Confirmation creates the record. Archive modules consume only the `<content>` body of `ai_output`.

```text
state_update → round_summary → episode_decision → episode_summary → complete
```

If no episode is needed, the decision advances directly to completion. Each result and step transition are saved together. Failure leaves the current step available for retry; after that retry succeeds, orchestration continues. Episode summary retries use the saved decision range.

## 9. Episodes: `episodes`

| Field | Meaning |
| --- | --- |
| `id` | Episode ID |
| `chat_id` | Owning chat |
| `start_round_id` | First covered round |
| `end_round_id` | Last covered round |
| `title` | Episode title, nonblank and at most 20 characters on generation; empty for legacy episodes |
| `summary` | Episode summary text |
| `created_by_round_id` | Round whose archive created the episode |
| `created_at` | Save time |

If round 6 creates an episode covering 1–5, its endpoints are 1 and 5, and its creating round is 6. `created_by_round_id` determines whether the episode is editable from the latest completed round. Coverage advances only when the episode is saved successfully.

## 10. Creation and modification

Creating a chat copies its selected character, identity, definitions, presets, and model configurations, generates new IDs, and remaps relationships to the copies. First Message and state configuration travel with the character. The copied Schema generates the initial state.

Chats are independent. The chat interface operates on the latest round; after completion it can edit only that round's summary, state, and newly created episode. Data management can modify any business record.

A data management batch can change primary keys, owners, episode ranges, and related records together. It commits or rolls back as a unit. Final records must satisfy references, continuous round numbering, complete archive results, and consistent episode coverage. Historical states retain submitted JSON and check universal world fields on writes, without character Schema execution or automatic recomputation. Untouched legacy states remain readable.
