# LoreNook Frontend — Temporary Functional Brief

Date: 2026-10-19  
Status: Temporary handoff for frontend exploration and implementation.

## Purpose and freedom of design

Build a usable web frontend for LoreNook, a personal AI roleplaying tool centered on independent chats, layered memory, and programmable writing presets.

The selected foundation is **Vue 3 + TypeScript + Vite + Vue Router**. Other libraries are implementation choices. TanStack Vue Query, CodeMirror, and OpenAPI-generated TypeScript types are possible additions, not requirements.

This brief describes required capabilities and existing business constraints. It intentionally leaves visual style, layout, navigation structure, component libraries, and detailed interactions open. Functional areas below do not have to become separate pages. Propose solutions appropriate to a writing and roleplaying application.

The existing Python/FastAPI backend owns persistence, model calls, template execution, memory assembly, and archiving. Use its implemented contracts rather than recreating these operations in the browser.

## 1. Chats and the roleplaying workflow

Users need to:

- List, open, create, rename, and delete chats.
- Create a chat from a source character and a source user identity, choosing presets and model configurations to copy and use.
- Read the character's First Message as a separate opening entry, conventionally floor 0, followed by chronological rounds.
- Compose input, generate a reply, inspect the candidate, and regenerate before confirmation. Editing the input before regeneration must also be supported. Empty input is permitted by the backend.
- Explicitly accept a candidate by confirming it for archiving.
- Understand whether the current interaction is generating, awaiting confirmation, archiving, failed, or complete, and which actions are available.
- Reopen a chat and recover its persisted archive progress.

A round consists of one user input and one approved AI output. Generation returns an **unsaved candidate**. Only confirmation saves the formal round. Pending candidates do not currently require temporary persistence or restoration after reload.

Archiving saves the text, updates state, generates a round summary, decides whether an episode is needed, and generates that episode when required. A new round cannot begin until the previous archive completes. Show saved-but-incomplete rounds as such rather than presenting them as fully archived.

Failures must preserve useful context and provide an explicit recovery action. Retry the unfinished archive through the backend's retry endpoint; do not recreate the round or restart successful steps. After successful archiving, the normal chat interface permits manual editing of the latest state, latest round summary, and any episode produced by that latest round. It does not regenerate a completed archive or edit historical round text. Historical changes belong to data management.

## 2. State, summaries, episodes, and memory

- Display the latest state, including the initial state before the first round.
- Make round summaries and episodes accessible alongside conversation history. Episodes have separate titles and summaries and cover explicit round ranges.
- Allow the latest permitted results to be edited and saved, surfacing validation errors without losing the user's edits.
- Expose chat memory settings: recent full rounds (`recent_rounds`, X) and minimum retained round summaries (`min_summaries`, Y).
- Provide a way to inspect the backend-assembled memory/context when needed for understanding or debugging requests.

The backend chooses chronological episode summaries, individual round summaries, and recent full rounds without overlapping representations. The frontend must not implement its own competing memory selection. Editing a saved state or summary takes effect immediately and does not automatically recompute other results.

State is typed JSON and may contain arbitrary nested fields. Preserve numbers, booleans, arrays, objects, and strings. The required world fields keep their exact Chinese keys: `世界`, with `日期`, `星期`, `时间`, and `地点`. Dates use `YYYY-MM-DD`, times use `HH:mm`, and weekdays use `星期一` through `星期六` or `星期日`; location may be empty. Do not translate stored keys. Normal state edits are validated and may be corrected by the character's Schema on the backend.

## 3. Characters, user identities, and definitions

- Manage source characters and source user identities: create, read, edit, and delete.
- Edit names, descriptions, and avatar references.
- For characters, edit First Message, Python/Pydantic state Schema, state reference information, and state update rules.
- Manage character-owned and identity-owned definition entries, including content, order, enabled status, and whether the content contains a template.
- Support editing the chat-owned copies of these resources as well as their source versions.
- Make definition parsing errors actionable, using entry and line information when available. The backend also provides a chat definition-resolution preview.

A user identity is a roleplay persona, not an account. Creating a chat copies resources into independent chat-owned records. Editing the source library does not update existing chats. Make the editing scope understandable and use the copied IDs returned by the backend for chat configuration.

Definitions use Jinja2 and resolve against the latest state on the backend. Preserve their source text. A parsing failure stops generation before the model call.

Character creation and Schema changes validate the Schema's default initial state. An empty Schema is not a valid working default. The repository includes a usable example at `backend/modules/state/examples/basic.py`; make valid setup practical rather than requiring users to discover the contract by trial and error.

## 4. Writing presets and model configuration

- Manage source and chat-owned writing presets, including names and JavaScript source.
- Select the active preset for a chat.
- Support backend build/parse trials and a chat writing-request preview so users can diagnose preset behavior.
- Manage source and chat-owned model configurations: name, API type, base URL, model, API key, and default parameters.
- Bind chat models to the four purposes: `writing`, `state_update`, `round_summary`, and `episode_summary`. One configuration may serve multiple purposes.
- Offer a practical model-call test using the existing invocation API and an appropriate request body.

