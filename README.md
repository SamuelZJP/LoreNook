# LoreNook

[中文](docs/zh-CN/README.md) | [Documentation](docs/README.md)

A personal AI roleplaying tool built around chats, layered memory, and programmable writing presets. The backend implements character and chat management, definition rendering, memory assembly, model calls, writing generation, state updates, round summaries, episode decisions and summaries, sequential archiving, and data management. A Vue web frontend covers the chat workflow, resource editors, data management, and preferences.

Milestone 1 is deployed and accepted on Ubuntu 26.04 LTS. See [deployment and operations](docs/deployment/ubuntu.md) for the existing Caddy entry point, systemd services, updates, and backups, and [milestone 1](docs/releases/milestone-1.md) for acceptance results.

## Local development

Python 3.12 or later is required. Run these commands from the project root in PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.venv\Scripts\python.exe -m pip install --no-deps -e .
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Health check: `GET /health`. Interactive API reference: [local Swagger UI](http://127.0.0.1:8000/docs).

The default database is `data/lorenook.db` under the project root. Set `LORENOOK_DATABASE_URL` to use another SQLite location. Relative file paths are always resolved from the project root. Startup does not create tables or run migrations automatically.

```powershell
$env:LORENOOK_DATABASE_URL = 'sqlite:///data/development.db'
.venv\Scripts\python.exe -m alembic upgrade head
```

## Frontend

The web frontend lives in `frontend/` (Vue 3, TypeScript, Vite). With the backend running on port 8000:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. See [frontend/README.md](frontend/README.md) for builds, type generation, and the mock backend.

For reproducible installation from the committed lock file, use `npm ci`. Production serves `frontend/dist/` through Caddy; Vite development and preview servers are local tools.

## Validation and migrations

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m alembic revision --autogenerate -m 'describe change'
```

`requirements-dev.lock` pins the dependency versions used for validation; `pyproject.toml` declares compatible ranges. Revalidate and update the lock file after dependency changes.

## Reading the project

- [Documentation index](docs/README.md): reading order and terminology.
- [Product design](docs/design/product-design.md): scope, lifecycle, memory, and business rules.
- [Data model](docs/design/data-model.md): logical fields and ownership.
- [Project layout](docs/architecture/project-layout.md): directories and responsibilities.
- [Backend overview](docs/backend/README.md): stack, layers, workflows, and module reference.

## API capabilities

All business endpoints use the `/api` prefix. See the linked module documents for request fields, response contracts, and errors.

| Capability | Main paths | Reference |
| --- | --- | --- |
| Source characters and identities | `/characters`, `/user-identities` | [Characters and chats](docs/backend/02-characters-and-chats.md) |
| Chats and independent copies | `/chats`, `/chats/{id}/character`, `/chats/{id}/user-identity` | [Characters and chats](docs/backend/02-characters-and-chats.md) |
| Definition management and rendering | `/definitions` under an owner; `/chats/{id}/definitions/resolve` | [Definition rendering](docs/backend/03-definition-rendering.md) |
| Read-only layered history | `/chats/{id}/memory` | [Memory assembly](docs/backend/04-memory-assembly.md) |
| Preset libraries, build/parse trials, request preview | `/writing-presets`, `/chats/{id}/writing-presets`, `/chats/{id}/writing-preview` | [Writing presets](docs/backend/05-writing-presets.md) |
| Model libraries and direct invocation | `/model-configs`, `/chats/{id}/model-configs`; `/{config_id}/invoke` | [Model calls](docs/backend/06-model-calls.md) |
| Generate or regenerate an unconfirmed reply | `POST /chats/{id}/writing` | [Writing workflow](docs/backend/07-writing-workflow.md) |
| Read/edit latest state; generate a round state | `/chats/{id}/state`, `/chats/{id}/rounds/{round_id}/state-update` | [State updates](docs/backend/08-state-updates.md) |
| Generate, read, and edit round summaries | `/chats/{id}/rounds/{round_id}/round-summary`, `/summary` | [Round summaries](docs/backend/09-round-summaries.md) |
| Decide episode coverage without a model | `/chats/{id}/rounds/{round_id}/episode-decision` | [Episode decisions](docs/backend/10-episode-decisions.md) |
| Generate, read, and edit episodes | `/chats/{id}/rounds/{round_id}/episode-summary`, `/chats/{id}/episodes` | [Episode summaries](docs/backend/11-episode-summaries.md) |
| Confirm, archive, recover, and read rounds | `/chats/{id}/archive`, `/chats/{id}/rounds`, `/chats/{id}/rounds/{round_id}/archive/retry` | [Archiving workflow](docs/backend/12-archiving-workflow.md) |
| Full business-data reads and atomic batches | `/admin/schema`, `/admin/data` | [Data management](docs/backend/13-data-management.md) |

## Editable examples

Character creation and Schema edits must generate initial state with a `世界` object containing valid `日期` (`YYYY-MM-DD`), `星期` (星期一–星期六 or 星期日), `时间` (`HH:mm`), and string `地点` (empty allowed). The default executor rejects empty Schema. All normal state writes check this world contract after Schema correction; administrative state writes check the contract without executing the Schema. Existing states remain readable without migration. A nonempty `state_schema` contains Python/Pydantic source exporting a model named `Schema`; its defaults generate the initial state, and its validators check and correct later states. See `backend/modules/state/examples/basic.py`.

`backend/modules/presets/examples/google_tool.js` is a complete writing preset. Save its contents as a preset's `source`; editable fixed text is grouped in its top-level `fixed` object.

Model calls support `google_generate_content` and `deepseek_chat_completions`. Set `base_url` to the required API root including any version path. Google defaults use `generationConfig`; DeepSeek defaults use native top-level fields such as `temperature`, `max_tokens`, and `thinking`. State updates and both summary purposes may share one DeepSeek configuration. See [model calls](docs/backend/06-model-calls.md).

Select a chat-owned preset and bind a `writing` model before generating. Confirm the accepted candidate through the archive endpoint. Archiving uses the `state_update`, `round_summary`, and, when required, `episode_summary` model bindings. The current round must complete archiving before the next round begins.
