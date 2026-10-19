# LoreNook Product Design

[中文](../zh-CN/design/product-design.md) | [Documentation](../README.md)

Updated: 2026-10-19

This document defines product goals, user interactions, and business rules. Technical choices and API contracts are described in the [backend documentation](../backend/README.md). The [original outline](../archive/initial-project-outline.zh-CN.md) is preserved as a historical draft; this document supersedes it.

## 1. Goals and scope

LoreNook is a lightweight AI roleplaying tool for personal use, built around chats, memory, and writing presets.

Stories advance one round at a time. The user reviews a generated reply before confirming it; confirmation saves the round and updates memory. The current round must finish archiving before the next round can begin.

The first version covers:

- Generating and regenerating replies, followed by confirmation and archiving.
- State updates, round summaries, episode decisions, and episode summaries.
- Layered memory consisting of episodes, round summaries, and recent full rounds.
- Writing presets for building requests and parsing responses.
- Definition editing, preset editing, data management, and settings pages.

Image and speech generation are future possibilities. The interface and content model should accommodate them, but they are outside the current implementation. Saving and restoring unconfirmed candidates is also outside the first version. A writing preset supports transformations around a single model call.

## 2. Interface

| Page | Responsibility |
| --- | --- |
| Roleplay | Display conversation entries, summaries, episodes, and the latest state; offer generation and archiving controls |
| Definitions | Edit characters, user identities, and their definitions |
| Presets | Edit writing request construction and response parsing |
| Data management | Read and modify the entire business database, including historical records |
| Settings | Summary settings, model configuration, appearance, frontend parsing, and other preferences |

The chat interface displays the latest state and may also display summaries and episodes. Its generation, retry, and editing controls apply to the latest round and its archive results.

Frontend parsing determines how output sections are shown, hidden, collapsed, and rendered. A preset's custom `think` text tag is distinct from a model API's native thinking output.

## 3. Core concepts

| Concept | Meaning |
| --- | --- |
| Chat | An entire conversation between one user identity and one character, associated with rounds, memory, and state |
| Character | A roleplay character with a name, avatar, descriptive metadata, and related configuration |
| User identity | The persona adopted by the user, with a name, avatar, and metadata; separate from a multiuser account system |
| Definition | A setting entry owned by a character or user identity, including worldbook-style information |
| Definition rendering | Resolving dynamic template fragments against the latest state before building a request |
| First Message | A character's separate opening text, shown as conversation entry 0 and supplied to the writing preset |
| Round | One user input and one user-approved AI output |
| Round summary | A summary of what happened in one round |
| State | A JSON snapshot at the end of a round, including time, location, characters, and other variables; also the source of template variables |
| Episode | A summary covering a continuous range of rounds with explicit endpoints |
| Writing preset | Rules that turn structured materials into an API request and extract and validate acceptable AI output from the response |

A completed archive must include a round summary and state. An unconfirmed candidate or incomplete archive may not yet have these results.

Creating a chat copies the selected character, identity, definitions, First Message, state configuration, and other selected resources into independent chat-owned records. Later edits to source resources do not change existing chats. Chats have independent characters, identities, variables, and rounds.

### 3.1 Definition ownership and fields

Character definitions belong to characters; user definitions belong to user identities. Both use the same entry structure. Worldbook-style settings belong to these two groups rather than a third category.

| Business field | Meaning |
| --- | --- |
| Order | Position among entries |
| Enabled | Whether an entry participates in rendering and request construction |
| Has template | Whether content needs template rendering |
| Content | Original text, possibly containing dynamic fragments |

Ownership and storage fields are described in the [data model](data-model.md). Presets receive enabled entries in order, with rendered content for templates and original text for ordinary entries.

### 3.2 Rendering before sending

Templates let a definition vary with state: for example, one description when `A > 10` and another when `A <= 10`.

When the user sends a message:

1. Collect and order enabled character and identity definitions.
2. Render entries marked as templates using the latest state; leave other entries unchanged.
3. Pass all resolved text to the writing preset as structured materials.
4. If any participating template fails, fail the send before request construction or model invocation. The user can correct the template and send again.