The current adapters are `google_generate_content` and `deepseek_chat_completions`. Preset API type and writing model API type must be compatible. The backend handles request construction, default parameter merging, credentials, and calls. Presets execute JavaScript on the backend and do not control archiving or presentation.

Normal model reads return `has_api_key`, not the stored key. Omitting `api_key` during an update preserves it; explicitly sending an empty string clears it. Do not accidentally erase credentials when saving other fields.

Source editing should preserve formatting and provide a comfortable multiline editing experience. The exact editor is open. A complete preset example is available at `backend/modules/presets/examples/google_tool.js`.

## 5. Output presentation and frontend preferences

AI output may contain `<content>`, custom `<think>`, and other preset-defined sections. Provide a coherent way to display, hide, or collapse sections and expose the relevant rendering preferences. Custom `<think>` text is distinct from a provider's native reasoning output.

Keep the accepted output unchanged for confirmation and storage. Presentation transformations must not strip hidden sections from the stored text. The archive backend requires exactly one closed, nonempty `<content>` section and uses only its body for derived results.

The frontend may choose Markdown or other rendering behavior where useful, but model text must not become executable browser code. Define sensible behavior for unknown sections and malformed content. Visual preferences and their interaction design remain open.

There is currently no unified backend endpoint for global appearance or parsing preferences. Browser-local persistence is a reasonable initial choice; be explicit about its scope. Existing chat and model settings should use their actual backend APIs. Some summary-context settings are currently server configuration values rather than editable web settings.

## 6. Data management

Provide a separate advanced capability to inspect and batch-create, update, or delete business records, including historical rounds, states, summaries, episodes, and archive fields. The backend exposes table metadata and row schemas to support this.

Reads return a revision; submit changes with that `expected_revision`. The backend validates the final dataset and applies a batch atomically. On conflict, let the user refresh and reconcile changes rather than silently overwriting newer data. Make pending changes and the outcome of a batch understandable.

This is broader than normal chat editing. Administrative state writes check JSON, required world fields, and associations without running the character Schema. They do not trigger models or recompute dependent results. Keep model secrets hidden by default; ordinary inspection does not need `include_secrets=true`.

## 7. Integration notes

- Business routes use `/api`; health is `/health`; interactive documentation is `/docs`; OpenAPI is `/openapi.json`. Use `backend/schemas/` and the generated OpenAPI for exact fields and payloads.
- Generation currently returns a complete response, without token streaming. Archiving runs its remaining steps within the confirmation or retry request. Allow sufficient waiting time and use progress queries where helpful.
- Confirmation must forward the candidate's `user_input`, full `ai_output`, and `based_on_round_id`; the latter is explicitly `null` for the first round. If the input is edited, regenerate so the accepted input and output stay paired.
- After a lost confirmation response or a timeout, query the latest archive progress before deciding what to do next. Do not blindly resend confirmation or automatically retry model-producing mutations. Browser request cancellation does not establish that server work was cancelled.
- Archive errors may include an `archive` object even on a non-success HTTP response. Use it to reconcile saved progress. Retry uses the latest unfinished round and its current `expected_step`.
- Error `detail` may be a string, a validation array, or a structured object. Handle all forms and preserve useful diagnostics. Refresh relevant data after mutations and conflicts.
- Request contracts reject unknown fields and are strict about types. For PATCH, omission usually means unchanged; explicit `null` is accepted only for designated nullable fields.
- Current history endpoints return full lists. Begin with that contract; add rendering optimizations when actual history sizes justify them.
- Avatar fields currently store references; there is no avatar upload/storage endpoint.
- A Vite development proxy for `/api` can connect to FastAPI without requiring browser CORS changes. Production hosting and packaging remain open; a same-origin static frontend and API is a suitable option. If using history-based routing, configure route fallback accordingly.
- Run database migrations before integration. At the review on 2026-10-19, the default database was one migration behind; `python -m alembic upgrade head` applies the pending episode-title migration. This is a local setup observation, not a permanent product constraint.

## 8. Delivery focus and verification

Prioritize a working vertical slice: configure valid resources, create a chat, generate and regenerate, confirm, read derived results, recover a failed archive, and continue the conversation. Complete the supporting editors, data management, and preferences around that workflow.

Verify the first-round and later-round paths, candidate/original-text preservation, source-versus-chat independence, incomplete archive recovery after reload, failed requests, credential-preserving edits, and data revision conflicts. The backend review passed 614 tests; frontend behavior and end-to-end integration still need their own validation.

Image generation, voice, multi-user accounts, offline operation, and pending-candidate restoration are outside the current required scope. Additional libraries and interaction refinements should follow demonstrated needs. You are encouraged to propose better organization and interactions while retaining the lifecycle and ownership rules above.

## References

- [Project setup and API overview](../README.md)
- [Product design](design/product-design.md)
- [Data model](design/data-model.md)
- [Backend overview and module references](backend/README.md)
- [Writing workflow](backend/07-writing-workflow.md)
- [Archive contracts and recovery](backend/12-archiving-workflow.md)
- [Data management contracts](backend/13-data-management.md)

This temporary brief does not replace those detailed contracts. It can be revised or removed once the frontend direction and implementation are established.
