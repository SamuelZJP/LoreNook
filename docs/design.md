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
| Memory recall | A per-request judgment that expands relevant old memories in place before writing. |
| Writing preset | JavaScript that builds the model request and parses/validates the response. |
| Archiving | The steps that run after the user confirms a round: state → round summary → episode. |
| Image workflow | A ComfyUI workflow with placeholders and the prompt template that fits its model. |
| Cast | The people on a character card who can be drawn, each with an appearance and optional reference image. |
| Main characters | Who an illustration centers on, chosen from the cast and the user identity. |

**Chats are fully independent.** Creating a chat copies the selected character (with only the selected scene), identity, definitions, presets and model configs into chat-owned records with new IDs. Editing a library resource never changes an existing chat. Library records have `chat_id = NULL`.

## Round lifecycle

1. User sends input. Memory recall decides the memory layout if it is on. Enabled definitions are rendered against the latest state, memory is rendered, the preset builds a request, the writing model is called **once**, and the preset parses the response.
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

History uses three representations, oldest to newest: **episodes → round summaries → full rounds**. Each archived round appears in exactly one.

The first two are `<memory>`, the distant and earlier past, assembled by the backend. The full rounds are `recent_rounds`, separate from it. Everything is decided first as plain numbers and only then rendered:

```text
sources (validated records) → layout (episode and round numbers, no text) → render (text)
```

```python
MemoryLayout(memory=[episode [1, 2], summary [9, 10, …, 15]], recent_rounds=[16, 17, 18, 19, 20])
```

With `T` archived rounds, `X` = chat's `recent_rounds`, `Y` = `min_summaries`:

- The latest `min(T, X)` rounds are always full.
- Everything older starts as round summaries.
- Saved episodes then replace summaries, oldest first, **stopping before an episode would leave fewer than `Y` summaries**. Never skip an episode to use a later one.

Example: T=20, X=5, Y=6, episodes A(1–4) B(5–8) C(9–12) → A, B, summaries 9–15, full 16–20. C would leave only 3 summaries, so it waits.

Episode coverage (for decisions) and episode use (in context) are independent: a saved episode may not be in the prompt yet.

## Memory recall

Before writing, a model can expand parts of `<memory>` **in place**, like a clear stretch surfacing from a river of memory. An episode expands into its round summaries; a summary expands into its complete round. Nothing moves, each round still appears exactly once, and `recent_rounds` is never affected.

```python
memory=[episode [1, 2, 3], summary [15, 16, 17]]
memory=[episode [1], summary [4], round [5], summary [6], episode [3], summary [15], round [16], summary [17]]
```

- **Recall basis**: the latest D complete rounds (recall depth, per chat) plus the latest input. A complete round is `<round_1><user_input></user_input><content></content></round_1>`, which is also how an expanded round appears in memory.
- **Two passes**, each judging one kind only. Pass 1 judges episodes and returns the IDs to expand. Pass 2 judges summaries: the original ones plus those just expanded. A pass with no candidates makes no call.
- **Criterion**: memories that may be relevant to the plot's development. Summaries are judged far more strictly than episodes. The prompts alone control how much is recalled; there are no caps.
- **The temporary instruction outranks every rule**: memories it refers to are chosen unconditionally at both passes.
- **Per request.** `POST /recall` returns the layout and the panel updates; `POST /writing` takes the layout. Nothing is saved, and archiving never sees it. Regenerating reuses the layout unless the input or instruction changed. A layout that no longer fits the history is a conflict.
- **Failure** stops before writing and offers retry or writing without recall. IDs the model made up are skipped.
- **Off** when a chat has no recall model, the default.

It is a separate feature: `backend/recall/` and `frontend/src/features/recall/`. The core only accepts an optional layout for a request and a generic step before writing.

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

`materials`: `character_name`, `user_identity_name`, `character_definitions`, `user_definitions`, `first_message`, `memory`, `recent_rounds`, `user_input`, `state`, `state_yaml`.

- `memory` is finished text with no tags, empty when there is nothing older than the recent rounds. It may contain expanded rounds. The preset defines the `<memory>` tags and placement; it never assembles memory itself.
- `recent_rounds` is a list of `{id, round_no, user_input, ai_output}`, so the preset can build whatever structure it wants from them.

- `user_input` ends with a `<instruction>` block when the user adds a temporary instruction. It is plot guidance for that one request: never saved, and absent from history, summaries and state updates.
- The preset decides roles, message layout, whether to send First Message, and which stored tags to resend. The stored AI output keeps all its tags.
- A custom `<think>` tag is ordinary text, unrelated to a model's native thinking output.
- Example: `backend/modules/presets/examples/google_tool.js` — forces a `game_content(content)` tool call to carry the output, requires `<content>` and a report tag, and includes First Message until `memory` is non-empty.

## Model calls

- Supported `api_type`: `google_generate_content`, `deepseek_chat_completions`. The preset's `api_type` must match the config exactly; requests are never converted.
- `base_url` is the API root including version (e.g. `https://generativelanguage.googleapis.com/v1beta`).
- Config `default_parameters` are merged recursively into the request; explicit preset values win (including `false`, `0`, `""`, `null`); arrays replace whole.
- Each chat binds a config to each purpose: `writing`, `state_update`, `round_summary`, `episode_summary`. Purposes may share a config.
- `LORENOOK_LLM_RECORDING_DIRECTORY` (optional) records full requests/responses. Off by default; records contain chat content. The HTTP client ignores `HTTP(S)_PROXY`.

