# LoreNook Design

The concepts, rules and reasons behind the code. For *how* something is implemented, read the code; this covers what the code can't easily tell you.

## Concepts

| Concept | Meaning |
| --- | --- |
| Chat | One conversation between a user identity and a character. Owns its rounds, state and memory. |
| Character / User identity | The roleplay character and the user's persona. Each has a name, avatar, an optional 3:4 portrait (the cover on cards and pages), description and definitions. |
| Definition | A setting entry (incl. worldbook-style lore) owned by a character or identity. Optionally a Jinja2 template. |
| Scene | One of a character's openings: a First Message plus initial-state overrides. A chat is created from exactly one scene. |
| First Message | The selected scene's opening text, shown as entry 0 and always passed to the preset. |
| Round | One user input plus one user-approved AI output. |
| State | A JSON snapshot at the end of a round: time, place, character attributes, any variables. |
| State script (状态脚本) | Optional character Python that runs on each generated state with the states before it, and can change or reject it. |
| Round summary | ~150-character factual summary of one round. |
| Episode | Title + ~200–300-character summary of a continuous range of rounds. |
| Memory recall | A per-request judgment that expands relevant old memories in place before writing. |
| Writing preset | JavaScript that builds the model request and parses/validates the response. |
| Archiving | The steps that run after the user confirms a round: state → round summary → episode. |
| Image workflow | A ComfyUI workflow with placeholders for what LoreNook provides. |
| Cast | The people on a character card who can be drawn, each with an appearance and optional reference image. |
| Main characters | Who an illustration centers on, chosen from the cast and the user identity. |
| Status bar | Character-authored HTML at the foot of a reply, drawn from the state that round ended in. |
| Character card file | A character exported as one `.lorenook` file, importable as a new library character. |
| User | A built-in account (administrator or user). There is no sign-up; users are created on the command line. |
| Chat template (聊天配置) | Named starting values for a new chat's parameters: presets, model bindings, memory X/Y and each feature's settings. One may be the default. |

**Chats are fully independent.** Creating a chat copies the selected character (with only the selected scene), identity, definitions, presets and model configs into chat-owned records with new IDs. Editing a library resource never changes an existing chat. Library records have `chat_id = NULL`.

**Users are fully separate.** Every chat, library resource, template and uploaded image belongs to one user, and nobody sees or reaches another user's data, administrators included. Each user brings their own model and ComfyUI addresses.

**Chat templates only prefill the new-chat form.** They never set the character, identity or scene, and creation still goes through the same request. They store library IDs as plain references, so a deleted preset or model is dropped (with a notice) when the template is used. Each optional feature stores its own entry under `features.<name>` and is the only code that reads it; the backend checks only that it is a JSON object.

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

### State script

A character may carry a Python `state_script` defining `process(state, previous, history)`. It runs inside the state update, after the unchanged check, so the check still judges the model alone:

```text
patch → Schema + world → unchanged check → process → Schema + world → save
```

- `state` is the new state, `previous` the state before this round (the initial state for round 1). `history` is the latest N earlier snapshots, oldest first and ending with `previous`, as `{round_no, state}` with the initial state as 0. N is the character's `state_script_history` (0–100, default 0).
- It returns the state to save. Raising fails the step with its message; retry reruns the whole step, model call included.
- It runs only on generated updates: not on initial states, chat-UI edits or data management. Saving a character only checks that it defines `process`.
- Like the Schema it is ordinary unsandboxed Python, copied into chats with the card. Example: `backend/modules/state/examples/script.py`.

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

### State display

The chat's state panel is drawn from the state plus the JSON Schema exported from the chat's `Schema`, so no character needs display code:

- **Scene line** on top from `世界`, the same for every character.
- **One card per other top-level object** (usually a person); other top-level values go in a final 其他 card.
- **Display hints**, optional, in the field's `json_schema_extra={"display": ...}`: `bar` (number, with `max`, default 100), `tags` (list of strings), `group` (object as a collapsible group), `hidden`. Pydantic `title`/`description` become the label and tooltip.
- **Fallback by value type** when there is no hint: number and string as text, boolean as a dot, list of scalars as tags, object as a group, empty values hidden.
- **原始数据** at the bottom keeps the JSON editor; editing happens there.

On wide screens the panel sits on the right; on phones it is a bottom sheet opened from the scene line.

## Visual design

"Ink and paper, by candlelight": a cabin corner lit by a candle. Calm, reading first.

- **Floating islands.** The app shell is a warm wood-toned ground; sidebar, reading area and side panel are rounded cards on it with small gaps, not full-height columns split by rules.
- **One accent, candle amber** (`#A85C14` light, `#E8A04A` dark), used for the send action, the current selection and dialogue marks only. Everything else is ink and paper neutrals. Dark mode (walnut ground, candlelit paper text) is the primary look.
- **Reading column** ~720px, serif body, dialogue marked by a thin left rule instead of a box.
- **Tokens only.** Colors, font sizes, spacing and radii come from `frontend/src/styles/tokens.css`; components don't write raw values. Dark values are defined once.
- **Avatars** use the image, falling back to the first character of the name.

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

