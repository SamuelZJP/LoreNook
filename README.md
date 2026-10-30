# LoreNook

A personal AI roleplay tool built around chats, layered memory, and programmable writing presets. FastAPI + SQLite backend, Vue 3 frontend.

- [docs/design.md](docs/design.md) — concepts, round lifecycle, archiving, memory, state rules
- [docs/deployment.md](docs/deployment.md) — production setup, updates, backups
- API reference: http://127.0.0.1:8000/docs (Swagger, while the backend runs)

## Development

Python ≥ 3.12, Node `^20.19.0 || >=22.12.0`.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn backend.main:app --reload
```

The database defaults to `data/lorenook.db`; set `LORENOOK_DATABASE_URL` (e.g. `sqlite:///data/dev.db`) to use another. Relative paths resolve from the project root. Uploaded images are stored under `LORENOOK_MEDIA_DIRECTORY` (default `data/media`), generated illustrations under `LORENOOK_IMAGE_DIRECTORY` (default `data/images`). Startup never migrates — run `alembic upgrade head` yourself.

Frontend (proxies `/api` to `LORENOOK_BACKEND`, default `http://127.0.0.1:8000`):

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. Other scripts: `npm run build`, `npm run typecheck`, `npm run gen:api` (regenerates `src/api/schema.d.ts` from a running backend).

### Mock backend

Runs the real app against `data/mock.db` with a fake model, seeded with an example character, identity, preset and model config:

```bash
python frontend/dev/mock_backend.py --port 8765 --reset
LORENOOK_BACKEND=http://127.0.0.1:8765 npm run dev
```

Put markers in the user input to trigger behavior: `[[fail-writing]]`, `[[fail-state_update]]`, `[[fail-round_summary]]`, `[[fail-episode_summary]]` (archive markers fail only the first attempt), `[[bad-output]]`, `[[newday]]` (advances `世界.日期`), `[[slow]]`.

## Tests and migrations

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m alembic check
.venv/bin/python -m alembic revision --autogenerate -m 'describe change'
```

`requirements-dev.lock` pins tested versions; `pyproject.toml` declares ranges.

## Getting started in the app

1. Create a character. Its `state_schema` must produce a state with a valid `世界` object — start from `backend/modules/state/examples/basic.py`.
2. Create a writing preset from `backend/modules/presets/examples/google_tool.js`.
3. Create model configs and, in the chat, bind them to `writing`, `state_update`, `round_summary`, `episode_summary`.
4. Generate, confirm, and let the archive finish before the next round.

## Layout

```text
backend/
  api/        HTTP routes          schemas/    request/response contracts
  workflows/  cross-module flows   modules/    business rules per feature
  repository/ DB models & access   llm/        model API adapters
  migrations/ Alembic              tests/
frontend/src/
  api/        typed client         composables/roundFlow.ts  round lifecycle
  views/      pages                components/ panels & editors
  lib/        output parsing, quotes, prefs, fonts
```