Rendered text is used only for the current request and never overwrites the stored definition. Regeneration repeats this process.

Definition rendering and preset request construction are separate stages. Definitions use Jinja2; writing presets use JavaScript executed by QuickJS. The application supplies a complete state copy, and templates access the fields they need. Before the first round, they use the initial state generated from the character's state configuration.

### 3.3 JSON state

State supports nested world and character attributes. Top-level `世界` is a required object with four string fields: valid calendar date `日期` in strict `YYYY-MM-DD`, `星期` in 星期一 through 星期六 or 星期日, 24-hour `时间` in strict `HH:mm`, and unrestricted `地点` (empty allowed). Extra fields are allowed. Dates and times are not trimmed or guessed; weekdays are not checked against dates. Chinese keys form the application contract.

```json
{
  "世界": {
    "日期": "2024-11-14",
    "星期": "星期四",
    "时间": "17:53",
    "地点": "温州第二高级中学/校门外/学院东路街角"
  },
  "江清月": {
    "年龄": 16,
    "服装": {
      "外套": "深藏青校服外套(拉上大半)",
      "上衣": "白色校服衬衫",
      "鞋子": "黑色圆头小牛皮乐福鞋"
    },
    "姿势": "坐在车后座，下巴搁在窗沿望着他"
  }
}
```

Templates access nested fields with bracket notation, such as `state["世界"]["时间"]`. JSON types are preserved: age is a number; dates and times are strings.

Initial values, structure, validation and correction rules, reference information, and update rules belong to the character and are copied into the chat. A Schema defines structure, defaults, validation, and corrections. Defaults generate the initial state. Incremental updates produce complete stored snapshots, as described in section 6.1.

Generated states and manual edits pass JSON and character Schema validation/correction, followed by the universal world contract. Character creation and Schema edits also validate generated defaults. Data management preserves submitted historical JSON, checking world fields and relationships without executing the Schema. Existing states remain readable without migration; the contract applies when a state is saved again.

## 4. Round lifecycle

### 4.1 Generation and confirmation

1. Select or create a chat, choose a writing preset, and configure the required models.
2. Send an input, which appears as a user entry.
3. Collect materials and render enabled definitions against the latest state.
4. Build a request with the preset, invoke the model once, and parse and validate its response.
5. Display a successful reply for review. A failure does not produce a new valid AI entry.
6. Allow regeneration, including after editing the user input.
7. Save the official round only when the user confirms and archives it.

Rendering, model invocation, preset execution, or output validation can fail generation. Passing format validation means a candidate was generated successfully; user approval and persistence happen afterward.

### 4.2 Archiving

Confirmation starts this sequence:

1. Save the approved round text.
2. Update and save its state.
3. Generate and save its round summary using that updated state.
4. Decide whether an episode is needed.
5. If needed, generate and save an episode for the selected range.
6. Mark the archive complete once all required results have been saved.

Saving the round text and completing its archive are separate milestones. The next round remains blocked while any required result is missing. The first episode decision method uses state dates and a round threshold without calling a model or using a fallback. Episode summarization calls a model and can fail.

### 4.3 Failure and recovery

Archiving stops at a failed step. Retry resumes the current incomplete step, then continues forward. It preserves committed text and results, creates no duplicate round, and does not repeat successful steps. Recovery also supports interruptions that did not leave an error record.

An episode summary retry uses the previously saved decision range. Completed archives cannot be regenerated or archived again as a whole.

### 4.4 Editing archived results

The chat interface permits manual edits to the latest completed round's summary, state, and episode created by that round. Changes take effect immediately without recomputing other results. Once another round is saved, the previous one is outside this editing scope.

Data management separately supports full reads and batch creation, updates, and deletion of historical text, states, summaries, episodes, and archive fields. Related changes commit together after final consistency checks; failures roll back the entire batch. A read revision prevents stale submissions. Changes do not automatically run models, Schemas, templates, presets, or downstream recomputation.

## 5. Layered memory and writing context

