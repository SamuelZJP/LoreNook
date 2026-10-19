# LoreNook Definition Management and Rendering

[中文](../zh-CN/backend/03-definition-rendering.md) | [Backend overview](README.md)

Updated: 2026-10-19

## 1. Responsibilities and implementation

Definitions belong to characters or user identities. This module manages ordered original text and renders templates against the latest state. Results apply only to the current request.

Paths below are relative to `backend/`.

| File | Responsibility |
| --- | --- |
| `schemas/definitions.py` | Edit, reorder, and rendering contracts |
| `modules/definitions/service.py` | Owner-scoped entry management and whole-list ordering |
| `modules/definitions/storage.py` | Lists used during resource creation and copying |
| `modules/definitions/renderer.py` | Jinja rendering for preview and writing |
| `workflows/resolve_definitions.py` | Consistent snapshot read, rendering outside the transaction |
| `api/definitions.py` | Source-library and chat-owned endpoints |

The writing workflow proceeds to request construction only after every participating definition succeeds. This module does not construct or invoke model requests.

## 2. Management

Every entry contains `order`, `enabled`, `has_template`, and `content`, plus its ID and resource-derived owner.

- `order`: nonnegative integer, default 0; sort by order then ID, allowing ties.
- `enabled`: default true; disabled entries are neither rendered nor supplied to presets.
- `has_template`: default false; ordinary entries bypass Jinja syntax checking and execution.
- `content`: original text, allowed to be empty; an empty rendered result is valid.

Entry edits, enabled toggles, and reordering preserve IDs. Saving does not execute templates, so incomplete templates may be stored and checked when used. Source characters, source identities, and their chat copies have separate scopes; IDs cannot transfer ownership or bypass scope. Copying generates new IDs.

### HTTP interface

These collections support identical operations:

| Collection | Owner |
| --- | --- |
| `/api/characters/{id}/definitions` | Source character |
| `/api/user-identities/{id}/definitions` | Source identity |
| `/api/chats/{id}/character/definitions` | Chat character |
| `/api/chats/{id}/user-identity/definitions` | Chat identity |

| Method/suffix | Behavior |
| --- | --- |
| `GET` collection | All definitions, including disabled entries, in order |
| `POST` collection | Create; return 201 |
| `GET /{definition_id}` | Read one entry |
| `PATCH /{definition_id}` | Change supplied business fields |
| `DELETE /{definition_id}` | Delete; return 204 |
| `PUT /reorder` | Reorder all entries using a complete ID list |

```json
{"definition_ids": ["second-definition-id", "first-definition-id"]}
```

The list must contain each owner-scoped definition exactly once, including disabled entries. Success resets order to 0, 1, 2, and so on. Duplicate IDs return 422; missing, extra, or foreign IDs return 409 without changes. An empty collection accepts an empty list.

PATCH omission preserves values; explicit null, ID, and owner fields are rejected. Resource-level `definitions` replacement remains available but creates new IDs; use entry endpoints to preserve them.

## 3. Template execution

Execution follows the [Jinja sandbox](https://jinja.palletsprojects.com/en/stable/sandbox/) and [Jinja API](https://jinja.palletsprojects.com/en/stable/api/) documentation.

Jinja2 uses `ImmutableSandboxedEnvironment` and `StrictUndefined`. The sole business-context variable is `state`, a complete JSON copy of the latest state. Default Jinja helpers, filters, and tests remain available; application objects, sessions, repositories, and configuration are not supplied.

```jinja
Current date: {{ state["世界"]["日期"] }}
{% if state["年龄"] > 10 %}Use the older description.{% else %}Use the younger description.{% endif %}
{% for name in state["在场人物"] %}{{ name }}{% if not loop.last %}, {% endif %}{% endfor %}
```

Use bracket notation for nested JSON. A missing bracket key produces an undefined value without falling back to dictionary methods; missing `state["items"]` will not resolve to `dict.items`.

Unhandled missing fields, syntax errors, and runtime errors fail the request. Optional fields can be handled explicitly:

```jinja
{{ state["可选字段"] | default("Not set") }}
{% if state["可选字段"] is defined %}{{ state["可选字段"] }}{% endif %}
```

No HTML escaping is performed, preserving tags such as `<content>`. Templates retain trailing newlines, while Jinja normalizes their line endings to LF. Plain entries preserve original CRLF and template symbols.

The immutable sandbox blocks mutation of JSON dictionaries/lists and access to Python internals. No external template loader is configured, so file-based includes, imports, and inheritance are unavailable. Each template streams output and fails above 1,000,000 characters rather than returning a truncated success.

Each rendering operation creates a new state copy shared across its entries; mutating methods are blocked. Results are not persisted.

## 4. Chat rendering endpoint

`POST /api/chats/{id}/definitions/resolve` uses stored latest state, without a client-supplied replacement. Preview and writing share the renderer.

1. Read chat character, identity, definitions, and state in one transaction.
2. Record the snapshot ID and detach definition data.
3. Close the session.
4. Filter disabled entries and render each owner group in order.
5. Return both groups only if all succeed.

| Response field | Meaning |
| --- | --- |
| `chat_id` | Current chat |
| `state_snapshot_id` | State used for rendering |
| `character_definitions` | Ordered ID/order/rendered-content entries |
| `user_definitions` | Ordered identity entries in the same shape |

Latest state is selected by round number, or initial state before round 1. Each request rereads edits. Rendering preview can use state already saved during archiving; the writing workflow separately requires a completed archive before sending.

## 5. Errors and transactions

- 404: resource/chat/definition missing or outside scope.
- 409: reorder membership mismatch or required chat resources/state missing.
- 422: invalid parameters or template compilation/execution failure.

```json
{
  "detail": {
    "definition_id": "failed-definition-id",
    "message": "Missing field or template error",
    "line": 2
  }
}
```

Line is included when locatable. The first failure stops processing and discards partial results. Rendering holds no transaction and changes no text, state, or archive progress. Edits and reorder operations each commit in one write transaction or roll back together.

## 6. Validation

Tests cover four ownership scopes, rejected cross-scope access, PATCH behavior, ID preservation, full ordering and rollback, nested JSON, conditions/loops, disabled entries, plain-text preservation, undefined variables and error locations, sandbox and length limits, latest-state reads, and no partial group results.
