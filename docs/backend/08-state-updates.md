# LoreNook State Updates

[中文](../zh-CN/backend/08-state-updates.md) | [Backend overview](README.md)

Updated: 2026-10-20

## 1. Responsibilities and implementation

Execute character Schemas, generate initial state, read/edit the latest state, and perform state updates for saved rounds. State is stored as a complete JSON object. Updates use model-generated incremental operations rather than writing presets.

Paths below are relative to `backend/`.

| File | Responsibility |
| --- | --- |
| `modules/state/world.py` | Universal world contract and strict date parsing |
| `modules/state/schema.py` | Python/Pydantic execution, defaults, validation/correction, JSON checks |
| `modules/state/initial.py` | Injectable initial-state factory and result checks |
| `modules/state/patch.py` | `add`/`replace`/`remove` execution |
| `modules/state/prompts.py` | System prompt, context template, single-pass placeholder substitution |
| `modules/state/update.py` | Native model request, tagged response parsing, state update |
| `modules/state/service.py` | Latest-state reads, edit scope, persistence |
| `modules/state/examples/basic.py` | Editable Schema example |
| `workflows/state_update.py` | Snapshot read, generation, atomic save/advance, errors and retry |
| `workflows/edit_state.py` | Validate outside transactions, recheck and save |
| `shared/content.py` | Extract the unique `<content>` body |
| `api/state.py`, `schemas/state.py` | HTTP and module contracts |

Existing snapshot, character, and round tables are reused without new migrations or dependencies. The [archive workflow](12-archiving-workflow.md) coordinates this step. The independent update endpoint processes the latest saved `state_update` round and advances it to `round_summary`.

## 2. Schema source

`characters.state_schema` holds ordinary Python source exporting a Pydantic `BaseModel` subclass named `Schema`. It may define nested models, field defaults, `Field(default_factory=...)`, field validators, and model validators. It is executable application Python rather than the writing preset's JavaScript sandbox.

Save the full editable example as `state_schema`, or use a custom structure. Custom fields are flexible, but the universal world fields are required. A simplified example retains its Chinese field name:

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator

class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)
    世界: dict = Field(default_factory=lambda: {"日期": "2026-10-19", "星期": "星期一", "时间": "08:00", "地点": ""})
    好感度: int = 0

    @field_validator("好感度")
    @classmethod
    def clamp(cls, value):
        return max(0, min(100, value))
