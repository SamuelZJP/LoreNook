# LoreNook Frontend

Vue 3 + TypeScript + Vite + Vue Router single-page application for LoreNook. It is a chat-style interface with light and dark themes and a responsive layout for desktop and phone widths. The interface language is Chinese, matching the stored content and backend messages.

## Commands

Run from `frontend/`:

| Command | Purpose |
| --- | --- |
| `npm install` | Install dependencies |
| `npm ci` | Install exactly from the committed lock file |
| `npm run dev` | Dev server on http://localhost:5173, proxying `/api` and `/health` to the backend |
| `npm run build` | Type-check (`vue-tsc`) and build to `dist/` |
| `npm run preview` | Serve the built `dist/` with the same proxy |
| `npm run typecheck` | Type-check only |
| `npm run gen:api` | Regenerate `src/api/schema.d.ts` from a running backend's `/openapi.json` |

The proxy target defaults to `http://127.0.0.1:8000`; set `LORENOOK_BACKEND` to use another address. Proxy timeouts are disabled because generation and archiving can run for minutes.

Production uses Caddy to serve `dist/` from the same origin as the API, with history-route fallback to `index.html`. Keep API requests outside that fallback. The existing deployment and update procedure is documented in [Ubuntu deployment and operations](../docs/deployment/ubuntu.md). Vite development and preview servers are local tools.

## Mock backend

`dev/mock_backend.py` runs the real FastAPI application against a separate SQLite file (`data/mock.db` by default) with an in-process mock model transport. No request reaches a model provider. On first start it seeds an example character (with the example Schema), an identity, the example Google tool preset, and a mock `google_generate_content` model configuration.

```bash
python frontend/dev/mock_backend.py --port 8765 --reset
LORENOOK_BACKEND=http://127.0.0.1:8765 npm run dev
```

Markers in the user input change the mock behavior: `[[fail-writing]]`, `[[fail-state_update]]`, `[[fail-round_summary]]`, `[[fail-episode_summary]]` (the archive markers fail the first attempt only, so retry succeeds), `[[bad-output]]` (no `<content>`, so the preset parse fails), `[[newday]]` (advances `世界.日期`, which drives episode decisions), and `[[slow]]` (15-second delay per model call). See the script docstring.

## Structure

| Path | Responsibility |
| --- | --- |
| `src/api/` | `schema.d.ts` (generated), `client.ts` (fetch wrapper, `ApiError` normalizing every `detail` form plus `archive` progress), `endpoints.ts` (typed endpoint functions) |
| `src/composables/roundFlow.ts` | Round lifecycle: generate, regenerate, confirm, retry, and reconciling a lost confirmation response by reading progress |
| `src/lib/sections.ts` | Splits AI output into tag sections for display; `contentProblem` mirrors the archive's `<content>` requirement |
| `src/lib/prefs.ts` | Browser-local preferences (theme, font size, reading fonts, per-tag rendering category and display mode, send key, floor display limit) |
| `src/lib/fonts.ts` | Chinese and English reading font stacks; the English stack goes first so Latin text takes it and CJK falls through to the Chinese stack |
| `src/lib/quotes.ts` | Recognizes standalone and inline quotations in main prose; `src/lib/markdown.ts` applies it during Markdown rendering |
| `src/styles/reading.css` | Reading surface, prose typography, quotation, thought, and other-content styles; reading tokens live in `tokens.css` |
| `src/lib/admin.ts` | Data-management staging, operations, and conflict detection |
| `src/views/ChatView.vue` | Chat timeline, candidate, archive banner, composer, side panel |
| `src/components/panel/` | Chat side panel: state, memory and diagnostics, chat settings, chat-owned resources |
| `src/components/editors/` | Character/identity, definitions, preset (with build/invoke/parse trials), and model editors, shared by library and chat scopes |
| `src/views/DataView.vue` | Revision-checked batch editing of all business tables |

## Behavior notes

- Saved data always comes from the backend. Only the unconfirmed candidate lives in memory and is lost on reload; the page warns before unloading while a candidate or request is pending.
- Model text is rendered with Markdown-it with raw HTML disabled and images disabled; display preferences never change stored output.
- The floor display limit (default 100, or unlimited) only limits rendering; earlier floors can be revealed in the chat, and the model context is unaffected. Round summaries are collapsed by default.
- Model editing sends `api_key` only when the user explicitly chooses to replace or clear it.
- Preferences are stored in `localStorage` under `lorenook.prefs` (and `lorenook.panel` for the side panel) and apply to this browser only.