### 5.1 Three historical representations

Writing materials contain, in chronological order:

1. Episodes: compressed summaries of older ranges.
2. Round summaries: individual summaries of intermediate rounds.
3. Recent full rounds: complete user inputs and AI outputs.

Each archived round uses exactly one representation. Presets determine how these materials appear in the target API request.

### 5.2 Selection rules

Let `T` be the number of archived rounds, `X` the recent full-round count, and `Y` the minimum retained round-summary count. The current input is outside `T`.

- `T <= X`: use only full rounds.
- `X < T <= X + Y`: use the latest `X` rounds in full and summaries for the rest.
- `T > X + Y`: start with summaries outside the latest `X`, then try replacing older ranges with saved episodes, from oldest to newest.
- With no episodes, retain all older rounds as round summaries.
- Stop when the next episode would leave fewer than `Y` round summaries. Never split it or skip it to use a later episode.
- Episodes cannot overlap the recent rounds required in full.

`Y` constrains compression; it does not require inventing summaries when history is short.

For `T = 20`, `X = 5`, `Y = 6`, and episodes A (1–4), B (5–8), C (9–12):

| Representation | Rounds |
| --- | --- |
| Episodes A and B | 1–8 |
| Seven round summaries | 9–15 |
| Five full rounds | 16–20 |

Using C would leave only three summaries, so C is not selected yet. Saving an episode does not immediately put it into writing context. Its original rounds and summaries remain stored.

### 5.3 Materials supplied to presets

- Enabled character and identity definitions, rendered when required.
- First Message.
- Selected episodes and round summaries.
- Recent full rounds.
- Current user input.
- Latest state as JSON.

Materials use stored text after the specifically required rendering. First Message is always supplied; the preset decides whether to send it. The intended example behavior includes it until compressed history is used, then omits it even when summaries later become episodes. This decision uses the selected representation, not the mere existence of saved summaries.

## 6. Built-in archive modules

State updates, round summaries, episode decisions, and episode summaries use built-in module code rather than writing presets. When consuming AI output, archive modules read only the text inside `<content>`. User input is supplied separately.

### 6.1 State updates

The state model advances the previous world state to the end of the current dialogue. It checks each variable and settles elapsed time, location changes, and other updates from current actions, dialogue, and rules. Users need not report the time or specify each new value. Do not settle unfulfilled plans; previous summaries provide context only. This step still runs after prose confirmation, and the next round uses the updated state.

1. Read the latest state, or Schema defaults before the first round.
2. Provide the old state, current user input and AI body, recent round summaries, character reference information, update rules, and identity name to the model. Render the old state as YAML. Recent summaries provide context; changes are based on the current round.
3. Receive `<UpdateVariable>` containing brief settlement conclusions in `<Analysis>` and an operation array in `<JSONPatch>`, supporting `replace`, `add`, and `remove`. Apply only the operations without saving the assessment.
4. Apply them to a state copy, then run Schema validation and correction.
5. Save a complete JSON snapshot for the round.

Skip individually invalid or failed operations and continue. Even if all operations are skipped, an unchanged snapshot can succeed if it passes final validation. Model, whole-response parsing, or final validation failures fail the step without saving a new snapshot.

### 6.2 Round summaries

After the state update succeeds, summarize the current input, AI body, updated state, and required context. Cover key events, interactions, and facts, using state dates, times, and locations to record the scene. Request a date—time—location header and about 150 Chinese characters of factual third-person narration without interpretation or speculation. Save nonblank original text and advance to episode decision.

### 6.3 Episode decisions

Methods are selected in code. The first version implements a day boundary and round threshold. Shared rules are:

- Exclude covered rounds from decision candidates. Episode generation may read only the nearest previous episode's last covered round as a reference bridge, without repeating coverage.
- Order uncovered candidates chronologically.
- Return no episode, or an ending round.
- Always start at the earliest uncovered round.
- Require a continuous, inclusive range ending in the candidate history before the current round.

For candidates 13–20, a method returning 17 selects 13–17 and leaves 18–20.