```

Each execution loads a fresh temporary module with forward-reference support and removes its registration afterward. Mutable model instances are not cached across chats. Pydantic configuration controls coercion, extra fields, and default validation; explicitly configure `extra` and `validate_default` as appropriate. Export results in JSON mode using aliases, require a top-level object with valid finite JSON values and valid Unicode, and detach mutable references.

Blank source skips character Schema execution but still requires a compliant world object. Initializing it from `{}` fails, so the default executor rejects blank Schema when creating characters or chats. Nonblank source is never interpreted as JSON defaults.

Creation uses `python_initial_state`: validate an empty object through Schema defaults and corrections, rolling back creation on failure. `state_reference` and `state_update_rules` remain separate fields rather than constants loaded from source.

Inject factories with `create_app(initial_state_factory=...)` and validators with `create_app(..., state_validator=...)`. The validator protocol is `(source, content) -> JSON object`. Custom implementations should use pure computation without models/network/files. If a custom Schema format is used for both creation and updates, provide matching factory and validator implementations.

The application checks world fields with `modules/state/world.py` after character Schema correction. Top-level `世界` must be an object containing these string fields; additional fields are allowed:

| Field | Constraint |
| --- | --- |
| `世界.日期` | Strict `YYYY-MM-DD`, four-digit year 0001–9999, valid calendar date |
| `世界.星期` | Exactly `星期一`, `星期二`, `星期三`, `星期四`, `星期五`, `星期六`, or `星期日` |
| `世界.时间` | Strict 24-hour `HH:mm`, from `00:00` to `23:59` |
| `世界.地点` | Any string, including empty |

Dates and times require ASCII digits, with no trimming, padding, or format guessing. Weekdays are not checked against dates or corrected automatically. The application does not fill missing fields. Injected factories and validators must also produce compliant final output.

Existing states remain readable without migration. Created or updated administrative state rows must comply, without character Schema execution; untouched legacy snapshots do not block unrelated edits.

## 3. Update inputs

Collect in one read transaction:

- Chat character, identity name, and state settings.
- Latest target round at `state_update`, including approved input and complete AI output.
- Latest saved state, falling back to initial state for round 1. An already saved current-round state at this step is a storage conflict.
- The chat's `state_update` model binding and configuration.
- The nearest preceding archived summaries in chronological order.

`Repository.summaries_before(chat_id, round_no, limit)` excludes the current round but includes rounds covered by episodes. The default window is 3, configured by `Settings.state_recent_summaries`; nonpositive values omit summaries. They provide context, while changes must follow the current dialogue.

Require exactly one closed, nonblank `<content>` section. Only its original inner text is used as AI body. Reports, other tags, and native thinking are excluded without changing full stored output.

## 4. Generation and Patch

The state model advances previous state to the end of the current dialogue, checking every variable and settling elapsed time, location changes, and other updates. It runs after prose confirmation; the next writing round uses the resulting state. Users need not specify every new value or report the time. Without an explicit duration, the model estimates elapsed time from current actions and update rules. Plans, invitations, and wishes are not completed actions; speech and guesses are not automatically objective facts. Do not invent important events or settle old summaries again. Across midnight, the prompt requests consistent date, weekday, and time updates; application validation still checks formats and Schema without automatically correcting weekday agreement.

See [`modules/state/prompts.py`](../../backend/modules/state/prompts.py) for the complete prompt. The system message defines settlement responsibilities. One `user` message contains these sections in order:

1. **Identity emphasis**: map `<user>`, the protagonist, and first-person references to the identity name.
2. **Context**: `state_reference` inside `<Reference_Info>`.
3. **Previous state**: full state YAML.
4. **Recent plot recap**: three preceding summaries by default, for context only.
5. **Current dialogue**: original user input and AI `<content>` body.
6. **Variable rules**: `state_update_rules` inside `<Variable_Update_Rules>`.
7. **World contract**: time advancement, completed actions, and universal world fields.
8. **Output format**: settlement conclusions and tagged JSON Patch.

Substitute template placeholders once, preserving template syntax in inserted materials. Full character/identity definitions, writing presets, episodes, full history, and Schema source are not automatically supplied. Character-specific context belongs in reference information and update rules; existing character rules are not rewritten automatically.

After closing the session, construct a native request for the bound `google_generate_content` or `deepseek_chat_completions` API. Google uses one candidate and `responseMimeType: text/plain`; DeepSeek sends identical system/user text in order, using non-streaming output and `response_format: {"type": "text"}`. Model defaults fill remaining parameters. Require one normally completed candidate (`finishReason=STOP` for Google, `finish_reason=stop` for DeepSeek), rejecting tools, explicit refusals, and truncation. DeepSeek reads only `message.content`; native reasoning remains in full call logs. Visible text follows this structure:

```xml
<UpdateVariable>
<Analysis>Two minutes pass during a brief conversation; location and other variables remain unchanged.</Analysis>
<JSONPatch>
[{"op":"replace","path":"/世界/时间","value":"08:02"}]
</JSONPatch>
</UpdateVariable>
```

`Analysis` contains brief settlement conclusions about elapsed time, whether substantial changes are appropriate, and each variable's outcome, without detailed reasoning or language/word-count requirements. Require nonblank assessment text but do not save or return it. Each tag must occur exactly once, close correctly, and follow the shown order. Only whitespace may surround the structure; reject Markdown fences, extra text, and missing or repeated tags. `JSONPatch` must contain a complete JSON array with finite numbers; use `[]` for no change. Bare arrays from the previous format are no longer accepted. Ignore `thought` text parts, reject tool calls, and never search arbitrary prose for an array.

The prompt treats underscore-prefixed fields as read-only. This is a model instruction; the Patch executor does not enforce prefixes. Use character Schema for hard constraints.

Supported operations are `add`, `replace`, and `remove`. Paths follow [JSON Pointer (RFC 6901)](https://www.rfc-editor.org/rfc/rfc6901); these operations follow [JSON Patch (RFC 6902)](https://www.rfc-editor.org/rfc/rfc6902):

- Object `add` creates or replaces a key; the parent must exist. `replace`/`remove` require an existing target.
- Array `add` inserts, allowing the length position or `-` for append. `replace` overwrites and `remove` deletes.
- Array indexes are ASCII nonnegative integers without leading zeroes. Reject negative/out-of-range indexes and `-` for replacement/deletion.
- Decode `~0` as `~` and `~1` as `/`; reject invalid escapes.
- An empty path can replace/add the root object; it cannot remove it or make it a non-object. `/` addresses an empty-string key.
- `add`/`replace` require `value`. Unrelated extra fields do not affect the operation.

Apply operations sequentially to a copy. Skip an individually malformed, mistyped, or unsuccessful operation and continue; report its count in `skipped_operations`. This module intentionally tolerates individual failures rather than failing the entire batch.

Validate and correct the final full state through Schema, then check the universal world contract. Compare the complete resulting JSON with the previous state, ignoring object key order but preserving value types and array order. An identical final state fails with 422, including empty/all-skipped operations, writes of original values, cancelling operations, and changes reverted by Schema correction. Save no snapshot and retain `state_update` for retry. The prompt explains this failure rule and requires factual updates; it must not invent elapsed time or other changes to pass the check. Whole-response parsing, model, or final validation failures also save no state.

## 5. Saving, retry, and concurrency

Generation and Schema validation happen outside database transactions. Before saving, reopen a write transaction and compare the current step and every input to the captured snapshot. Changes to text, old state, Schema, prompt resources, summaries, or configuration return 409 without saving a stale result. JSON type changes such as integer versus boolean are detected.

When unchanged, `ArchiveRepository.save_state` saves the full state, advances to `round_summary`, and clears the old error in one transaction. Duplicate/stale requests are rejected before model invocation when detectable; concurrent results are checked again on save. Persistence or commit failure rolls back the snapshot and step together.

Model, parsing, body, or validation errors are recorded in a separate short write transaction after rechecking inputs and step, then returned. Changed inputs or progress prevent stale errors from overwriting newer state. The round text remains saved at `state_update`; retry reruns only this step.

## 6. Reads and manual edits

`GET /api/chats/{chat_id}/state` returns latest state with its ID, character, round, and timestamp. Selection uses round number, then initial state. Saved state from an incomplete archive is readable.

`PUT /api/chats/{chat_id}/state` accepts `{"content": {...}}` and replaces the editable snapshot. Before any round, initial state is editable. Otherwise only the latest completed round's state is editable; unfinished archiving blocks manual changes.

After validation/correction, recheck Schema, original state, and round scope, then update the original snapshot while retaining its ID and relationships. Type changes persist, including `1` to `true`. Failure preserves the original; success does not recompute summaries or episodes. The next render/send uses the changed state.

## 7. Update endpoint and errors

`POST /api/chats/{chat_id}/rounds/{round_id}/state-update` reads stored text/settings, with no client replacement state or model response. Success:

```json
{
  "chat_id": "chat-id",
  "round_id": "round-id",
  "archive_step": "round_summary",
  "state": {"id": "state-id", "character_id": "character-id", "round_id": "round-id", "content": {}, "created_at": "2026-10-19T00:00:00Z"},
  "skipped_operations": 0
}
```

- 404: missing chat/round or wrong ownership.
- 409: not latest, wrong step, missing resources/previous state/binding, stale inputs, or invalid edit scope.
- 422: invalid fields, body, Schema, whole Patch response, or model configuration.
- 502/504: upstream failure/timeout using model-layer mappings, without keys or upstream bodies.

## 8. Validation

Additional checks cover context section order, literal template syntax in inserted materials, tagged output, nonfinite numbers, and malformed response rejection. Automated tests do not assess narrative settlement quality with a real model.

Tests cover defaults, forward references, nesting, correction rules, JSON types and module cleanup; object/array/escaped/root paths and skipped operations; creation, reads, editing and scope; body isolation and summary context; atomic step persistence, retry/error clearing, cross-chat rejection, rollback, and stale inputs. Model transport is mocked.
