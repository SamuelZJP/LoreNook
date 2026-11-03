# Agent notes

- **Never code before the plan is agreed.** When a feature or design is under discussion, do not write or change code until the user has explicitly approved the complete plan. Agreeing to one point, answering a question or saying "do it as you said" about one item does not approve the rest. Present the plan, resolve every open question, then ask for the go-ahead. If still unsure, ask.
- Personal project, single `main` branch. Commit directly to `main`.
- Keep communication and docs short and direct. No defensive caveats or repeated disclaimers.
- Write docs and code comments in English. User-facing UI text, prompts and the `世界` state keys stay Chinese.
- Docs are minimal: `README.md`, `docs/design.md`, `docs/deployment.md`. The code is the reference for implementation details. Update `design.md` only when a concept or rule changes, and only once a discussion has reached a conclusion.
- Keep code modular: high cohesion, loose coupling, plugin-like features. Where it fits, decide with plain data first and render text last. Dependency rules below are enforced by `backend/tests/test_architecture.py`.
- Run `.venv/bin/python -m pytest -q` after backend changes and `npm run typecheck` in `frontend/` after frontend changes.

## Code map

Backend dependencies point one way: `api → workflows → modules → repository, schemas, llm, shared`. Each package's `__init__.py` states its purpose.

| Path | Purpose |
| --- | --- |
| `backend/main.py` | Builds the app: core routers plus everything in `FEATURES` |
| `backend/features.py` | The installed optional features, and the contract a feature provides |
| `backend/api/` | HTTP routes, thin |
| `backend/workflows/` | Multi-step operations and transaction boundaries |
| `backend/workflows/writing.py`, `writing_materials.py` | One writing request: snapshot → materials → preset → model |
| `backend/workflows/archive.py`, `archive_step.py` | Post-confirm pipeline; the shape all its model-backed steps share |
| `backend/modules/memory/` | `sources.py` (validated records) → `layout.py` (plain numbers) → `render.py` (text) |
| `backend/modules/presets/` | Sandboxed JS presets: receive materials, build the request, parse the response |
| `backend/modules/` (others) | One package per domain concept |
| `backend/repository/` | Tables and queries |
| `backend/illustrations/` | Illustration feature; `feature.py` is its single connection to the app |
| `backend/recall/` | Memory recall feature: `service.py` runs two passes of `judge.py` with `prompts.py`, producing a layout |
| `backend/status_bar/` | Status bar feature: per-character HTML, rendered in a sandboxed frame by `frontend/src/features/status_bar/` |
| `frontend/src/composables/roundFlow.ts` | Round lifecycle in the browser; `WriteStep` is the seam for a step before writing |
| `frontend/src/features/` | Frontend of optional features; core views only place their components |
