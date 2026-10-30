# LoreNook Design

The concepts, rules and reasons behind the code. For *how* something is implemented, read the code; this covers what the code can't easily tell you.

## Concepts

| Concept | Meaning |
| --- | --- |
| Chat | One conversation between a user identity and a character. Owns its rounds, state and memory. |
| Character / User identity | The roleplay character and the user's persona. Each has a name, avatar, description and definitions. |
| Definition | A setting entry (incl. worldbook-style lore) owned by a character or identity. Optionally a Jinja2 template. |
| Scene | One of a character's openings: a First Message plus initial-state overrides. A chat is created from exactly one scene. |
| First Message | The selected scene's opening text, shown as entry 0 and always passed to the preset. |
| Round | One user input plus one user-approved AI output. |
| State | A JSON snapshot at the end of a round: time, place, character attributes, any variables. |
| Round summary | ~150-character factual summary of one round. |
| Episode | Title + ~200–300-character summary of a continuous range of rounds. |
| Writing preset | JavaScript that builds the model request and parses/validates the response. |
| Archiving | The steps that run after the user confirms a round: state → round summary → episode. |

**Chats are fully independent.** Creating a chat copies the selected character (with only the selected scene), identity, definitions, presets and model configs into chat-owned records with new IDs. Editing a library resource never changes an existing chat. Library records have `chat_id = NULL`.

## Round lifecycle

1. User sends input. Enabled definitions are rendered against the latest state, history is assembled, the preset builds a request, the model is called **once**, and the preset parses the response.
2. The result is shown as an unconfirmed **candidate**. It lives only in browser memory — not in the database. The user can edit the AI output (full raw text, tags included) or regenerate (optionally after editing the input). The edited text is what gets saved and archived.
3. On confirm, the round text is saved and archiving runs:

```text
state_update → round_summary → episode_decision → episode_summary → complete
                                      └─ not needed ─────────────────→ complete
```

- Each step's result and the `archive_step` transition commit together. Model calls never hold a DB transaction.
- A failed step records `archive_error` and stops. Retry resumes at that step; earlier results are kept, nothing is duplicated.
- **The next round is blocked until the current archive is complete.**
- After completion, only the latest round's summary, state and the episode it created can be edited from the chat UI. Edits don't trigger recomputation.

Archive modules are built-in Python, not presets. They read only the `<content>` body of the AI output; user input is supplied separately.

### State update

The model gets the old state (as YAML), the current input and AI body, recent round summaries, the character's reference info and update rules, and returns:

```xml
<UpdateVariable>
<Analysis>brief settlement reasoning (not saved)</Analysis>
<JSONPatch>[{"op": "replace", "path": "/世界/时间", "value": "18:05"}]</JSONPatch>
</UpdateVariable>
```

Ops are `add` / `replace` / `remove`. Individually invalid ops are skipped. The patched copy then goes through Schema validation/correction and the world-contract check, and is saved as a complete snapshot.

**If the final state is identical to the previous state, the step fails** (empty patch, all ops skipped, write-back of the same value, Schema correction reverting the change — all count). The model is told not to invent changes to pass.

### Round summary

Input: current input, AI body, the updated state. Output: date—time—location header + ~150 characters of factual third-person narration.

### Episode decision (no model call)

- Candidates are uncovered rounds, chronologically, excluding the latest round.
- Fewer than 5 candidates → no episode.
- Otherwise compare `世界.日期` of the last two candidates. Same date → no episode. Different (forward or backward) → episode covers all candidates up to, not including, the last one.
- Episodes always start at the earliest uncovered round. Invalid dates fail the step.

### Episode summary

Input: the range's round summaries, inputs, AI bodies and states; First Message for the first episode; the previous episode's last round as a bridge (not re-covered). Output: JSON with `title` (≤ 20 chars) and `summary`. Coverage advances only once the episode is saved; retries reuse the saved range.

### Output validation (both summaries)

A structurally valid but useless summary fails with 422 and goes through normal retry:

- **Minimum length**: `min(floor, max(1, ceil(N / 5)))` where N = effective characters of the source dialogue (user input + AI body; plus First Message for episodes). `floor` is 75 for round summaries, 100 for episodes — half of the prompt's target length. "Effective" = `str.isalnum` characters; the leading date—location header doesn't count, but narrative on the same line does.
- **Must start with two ASCII digits** after trimming (i.e. a date), so preambles, code fences and tags are rejected.

These checks apply only to live archive generation, not to imports or manual edits.

## State

State is free-form JSON, but top-level `世界` is required:

```json
{
  "世界": {"日期": "2024-11-14", "星期": "星期四", "时间": "17:53", "地点": "校门外"},
  "江清月": {"年龄": 16, "姿势": "坐在车后座"}
}
```

- `日期` strict `YYYY-MM-DD` and a real date; `星期` is 星期一…星期六 or 星期日; `时间` strict `HH:mm`, 00:00–23:59; `地点` any string. No trimming or guessing; weekday isn't cross-checked against date.
- **These Chinese keys are part of the contract** — episode decisions read `世界.日期`. Don't translate them.
- `characters.state_schema` is Python source exporting a Pydantic model named `Schema`. Its validators check and correct every state. Example: `backend/modules/state/examples/basic.py`.
- **Initial state** = the selected scene's `initial_state` (a partial JSON object, e.g. `{"世界": {"地点": "教室"}}`) run through the Schema, which fills defaults, then the world contract. With an empty Schema the override is the whole state.
- A library character has at least one scene; a chat-owned character has exactly one. Saving scenes or the Schema validates every scene's initial state, so a Schema edit can't silently break another scene. Editing a chat copy's scene doesn't recompute its existing state.
- Generated states and chat-UI edits go through Schema + world contract. Data management writes check only the world contract (no Schema execution).
- Templates read state with `state["世界"]["时间"]`.

## Memory assembly

Writing history uses three representations, oldest to newest: **episodes → round summaries → full rounds**. Each archived round appears in exactly one.

With `T` archived rounds, `X` = chat's `recent_rounds`, `Y` = `min_summaries`:

- The latest `min(T, X)` rounds are always full.
- Everything older starts as round summaries.
- Saved episodes then replace summaries, oldest first, **stopping before an episode would leave fewer than `Y` summaries**. Never skip an episode to use a later one.

Example: T=20, X=5, Y=6, episodes A(1–4) B(5–8) C(9–12) → A, B, summaries 9–15, full 16–20. C would leave only 3 summaries, so it waits.

Episode coverage (for decisions) and episode use (in context) are independent: a saved episode may not be in the prompt yet.

## Definitions

- Ordered entries with `enabled`, `has_template`, `content`. Exactly one of `character_id` / `user_identity_id` is set.
- Templates use Jinja2 (`ImmutableSandboxedEnvironment` + `StrictUndefined`). Any failing template fails the send before the model is called.
- Rendered text is used for that request only; the stored definition is never overwritten.
- `{{user}}` / `{{char}}` (case-insensitive, inner spaces allowed) become the chat's identity and character names before any preset or archive prompt sees them. Applies to all definitions (plain text by literal replacement, templates as variables `user` / `char`), First Message, state reference info and update rules. Character text must use these instead of a hard-coded user name, since one character can be paired with any identity.

## Writing presets

JavaScript executed by QuickJS, fresh context per call, no network/filesystem/DB, synchronous only. Limits: 0.5 s CPU, 32 MiB memory, 512 KiB stack, 2 M chars in/out.

```javascript
function build(materials) { return {api_type: 'google_generate_content', body: {...}}; }
function parse(response)  { return 'full AI output text'; }  // throw Error to fail
```

`materials`: `character_name`, `user_identity_name`, `character_definitions`, `user_definitions`, `first_message`, `history` (`items`, `uses_compressed_history`, …), `user_input`, `state`, `state_yaml`.

- The preset decides roles, message layout, whether to send First Message, and which stored tags to resend. The stored AI output keeps all its tags.
- A custom `<think>` tag is ordinary text, unrelated to a model's native thinking output.
- Example: `backend/modules/presets/examples/google_tool.js` — forces a `game_content(content)` tool call to carry the output, requires `<content>` and a report tag, and includes First Message until compressed history kicks in.

