# LoreNook Model Calls

[中文](../zh-CN/backend/06-model-calls.md) | [Backend overview](README.md)

Updated: 2026-10-19

## 1. Responsibilities and implementation

Manage source and chat model configurations, resolve purpose bindings, and execute one HTTP model request. Check API compatibility, merge defaults, and construct the URL and authentication before sending. Return the complete JSON response to presets or archive generation modules.

Paths below are relative to `backend/`.

| File | Responsibility |
| --- | --- |
| `schemas/models.py` | Configuration edits, public reads, internal connection snapshots, results |
| `modules/models/service.py` | Ownership, management, purpose lookup |
| `llm/parameters.py` | Recursive default merging |
| `llm/google.py` | Google URL/model/authentication adapter |
| `llm/client.py` | HTTPX calls, timeouts, response limits, errors |
| `api/models.py` | Configuration and direct-call endpoints |

Supported: `google_generate_content` and `deepseek_chat_completions`. Other APIs need adapters; incompatible presets are not silently converted. Existing tables are reused without migrations.

This layer does not execute presets or tools, extract tool arguments, save rounds, or advance archives. Preview builds a request; the [writing workflow](07-writing-workflow.md) coordinates the full send.

## 2. Configuration and ownership

Fields are `name`, `api_type`, `base_url`, `api_key`, `model`, and `default_parameters`. Creation requires everything except key and defaults. Name, API type, and model are nonblank. Key defaults to an empty string; parameters to `{}`.

- `base_url` is an HTTP(S) API root including a version when needed, for example `https://generativelanguage.googleapis.com/v1beta`. Exclude model paths, operation names, URL credentials, query strings, and fragments.
- Unsupported nonblank `api_type` values can be saved for editing but are rejected before invocation.
- Defaults use native request fields. Google generation parameters belong under `generationConfig`, for example `{"generationConfig": {"temperature": 0.8}}`.
- Credentials are stored separately and passed internally as `SecretStr`. Public reads return `has_api_key`. PATCH omission retains the key, an empty string clears it, and null is rejected.

Source, chat, and other-chat scopes are separate. Chat creation copies and remaps resources; shared purpose references copy a source configuration once. Source changes do not affect copies, and chats remain independent.

Deleting a chat configuration cascades to its purpose bindings. Later callers receive a missing-binding error.

## 3. Snapshots and transactions

`ModelService(repository, chat_id).connection(config_id)` returns a detached internal connection with API type, URL, key, model, and defaults.

`for_purpose(purpose)` reads the `chat_id + purpose` binding and verifies same-chat ownership. Purposes are `writing`, `state_update`, `round_summary`, and `episode_summary`. This lookup is chat-only; missing bindings are conflicts.

Read a connection snapshot in a short transaction, close the session, then call `ModelClient.invoke(connection, built_request)`. Editing during a call affects the next snapshot. Configuration changes commit through caller-owned write transactions.

## 4. Compatibility and parameter merging

Invocation accepts `{api_type, body}`. API type must exactly match the configuration and have an adapter; otherwise no request is sent.

Recursively fill missing request values from defaults:

- If both values are objects, merge by key.
- Explicit scalars, arrays, `false`, `0`, empty strings, and null win; arrays replace as a whole.
- An explicit empty object can still receive missing default keys; it does not clear the entire object.
- Work on copies without changing configuration, preset inputs, or stored text.

```text
Defaults: {"generationConfig": {"temperature": 0.8, "topP": 0.9}}
Request:  {"generationConfig": {"temperature": 1, "seed": null}, "contents": [...]}
Merged:   {"generationConfig": {"temperature": 1, "topP": 0.9, "seed": null}, "contents": [...]}
```

Results must serialize to valid JSON; NaN and Infinity are rejected. Beyond required adapter structure, there is no model-capability or parameter allowlist. The target API validates supported parameters.

## 5. Google GenerateContent

