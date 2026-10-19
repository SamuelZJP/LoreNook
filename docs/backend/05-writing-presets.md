# LoreNook Writing Presets

[中文](../zh-CN/backend/05-writing-presets.md) | [Backend overview](README.md)

Updated: 2026-10-19

## 1. Responsibilities and implementation

A writing preset is JavaScript source stored in `writing_presets.source`. It constructs a target API request from structured materials and extracts and validates complete AI output from a JSON response. Model calls, storage, archiving, and frontend display belong to the application.

Paths below are relative to `backend/`.

| File | Responsibility |
| --- | --- |
| `schemas/presets.py` | Preset management, materials, request, and parsing contracts |
| `modules/presets/service.py` | Source/chat CRUD and ownership checks |
| `modules/presets/runtime.py` | Independent QuickJS contexts, resource limits, result validation |
| `modules/presets/examples/google_tool.js` | Editable Google tool-output example |
| `workflows/writing_materials.py`, `workflows/preview_writing.py` | Shared snapshot/material collection and preview construction outside transactions |
| `api/presets.py` | Management, isolated trials, and chat previews |

Existing tables and copy behavior are reused without migration. Runtime dependencies include `quickjs-ng` and `PyYAML`; validated versions are in the lock file.

Runtime API reference: [QuickJS Python wrapper](https://github.com/genotrance/quickjs-ng).

## 2. Source and materials

Use ordinary JavaScript with two synchronous functions, without `export`, `import`, or CommonJS:

```javascript
function build(materials) {
    return {
        api_type: 'example',
        body: {messages: [{role: 'user', content: materials.user_input}]}
    };
}

function parse(response) {
    if (typeof response.text !== 'string') throw new Error('Missing response text');
    return response.text;
}
```

`build` receives:

| Field | Meaning |
| --- | --- |
| `character_name`, `user_identity_name` | Names from the chat copies |
| `character_definitions`, `user_definitions` | Ordered enabled entries with `id`, `order`, and rendered `content` |
| `first_message` | Original entry 0, always supplied |
| `history` | `total_rounds`, X/Y, chronological `items`, and `uses_compressed_history`; see [memory assembly](04-memory-assembly.md) |
| `user_input` | Current input, separate from history |
| `state` | Latest JSON state object |
| `state_yaml` | YAML generated from that state, preserving Unicode, field order, and JSON types |

`state_yaml` and `history.uses_compressed_history` are application-derived read-only values. HTTP trial inputs omit them and cannot replace them with contradictory values.

`build` returns exactly `api_type` (nonblank string) and `body` (JSON object). Request-body fields are target-specific. The common runtime does not prescribe message roles, tools, or tags. Presets can merge input into a `model` message or substitute fixed user messages.

`parse` receives the complete API response object and returns a nonblank string; the module exposes it as `{"ai_output": "..."}`. The runtime validates the result type, while preset source chooses tools/candidates and validates formats and tags. Throw a JavaScript `Error` on failure. Successful text is neither trimmed nor stripped of tags.

Database text remains original before the specifically required definition rendering. State additionally has a YAML representation. Presets may transform the current request/result without changing stored originals.

## 3. Execution environment

Each `build` or `parse` creates a fresh QuickJS Context and reevaluates source. Both functions must exist. Globals and closures do not persist across invocations. One complete writing request holds the same source snapshot for its separate build and parse executions.

Only JavaScript built-ins are available. There are no Python callbacks, network, files, database, or model interfaces, and no `fetch`, `require`, `process`, `std`, or `os`. Functions must return synchronously; Promise results and asynchronous scheduling are unsupported.

| Default limit | Value |
| --- | --- |
| Source evaluation and entry execution | At most 0.5 seconds CPU per QuickJS execution |
| Context memory | 32 MiB |
| Stack | 512 KiB |
| Source, serialized input, serialized output | Each at most 2,000,000 characters; input length uses ASCII-escaped JSON |

JSON exchange isolates inputs from mutable application/database objects. Circular references, `undefined`, functions, Symbol, BigInt, NaN, and Infinity are invalid successful results. Omit unused optional request fields rather than assigning `undefined`. Input/output integers must fit JavaScript's safe integer range; use strings for larger integers.

Source, execution, type, resource-limit, and result failures become preset execution errors with no partial result or persisted candidate.

## 4. Management and isolated trials

Both collections offer the same operations:

- `/api/writing-presets`: source library.
- `/api/chats/{chat_id}/writing-presets`: chat-owned presets.

| Method/suffix | Behavior |
| --- | --- |
| `GET` collection | List presets within scope |
| `POST` collection | Submit `name`, `source`; return 201 |
| `GET /{preset_id}` | ID, owner, name, full source, creation time |
| `PATCH /{preset_id}` | Edit supplied name/source while retaining ID |
| `DELETE /{preset_id}` | Delete; return 204 |
| `POST /{preset_id}/build` | Materials in; `{api_type, body}` out |
| `POST /{preset_id}/parse` | `{"response": {...}}` in; `{ai_output}` out |

Names must be nonblank. Empty or unfinished source can be saved; execution is checked during trials. PATCH omission preserves values; null, ID, owner, and unknown fields are rejected.

Library/chat/other-chat boundaries apply to reads, changes, deletion, and trials. Copied source and IDs are independent. Before deleting the chat's selected preset, switch or clear `writing_preset_id` through chat PATCH; otherwise deletion returns 409.

Trials use supplied materials or responses after the database session closes. They do not send a chat request or change records, original text, or archive progress.

## 5. Chat request preview

`POST /api/chats/{chat_id}/writing-preview` accepts `{"user_input": "Current input"}` and uses the selected chat preset:

1. In one read transaction, require the latest archive complete and a selected preset.
2. Read source, resources, definitions, latest state, and X/Y-assembled history as detached objects.
3. Close the session.
4. Render enabled definitions against the captured state; stop on any failure.
5. Derive state YAML, execute `build`, and validate.
6. Return `chat_id`, `preset_id`, `state_snapshot_id`, and `request: {api_type, body}`.

Preview requires no model binding, makes no model call, does not merge model defaults, and does not check model compatibility. [Writing](07-writing-workflow.md) coordinates real invocation through [model calls](06-model-calls.md). Preview creates no official round.

## 6. Tool-output example

Save the full contents of `modules/presets/examples/google_tool.js` as `source`. Its top-level `fixed` object groups editable fixed text. The file is distributed with the package rather than automatically inserted into the database.

The example uses the native [Google GenerateContent API](https://ai.google.dev/api/generate-content) format and behaves as follows:

- Targets `google_generate_content` with a native request body.
- Includes First Message until the selected history uses summaries or episodes.
- Places episodes and summaries in the first historical text segment. Recent user inputs with wrappers enter `model` messages; `user` messages use fixed filler. Previous AI output merges with the next user input.
- Resends full AI output, retaining `<report_nya~>` and `<content>`; definitions enter system instructions, and state enters a separate YAML message.
- Declares `game_content(content: string)`, selects `ANY`, and restricts selection to that tool. The tool only carries text; no function is executed and no second model call is made.
- Requires exactly one candidate with `finishReason=STOP` and exactly one `game_content` invocation; extracts its `args.content`.
- Requires each of the two tags once, correctly closed, with nonblank content and no nesting or crossing. It preserves sections and tags in their original order, joins them with a newline, and discards outside text.

Tool names, arguments, tags, and restrictions belong to this editable example rather than all presets.

## 7. Errors and validation

- 404: missing or out-of-scope chat/preset.
- 409: incomplete archive, no selected preset, missing resources/state, memory conflict, or deletion of the selected preset.
- 422: invalid input, definition failure, or preset compilation/execution/result failure.

Preset failures use `{"detail": {"stage": "build or parse", "message": "Error explanation"}}`, with the message capped at 2,000 characters. Template failures retain definition IDs and available line numbers. Constraint errors omit SQL parameters.

Tests cover CRUD/PATCH, scopes and copy independence, selected-preset deletion, OpenAPI contracts, synchronous execution/types, environment isolation, CPU/memory/stack/length limits, JSON numeric boundaries, example message transformations, YAML and First Message, invalid tools/tags, current-state reads, archive prerequisites, and failure without round creation.