- **Recall basis**: the latest D complete rounds (recall depth, per chat) plus the latest input. A complete round is a `日期—时间—地点` header taken from the state the round ended in, then `<用户名>` holding the input and `<plot>` holding the story body, separated by blank lines. An empty location or input is left out. This is also how an expanded round appears in memory, with a blank line before and after it.
- **Two passes**, each judging one kind only. Pass 1 judges episodes and returns the IDs to expand. Pass 2 judges summaries: the original ones plus those just expanded. A pass with no candidates makes no call.
- **Criterion**: memories that may be relevant to the plot's development. Summaries are judged far more strictly than episodes.
- **Hard limits** per pass, default 2 episodes and 5 summaries. Each is stated in that pass's prompt, then enforced by keeping the first IDs the model returned, so the prompt asks for most important first. A limit of 0 skips the pass.
- **The temporary instruction outranks every judging rule**: memories it refers to are chosen unconditionally at both passes and listed first. The hard limits still apply.
- **Per request.** `POST /recall` returns the layout and the panel updates; `POST /writing` takes the layout. Nothing is saved, and archiving never sees it. Regenerating reuses the layout unless the input or instruction changed. A layout that no longer fits the history is a conflict.
- **Failure** stops before writing and offers retry or writing without recall. IDs the model made up are skipped.
- **Off** unless the chat's switch is on and it has a recall model. Off is the default.

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

- `memory` is finished text with no tags, empty when there is nothing older than the recent rounds. An episode with a title shows `【标题】` on the line after its date and location. It may contain expanded rounds. The preset defines the `<memory>` tags and placement; it never assembles memory itself.
- `recent_rounds` is a list of `{id, round_no, user_input, ai_output}`, so the preset can build whatever structure it wants from them.

- `user_input` ends with a `<instruction>` block when the user adds a temporary instruction. It is plot guidance for that one request: never saved, and absent from history, summaries and state updates. The composer clears it after each confirmed round unless the user turns on keep, which holds it for later rounds in the same chat.
- The preset decides roles, message layout, whether to send First Message, and which stored tags to resend. The stored AI output keeps all its tags.
- A custom `<think>` tag is ordinary text, unrelated to a model's native thinking output.
- Example: `backend/modules/presets/examples/google_tool.js` — forces a `game_content(content)` tool call to carry the output, requires `<content>` and a report tag, and includes First Message until `memory` is non-empty.

## Model calls

- Supported `api_type`: `google_generate_content`, `deepseek_chat_completions`. The preset's `api_type` must match the config exactly; requests are never converted.
- `base_url` is the API root including version (e.g. `https://generativelanguage.googleapis.com/v1beta`).
- Config `default_parameters` are merged recursively into the request; explicit preset values win (including `false`, `0`, `""`, `null`); arrays replace whole.
- Config `timeout_seconds` (10–1800, default 300) is how long a call may go without receiving data. Without streaming that caps the wait for the whole response.
- Config `streaming` (default off) receives the response as server-sent events, for gateways that cut off a request with no data for too long. The switch owns DeepSeek's `stream` and Google's `streamGenerateContent?alt=sse`; chunks are joined into the non-streaming response shape, so presets and parsers don't change. The browser still gets one complete response.
- Each chat binds a config to each purpose: `writing`, `state_update`, `round_summary`, `episode_summary`. Purposes may share a config.
- `LORENOOK_LLM_RECORDING_DIRECTORY` (optional) records full requests/responses. Off by default; records contain chat content. The HTTP client ignores `HTTP(S)_PROXY`.

## Illustrations

An optional illustration per archived round: LoreNook sends the round's context and reference images to a local ComfyUI, the workflow turns them into an image, the chat shows it. Only locally deployed ComfyUI is supported.

LoreNook decides when to illustrate and who is central, and states what happened. It doesn't write image prompts: enhancement, image reverse-inference and external model calls belong to ComfyUI nodes.

It is a separate feature: `backend/illustrations/` and `frontend/src/features/illustrations/`. The feature depends on the core, never the reverse. The core connects to it only through the list in `backend/features.py` and the generic hooks in `shared/hooks.py` (round archived, chat created, chat deleted). The feature registers its own tables with data management. On the frontend, core views place a few of its components and otherwise know nothing about it. It keeps its own tables and endpoints; chat responses don't include it.

### Image workflows

An image workflow is a library resource (imported into chats as a copy) holding a ComfyUI **API-format** workflow, the ComfyUI address and the image size.