Native request behavior follows the [Google GenerateContent REST API](https://ai.google.dev/api/generate-content).

- POST nonstreaming requests to `{base_url}/models/{model}:generateContent`.
- Use the configured model unless the merged body explicitly supplies `model`; remove that override from the actual body. Accept an optional `models/` prefix, then only letters, digits, dots, underscores, and hyphens, preventing path-level changes.
- Put a nonempty key in `x-goog-api-key`, never the URL. Omit the header for an empty key, supporting compatible services that do not require it. Keys must be visible ASCII without spaces/newlines.
- Send `Content-Type: application/json` and require a nonempty `contents` array. Send other native fields as merged.
- Return the whole response object, including candidates, parts, tools, usage, and `promptFeedback`. A top-level `error` becomes a provider error. Presets decide what response is acceptable.

Tools are not executed and invocation does not append another model request.

### DeepSeek Chat Completions

`llm/deepseek.py` implements `deepseek_chat_completions`; see the [native API](https://api-docs.deepseek.com/api/create-chat-completion/).

- POST to `{base_url}/chat/completions`. Configure required version paths explicitly, for example `http://gateway:3000/v1`; no endpoint guessing or fallback calls.
- Keep `model` in the body, defaulting to the configured name with explicit request values taking precedence. Require nonempty `messages`. Gateways may route by model name; LoreNook uses the configured API type rather than inferring protocols from names.
- Nonempty keys use `Authorization: Bearer ...`, subject to existing URL/key validation. Empty keys omit authentication.
- Default `stream=false` and reject streaming. Return complete choices, tools, reasoning, usage, and additional fields; top-level errors retain provider classification.
- Use native top-level defaults, for example `{"temperature": 0.2, "max_tokens": 4096, "stream": false, "thinking": {"type": "disabled"}}`. Do not mix Google fields; model/gateway support determines accepted parameters.

State updates and both summary generators share `llm/generation.py` for native requests and `llm/text.py` for visible text. DeepSeek sends system/user text in order using non-streaming output: state/round summaries request `response_format: {"type": "text"}`, while episode summaries request `{"type":"json_object"}`. Google uses `text/plain` and `application/json`, respectively. Require one stopped assistant choice with nonblank content; the episode generator then validates the title/summary JSON. Reject tools/refusals/truncation and exclude native reasoning while retaining complete raw call logs.

The three archive purposes may share one chat-local DeepSeek configuration while writing uses another. Library and chat copies remain independent. Call journals take the model name from the final DeepSeek body or adapted Google URL; they never save authentication headers or URLs.

## 6. HTTP behavior

Each application lifecycle owns one synchronous `ModelClient` and closes its HTTPX Client on exit. Synchronous APIs execute in worker threads. Tests inject `create_app(..., llm_transport=...)` instead of contacting models.

Default timeouts: connect 10 seconds, write 30, pool wait 5, read 120. `Settings.llm_timeout_seconds` controls the read timeout per network read operation, not a total generation deadline.

See [HTTPX timeout behavior](https://www.python-httpx.org/advanced/timeouts/).

No automatic retries, redirects, or environment proxy configuration. Each `invoke` sends at most one POST; callers decide whether to retry.

Success requires 2xx. Stream-read the response with a default decoded limit of 8 MiB, configurable through `Settings.llm_max_response_bytes`. Oversized responses fail and close immediately. Require a valid JSON object; reject arrays, empty/invalid responses, nonfinite numbers, and strings that cannot be emitted as UTF-8.

## 7. HTTP endpoints and errors

Collections: `/api/model-configs` for sources and `/api/chats/{chat_id}/model-configs` for copies.

| Method/suffix | Behavior |
| --- | --- |
| `GET` collection | List without raw keys |
| `POST` collection | Create; return 201 |
| `GET /{config_id}` | Read configuration and `has_api_key` |
| `PATCH /{config_id}` | Supplied fields only; reject null for non-nullable fields, IDs, owners, and unknown fields |
| `DELETE /{config_id}` | Delete with bindings; return 204 |
| `POST /{config_id}/invoke` | Submit `{api_type, body}`, make one actual call, return `{"response": {...}}` |

Direct invocation works for source and chat configurations. It does not execute presets, check archive completion, or create a round. The writing workflow owns those rules.

- 404: missing or out-of-scope chat/configuration.
- 409: missing purpose binding or database relationship/uniqueness conflict.
- 422: invalid fields/JSON, API mismatch or unsupported type, invalid URL/model/key, or missing request structure.
- 504: timeout, `kind=timeout`.
- 502: `network`, `http`, `invalid_response`, `response_too_large`, or `provider` errors.

Errors use `{"detail": {"kind": "...", "message": "Fixed explanation", "upstream_status": 429}}`; `upstream_status` may be null. Do not echo URLs, credentials, request bodies, or upstream error text. Request-validation errors retain locations and explanations but omit raw `input`, including model-level inputs that might contain a key.

## 8. Validation

HTTPX MockTransport tests inspect constructed requests without real calls or credit use. Coverage includes recursive merging and explicit values, model overrides, detached originals, URL and headers, compatibility, no-key calls, complete JSON, HTTP/network/timeout mapping, disabled redirects/retries, JSON/size checks, credential redaction, CRUD/PATCH, scopes, copied/shared purposes, source deletion independence, binding cascades, and database writes during network execution.
