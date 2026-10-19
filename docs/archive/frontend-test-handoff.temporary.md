# LoreNook Frontend — Temporary Testing Handoff

Archived: 2026-10-20. This records the original mock-backed smoke checks and testing handoff. Statements about untested or unpackaged work describe that stage, not present deployment status. Later owner acceptance is recorded in [milestone 1](../releases/milestone-1.md); operations are documented in the [deployment guide](../deployment/ubuntu.md).

Date: 2026-10-19
Status: The frontend build is complete; testing is handed to the next stage. The original requirements are in [frontend-handoff.temporary.md](frontend-handoff.temporary.md).

## 1. State of the work

The `frontend/` application implements every functional area of the brief: chats and the round workflow, state/summary/episode/memory views and edits, characters/identities/definitions, presets and models, output display preferences, and data management. `npm run build` (type check included) passes. No automated frontend tests exist yet, and no test framework is installed.

Only smoke checks were run, in a browser against the mock backend (section 2). They covered: creating a chat; generating and confirming the first and a later round; a round-summary failure, a reload, and retry; an episode created after a date change and shown in the timeline; the memory tab; a revision conflict in data management; and a definition template error during generation. Layouts were checked at desktop and phone width (375 px), in light and dark themes. Everything else below is untested.

## 2. Environment

1. Backend environment: `python -m venv .venv`, install `requirements-dev.lock`, then `pip install --no-deps -e .` (see the root README; on Linux use `.venv/bin/python`).
2. Frontend: `cd frontend && npm install`.
3. Backend, choose one:
   - Real: `alembic upgrade head`, then `uvicorn backend.main:app` on port 8000. This needs real model credentials.
   - Mock (recommended for most tests): `python frontend/dev/mock_backend.py --port 8765 --reset`. It uses `data/mock.db`, seeds example resources, and never contacts a provider. The input markers listed in `frontend/README.md` force failures, invalid output, date changes, and slow calls.
4. Frontend server: `npm run dev`, or `npm run build && npm run preview` (port 4173). Set `LORENOOK_BACKEND=http://127.0.0.1:8765` for the mock.

The Claude desktop browser pane blocks Vite's `/@vite/client`, so the dev server renders a blank page there. Use the preview build in that pane. `.claude/launch.json` includes `frontend-mock-preview` for this.

Native `confirm()` dialogs guard destructive actions and batch submission. Automated runs must accept them, for example with Playwright's `page.on('dialog', d => d.accept())`.

## 3. Verification checklist

These map to section 8 of the original brief. "Mock" means the scenario can be reproduced with the mock backend.

| Area | Scenario | Expected |
| --- | --- | --- |
| Setup | Create a character with the default (example) Schema, an identity, a preset, and a model in the library | Each is saved. An empty or invalid Schema returns 422, the error is shown, and the draft is kept |
| First round (mock) | New chat → send → confirm | Floor 0 First Message, then the user and AI bubbles. Confirmation sends `based_on_round_id: null`. The archive banner shows its steps and then disappears |
| Later rounds (mock) | Send again after a completed archive | `based_on_round_id` equals the latest round ID |
| Regenerate | Generate, edit the input, regenerate | The candidate is replaced. While the composer input differs from the candidate's input, confirm is disabled with a warning |
| Empty input | Send with an empty composer | Allowed. Shown as "（空输入）" |
| Original text | Confirm a candidate with extra sections and whitespace | The stored `ai_output` (raw view, data management) matches the candidate exactly. Hiding or collapsing sections does not change it |
| Generation failure (mock `[[fail-writing]]`, `[[bad-output]]`) | Send | The error is shown, the input and any previous candidate are kept, and no round is created |
| Archive failure (mock `[[fail-state_update]]`, etc.) | Confirm | The round shows "已保存 · 待…". The banner shows the recorded error and a "继续归档" action that sends the current `expected_step`. The composer is blocked |
| Recovery after reload (mock) | Reload while the archive is incomplete, then retry | Progress is restored from `GET /archive`, retry completes, and successful steps are not rerun |
| Lost confirmation response | Kill the connection or backend during confirmation (mock `[[slow]]`) | The client reads progress instead of resending. The candidate is cleared if the round was saved, otherwise it is kept with a note |
| Episodes (mock: five rounds, then `[[newday]]` twice) | Continue rounds | The episode card appears after its end round. Only an episode created by the latest completed round is editable |
| Latest-result editing | Edit the latest state, summary, and episode | Saved immediately. Validation errors keep the draft. The state may be corrected by the Schema (a toast says so). Older rounds offer no edit |
| State types | Edit state with numbers, booleans, nested arrays, and Chinese keys | Types and keys are preserved. The world-field form edits `世界` without touching other fields |
| Memory | Memory tab with various X/Y settings | Shows the backend selection. Definition resolve and writing preview work. Writing preview requires a complete archive and a selected preset |
| Source vs chat | Edit a source character after creating a chat, and edit the chat copy | Neither affects the other. The scope banner names which copy is being edited |
| Definitions | Add, reorder, enable/disable, template on/off; break a template | Order persists. Template errors show the entry number and highlight the line (resolve preview), and generation errors name the entry |
| Presets | Build trial (sample or "用当前聊天素材"), parse trial, optional invoke | Results or `stage`/`message` errors are shown. Trials use the saved source |
| Model credentials | Edit other fields of a model with a key | `api_key` is not sent and `has_api_key` stays true. "替换" sends a new key, and "清除" sends `""` |
| Model test | Invoke on a configuration | One call, with the response and extracted text shown. Upstream errors show `kind` and `upstream_status` |
| Data management | Stage create, update, and delete operations, then submit | Atomic result. The pending list is understandable |
| Revision conflict | Stage a change, modify the same row elsewhere, submit | 409. "重新读取并核对" keeps pending changes and flags the changed or missing targets. Submission is blocked until each flag is resolved ("基于最新数据保留" or undo) |
| Responsive | 375 px, 768 px, 1024 px, ≥1280 px | Sidebar is a drawer below 900 px. The side panel is full-screen on phones, overlays the chat between 900 and 1279 px, and sits beside the chat at 1280 px or more |
| Theme | System, light, dark (sidebar button or settings) | All views remain readable. The stored theme applies before first paint |

## 4. Areas worth extra scrutiny

- `roundFlow.ts` lost-response detection. A request counts as "no answer" on a fetch exception or on any error response without a JSON `detail` (proxy errors, unhandled 500). Handled backend errors, including model 502/504 with JSON `detail`, count as answered.
- `contentProblem` in `lib/sections.ts` only warns. The backend's archive validation is authoritative.
- `parseSections` assumes non-nested top-level tags. Malformed or unclosed tags fall back to visible text.
- Data-management conflict detection compares rows with `JSON.stringify`, so it depends on the backend returning stable key order.
- History endpoints return full lists, and the timeline renders them all with no virtualization.
- Chat views are keyed by route, so leaving a chat during generation discards that candidate.

## 5. Out of scope or not implemented

Pending-candidate restoration after reload, avatar upload (avatars are references only), streaming, multi-user accounts, offline use, and production packaging. Server-side summary-context settings are not editable from the web UI.

This document is temporary and can be removed once the testing results are recorded.