- **Placeholders** go in any workflow string, and anything else is rejected. A string that is exactly one placeholder takes the raw value (a seed stays an integer); otherwise it's text substitution.
  - `{{prompt}}` (required) is the rendered context below.
  - `{{images}}` (optional) is the uploaded reference images as a JSON array inside a string, `[]` when there are none. A real array would be read by ComfyUI as a node link.
  - `{{seed}}`, `{{width}}`, `{{height}}` are numbers.
- **The prompt** has a fixed format with no instructions, since those live in the workflow: `## 用户输入`, `## 剧情内容`, `## 状态信息`, `## 人物外貌`, `## 中心人物`, then a closing line asking for the prompt text. Character definitions aren't included.
- **人物外貌** lists main characters first, then everyone else. Each entry is `<名字>…</名字>` with `参考图：图 N` if an image was sent, then the appearance. Someone with neither is left out.
- **Size**: the workflow's width and height fields reserve the plate's space, so a workflow should take its size from `{{width}}` and `{{height}}` rather than fix its own. The editor warns otherwise.
- **Prompt enhancement nodes** should take `{{seed}}`: ComfyUI caches a node whose inputs didn't change, so regenerating would reuse the same prompt.

### Cast and main characters

- A **cast** (画像人物) belongs to a character card: name, appearance, optional reference image. A multi-protagonist card lists each protagonist; the card's own name isn't a person. A user identity has one appearance and optional reference image. Both are copied into chats with their owner.
- **Main characters** decide who `## 中心人物` names and whose reference images come first. With no choice and a cast, `## 中心人物` holds a fixed line asking the workflow to pick them from the story; a card without a cast is its own default. A chat's manual choice overrides the default, and one attempt can override both when regenerating.
- **More than two is allowed and warned about**: models usually do best with one or two. A main character with neither appearance nor reference image is also warned about.
- **Reference images**: `{{images}}` carries everyone's, not just the main characters', because the workflow decides who appears. Up to 8 are sent, and people sharing a file share a number. A missing image is not an error, and a workflow without `{{images}}` gets none.

### Uploads

Avatars and reference images are uploaded through `/api/media` (PNG, JPEG, WebP; validated by content; up to 16 MB) and stored under `LORENOOK_MEDIA_DIRECTORY` (default `data/media`). Files are named by content hash, so copies in chats share one file; files nothing points at are left in place. Avatars may still be plain URLs. This is core, since avatars don't depend on illustrations.

### Jobs

- Per-chat settings: mode (`off` / `every_round` / `scene_change` / `manual`), image workflow, main characters. Manual generation needs any mode except `off`.
- `scene_change` triggers when `世界.地点` or `世界.日期` differs from the previous round's state (the initial state for round 1), or when the chat has no illustration yet.
- A job runs after its archive completes, in a single in-process queue (`pending → rendering → ready | failed`). **It never blocks the next round** and never shows as an archive error. One active job per round. Jobs don't survive a restart; unfinished ones are marked failed at startup.
- **Live progress.** While rendering, the backend reads ComfyUI's WebSocket (current node, sampler steps) and streams each running job's state to the open chat as server-sent events. Progress is in memory only and purely informative: the outcome always comes from ComfyUI's history, so without a socket a job still finishes, just without the bar. The stream is open only while a job runs, and a slow list refetch covers a stream that can't get through.
- Regenerate adds a new attempt; earlier attempts are kept and the newest is shown.
- Generated files live under `LORENOOK_IMAGE_DIRECTORY` (default `data/images`), one folder per chat, removed with the chat.

### Display

- **Inline plate.** The image is shown at the head of its round, inside the reading page, framed like a book plate, above the round's scene line. Space is reserved at the workflow's aspect ratio, so the page doesn't jump when the image arrives; a portrait image narrows the plate rather than being cropped.
- **Full-screen scene view.** Clicking a plate opens it full-screen with the caption and round summary; the chat's illustrations can be browsed in round order.
- **Ambient backdrop** (preference: off / subtle / strong, default off): the latest illustration, blurred and dimmed, behind the chat column. Always off on phones.
- Per-plate actions: regenerate, change main characters, hide, view prompt. On touch screens they fold into one toggle so they don't cover the image.

## Reading a round

A reply's reading page is, top to bottom: the illustration (if any), the **scene line**, the body, the status bar (if any), then the round's buttons.

- **Scene line**: `日期 · 时间 · 地点` from `世界` of the state the round ended in, sent as the round's `scene`. Never parsed from the summary, so it doesn't depend on how the model wrote the header. Absent until the state update has run.
- **Height cap** (browser preference, % of the chat area, default 100, can be off): past it, only the body scrolls, so the illustration and status bar stay in view. The body keeps a few lines at least, so a tall illustration can push a reply past the cap.

## Status bar