## Illustrations

An optional illustration per archived round: a model call turns the round into an image prompt, a local ComfyUI renders it, the chat shows it. Only locally deployed ComfyUI is supported.

It is a separate feature: `backend/illustrations/` and `frontend/src/features/illustrations/`. The feature depends on the core, never the reverse. The core connects to it only through the list in `backend/features.py` and the generic hooks in `shared/hooks.py` (round archived, chat created, chat deleted). The feature registers its own tables with data management. On the frontend, core views place a few of its components and otherwise know nothing about it. It keeps its own tables and endpoints; chat responses don't include it.

### Image workflows

An image workflow is a library resource (imported into chats as a copy) holding a ComfyUI **API-format** workflow, the ComfyUI address, the image size and a **prompt template**. Models differ in what they want — natural language, tags, a mix, edit instructions — so that difference lives in each workflow's template and placeholders, not in the code.

- **Placeholders** go in any workflow string. `{{seed}}`, `{{width}}`, `{{height}}` are filled by LoreNook. `{{image:focus_N}}` is main character N's reference image. Every other name is a **prompt field** the model must return, so a model needing both tags and a caption just uses two fields. A string that is exactly one placeholder takes the raw value (a seed stays an integer); otherwise it's text substitution.
- **Size**: the workflow's width and height fields reserve the plate's space, so a workflow should take its size from `{{width}}` and `{{height}}` rather than fix its own. The editor warns otherwise.
- **Text-to-image or image-to-image** isn't a setting: a workflow with an image placeholder is image-to-image.
- **The prompt template** is Jinja2 and writes the whole request to the model (variables are listed in the editor). The output format is appended by the code, so a template can't lose it. An empty template selects the default for the workflow's kind. The model returns one JSON object with every field as a string; a missing field fails the attempt before ComfyUI is called.

### Cast and main characters

- A **cast** (画像人物) belongs to a character card: name, appearance, optional reference image. A multi-protagonist card lists each protagonist; the card's own name isn't a person. A user identity has one appearance and optional reference image. Both are copied into chats with their owner.
- **Main characters** decide who the prompt centers on. The default is the first cast member, or the card itself if it has no cast. A chat's manual choice overrides the default, and one attempt can override both when regenerating.
- **More than two is allowed and warned about**: models usually do best with one or two.
- Reference images map to main characters by position. If the workflow needs one that's missing, the attempt fails with that reason before any model call.

### Uploads

Avatars and reference images are uploaded through `/api/media` (PNG, JPEG, WebP; validated by content; up to 16 MB) and stored under `LORENOOK_MEDIA_DIRECTORY` (default `data/media`). Files are named by content hash, so copies in chats share one file; files nothing points at are left in place. Avatars may still be plain URLs. This is core, since avatars don't depend on illustrations.

### Jobs

- Per-chat settings: mode (`off` / `every_round` / `scene_change` / `manual`), image workflow, the model config for the prompt, main characters. Manual generation needs any mode except `off`.
- `scene_change` triggers when `世界.地点` or `世界.日期` differs from the previous round's state (the initial state for round 1), or when the chat has no illustration yet.
- A job runs after its archive completes, in a single in-process queue (`pending → prompting → rendering → ready | failed`). **It never blocks the next round** and never shows as an archive error. One active job per round. Jobs don't survive a restart; unfinished ones are marked failed at startup.
- **Live progress.** While rendering, the backend reads ComfyUI's WebSocket (current node, sampler steps) and streams each running job's state to the open chat as server-sent events. Progress is in memory only and purely informative: the outcome always comes from ComfyUI's history, so without a socket a job still finishes, just without the bar. The stream is open only while a job runs, and a slow list refetch covers a stream that can't get through.
- Regenerate adds a new attempt; earlier attempts are kept and the newest is shown.
- Generated files live under `LORENOOK_IMAGE_DIRECTORY` (default `data/images`), one folder per chat, removed with the chat.

### Display

- **Inline plate.** The image is shown at the head of its round, inside the reading page, framed like a book plate, with a caption from the round summary's date—time—place header. Space is reserved at the workflow's aspect ratio, so the page doesn't jump when the image arrives; a portrait image narrows the plate rather than being cropped.
- **Full-screen scene view.** Clicking a plate opens it full-screen with the caption and round summary; the chat's illustrations can be browsed in round order.
- **Ambient backdrop** (preference: off / subtle / strong): the latest illustration, blurred and dimmed, behind the chat column. Always off on phones.
- Per-plate actions: regenerate, change main characters, hide, view prompt.

## Data management

`/api/admin/data` reads and batch-edits every business table, including history. A batch commits or rolls back as a whole, guarded by a read revision against stale writes. Final consistency is checked (references, continuous round numbers, complete archive results, gap-free non-overlapping episode coverage). No models, Schemas, templates or presets run.

The UI (聊天数据) is scoped by owner: one chat at a time (its history plus its copied resources; definitions belong to their owner's chat), or 资源库原始数据 for rows with `chat_id = NULL`. Pending changes stay global, so one batch can span scopes. 资源库 remains the normal editor for library resources.

Imported episodes may have `created_by_round_id = NULL`; they work normally for memory and coverage.

## Security

There is no built-in login, state Schemas execute arbitrary Python, and the admin API can reveal model API keys. Only expose LoreNook behind external authentication to trusted users.

## Out of scope

Saving candidates across reloads, streaming, multi-user accounts, speech generation, regenerating an already-archived round.