## Model calls

- Supported `api_type`: `google_generate_content`, `deepseek_chat_completions`. The preset's `api_type` must match the config exactly; requests are never converted.
- `base_url` is the API root including version (e.g. `https://generativelanguage.googleapis.com/v1beta`).
- Config `default_parameters` are merged recursively into the request; explicit preset values win (including `false`, `0`, `""`, `null`); arrays replace whole.
- Each chat binds a config to each purpose: `writing`, `state_update`, `round_summary`, `episode_summary`. Purposes may share a config.
- `LORENOOK_LLM_RECORDING_DIRECTORY` (optional) records full requests/responses. Off by default; records contain chat content. The HTTP client ignores `HTTP(S)_PROXY`.

## Illustrations

An optional illustration per archived round: a model call turns the round into an image prompt, a local ComfyUI renders it, the chat shows it. Only locally deployed ComfyUI is supported.

### Image workflows

An image workflow is a library resource (copied into chats like the others) holding a ComfyUI **API-format** workflow, the ComfyUI address, the image size, and **instructions** — the prompt style that workflow needs (language, tag format, what each field means). Different workflows need different prompts; the instructions carry that difference, not the code.

- Any string in the workflow may contain `{{name}}` placeholders. `seed`, `width`, `height` are filled by LoreNook; every other name is a **prompt field** the model must return. A string that is exactly one placeholder takes the raw value (a seed stays an integer); otherwise it's text substitution.
- The model gets the instructions, the field list, character/user definitions (rendered), the round's state, summary, input and AI body, and returns one JSON object with every field as a string. A missing field fails the job before ComfyUI is called.
- The first output image is kept (an `output`-type image preferred over previews).

### Jobs

- Per-chat settings: mode (`off` / `every_round` / `scene_change` / `manual`), the image workflow, and the model config for the prompt. Manual generation needs any mode except `off`.
- `scene_change` triggers when `世界.地点` or `世界.日期` differs from the previous round's state (the initial state for round 1), or when the chat has no illustration yet.
- A job runs after its archive completes, in a single in-process queue (`pending → prompting → rendering → ready | failed`). **It never blocks the next round** and never shows as an archive error. One active job per round. Jobs don't survive a restart; unfinished ones are marked failed at startup.
- Regenerate adds a new attempt; earlier attempts are kept and the newest is shown.
- Files live under `LORENOOK_IMAGE_DIRECTORY` (default `data/images`), one folder per chat, removed with the chat.

### Display

- **Inline plate.** The image is shown at the head of its round, inside the reading page, framed like a book plate, with a caption built from that round's `世界` (date · time · place). Space is reserved at the workflow's aspect ratio, so the page doesn't jump when the image arrives.
- **Full-screen scene view.** Clicking a plate opens it full-screen with the caption and round summary; the chat's illustrations can be browsed in round order.
- **Ambient backdrop** (preference: off / subtle / strong): the latest illustration, blurred and dimmed, behind the chat column. Off on phones by default.
- Per-plate actions: regenerate, hide, view prompt.

## Data management

`/api/admin/data` reads and batch-edits every business table, including history. A batch commits or rolls back as a whole, guarded by a read revision against stale writes. Final consistency is checked (references, continuous round numbers, complete archive results, gap-free non-overlapping episode coverage). No models, Schemas, templates or presets run.

The UI (聊天数据) is scoped by owner: one chat at a time (its history plus its copied resources; definitions belong to their owner's chat), or 资源库原始数据 for rows with `chat_id = NULL`. Pending changes stay global, so one batch can span scopes. 资源库 remains the normal editor for library resources.

Imported episodes may have `created_by_round_id = NULL`; they work normally for memory and coverage.

## Security

There is no built-in login, state Schemas execute arbitrary Python, and the admin API can reveal model API keys. Only expose LoreNook behind external authentication to trusted users.

## Out of scope

Saving candidates across reloads, streaming, multi-user accounts, avatar upload, speech generation, regenerating an already-archived round.