A character may carry status bar code: one HTML document, copied into chats with the card and editable there. It renders in a frame sandboxed without same-origin, and its CSP blocks requests and form posts, so the code can draw but can't reach LoreNook. It may load scripts (e.g. Vue from a CDN).

- `lorenook.onData(cb)` delivers `{state, round_no, character, identity, theme}`, where `state` is the full state that round ended in. The app's theme variables are set on the frame's root.
- **Public theme variables** are a contract with authors and keep their names: `--page-bg`, `--page-text`, `--page-muted`, `--page-em`, `--page-border`, `--page-rule`, `--text`, `--text-muted`, `--border`, `--accent`, `--danger`, `--warn`, `--font-reading`, `--reading-size`. Other app tokens may change freely.
- The frame is transparent and inherits the reading font, so a bar reads as part of the page.
- **Which rounds**: the newest round that has a state always shows its bar; earlier rounds open theirs on demand, to keep the number of frames small.
- **Per-chat switch**, on by default, only offered when the chat's character has code.

It is a separate feature: `backend/status_bar/` and `frontend/src/features/status_bar/`.

## Character card files

A `.lorenook` file is a zip holding `card.json` and the images it refers to under `media/`:

```json
{
  "format": "lorenook.character",
  "version": 1,
  "character": {"name": "…", "avatar": "media/<hash>.png", "scenes": [{"name": "默认", "initial_state": {}}], "…": "…"},
  "features": {"illustrations": {"cast": [{"name": "…", "appearance": "…", "reference_image": "media/<hash>.webp"}]},
               "status_bar": {"code": "…"}}
}
```

- **`character` mirrors `CharacterCreate`** without IDs or `order` fields: list order is the order. Uploaded images become package paths; outside avatar URLs stay as they are.
- **`features.<name>` belongs to that feature**, which registers how to export and import it. The core checks only that each is an object. Sections no installed feature reads are skipped, and the import says so.
- **Version.** A wrong `format` or a `version` above the supported one is refused. Bump the version only for changes an older LoreNook can't read.
- **Export** works for a library character (all scenes) and a chat's copy (its one scene). It writes what is saved.
- **Import always creates a new library character**; names may repeat. Every image is checked by content and stored by hash. A missing or invalid image, or invalid feature data, fails the whole import.
- **Code is dropped unless the user keeps it.** `state_schema` and `state_script` are unsandboxed Python, so the import first shows whether the card has them. Kept code runs at import as on any save. Dropping the Schema skips the scene checks, since scenes usually rely on its defaults; creating a chat still checks the scene.
- Limits: 64 MB per file, 256 entries, 16 MB for `card.json` and for each image. Entries outside `card.json` and `media/` are ignored.

## Data management

`/api/admin/data` (administrators only) reads and batch-edits every business table of every user, including history. A batch commits or rolls back as a whole, guarded by a read revision against stale writes. Final consistency is checked (references, continuous round numbers, complete archive results, gap-free non-overlapping episode coverage). No models, Schemas, templates or presets run.

The UI (聊天数据) is scoped by owner: one chat at a time (its history plus its copied resources; definitions belong to their owner's chat), or 资源库原始数据 for rows with `chat_id = NULL`. Pending changes stay global, so one batch can span scopes. 资源库 remains the normal editor for library resources.

Imported episodes may have `created_by_round_id = NULL`; they work normally for memory and coverage.

## Accounts and ownership

- **Sign-in.** A server-side session in an HttpOnly, Secure, SameSite=Lax cookie, valid 30 days and extended while used. Changing a password or disabling a user ends their sessions. Failed sign-ins make that username (and the visitor's public address, when known) wait, longer each time. Writes from another origin are refused.
- **Every route needs sign-in** except the public home data, health, sign-in and sign-out. The check is application-wide, so a new route is protected without opting in.
- **Ownership lives in the storage session.** Owned tables carry `owner_id`; every statement on them is filtered to the current user and new rows take the current user as owner. Other tables are reached through an owned parent: an ID in the path (chat, character, preset…) must belong to the user, and queries under a chat also filter by that chat. Code that touches owned rows without a scope fails rather than seeing everything.
- **Uploaded images** are stored once by content hash; `media_files` records who may read each. A card export packs only images its user may read.
- **Administrators** additionally get data management (all users' rows, raw) and illustrations, whose renders run on the server's own ComfyUI. New rows created in data management belong to the acting administrator.
- **Model addresses.** A user's model request may only reach public addresses: the host is resolved, every address must be public, and the connection is pinned to the checked one. Administrators may use private addresses.

## Security

State Schemas and state scripts execute arbitrary Python on the server, and the admin API can reveal every user's model API keys. Give accounts only to people you trust.

## Out of scope

Saving candidates across reloads, streaming, self-service sign-up, speech generation, regenerating an already-archived round.