The first method temporarily excludes the latest round. With fewer than five remaining candidates, it returns no episode. Otherwise, it compares the latest two candidates' state field `世界.日期`. Equal dates mean no episode; different dates select all candidates before the latest, ending at the preceding round. Required dates must parse as valid calendar dates in strict `YYYY-MM-DD`; invalid dates fail the decision. Any date change, forward or backward, triggers; weekday, time, and location are not used. Only round metadata and state dates are used, without story analysis or a model call.

### 6.4 Episode summaries and coverage

Summarize the selected range using round summaries, input, AI bodies, and corresponding states. Include First Message for the first episode and an optional preceding-episode end-round bridge later. Output JSON with a title of at most 20 characters and a date-range/location summary of about 200–300 Chinese characters, persisted as separate fields. Coverage advances only after the episode is successfully saved; failure leaves it unchanged.

Episode coverage and writing-context selection are independent. Once covered by an episode, rounds are excluded from later episode decisions even if the writing request has not adopted that episode yet.

## 7. Writing presets

### 7.1 Responsibilities

A preset transforms materials before and after one writing model call. It constructs the complete target request and extracts and validates the response. Model invocation, database access, archiving, and frontend rendering remain application responsibilities.

### 7.2 Request construction

Presets consume definitions after rendering and history after selection. The current input is supplied separately.

| Capability | Examples |
| --- | --- |
| Fixed content | Prompts, fixed messages, tool declarations, API parameters |
| Variables | Definitions, history, state, current input |
| Conditions and iteration | Conditional First Message, traversal of recent rounds |
| Transformations | Message merging, role changes, filtering tagged sections from stored outputs |

Logical user inputs and AI outputs need not map to identically named API roles. Presets may merge current input with other content or use target-specific roles and structures. They return `{api_type, body}`: a target API identifier and complete request object.

### 7.3 Model configuration

The preset's target API and model configuration are independent. The invocation layer reports incompatibility rather than silently converting requests. Explicit preset parameters take precedence; model defaults fill missing values. Connection, authentication, invocation, errors, and recursive merging are covered in [model calls](../backend/06-model-calls.md).

### 7.4 Parsing and validation

Response transformation determines the text accepted as stored AI output. For example, a preset may require a tool named `xxx` whose `content` argument contains:

```xml
<think>...</think>
<content>...</content>
<other>...</other>
```

The preset extracts the specified argument, checks required tags and closing structure, and returns acceptable text or fails generation. `<content>` supplies the AI body to archiving; other tags are preset-specific. `think` is custom text rather than native model thinking. A tool call used to carry output does not execute a function or cause another model call.

### 7.5 Storage, reuse, and display

Accepted output retains its approved tags and waits for confirmation before storage. On later sends, the preset decides which sections to include. Archiving reads the `<content>` body, while frontend parsing determines display. Neither request filtering nor hiding a section changes stored AI output.

Separate copies for display and context are unnecessary. Retaining complete upstream responses as diagnostic records remains an open design question.

## 8. Module boundaries

| Component | Responsibility | Outside its responsibility |
| --- | --- | --- |
| Chat and archive workflows | Lifecycle, step order, allowed operations, persistence | Preset transformations |
| Memory assembly | History selection using X, Y, and episode ranges | Episode triggers and API message format |
| Definition rendering | Resolve enabled templates against a state copy; fail before sending on errors | Requests, model calls, overwriting definitions |
| Writing presets | Request construction, response extraction and validation | Models, storage, frontend display |
| Model invocation | Parameter merging, API compatibility, connections and requests | Archive decisions |
| Archive modules | State updates, summaries, or decisions | Programmable writing presets |
| Frontend parsing | Display and rendering | Rewriting stored output |

## 9. Further design work

Frontend layout, appearance, parsing controls, and deployment arrangements still need detail. The backend has established Jinja2 definitions, JavaScript/QuickJS presets, Python/Pydantic state Schemas, tag extraction, sequential archiving, and interruption recovery. See the [backend overview](../backend/README.md) for their contracts.
