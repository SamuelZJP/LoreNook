# LoreNook Project Layout

[中文](../zh-CN/architecture/project-layout.md) | [Documentation](../README.md)

Updated: 2026-10-19

## 1. Documentation

```text
LoreNook/
├─ README.md                       # English introduction and local setup
├─ AGENTS.md                       # Collaboration instructions
└─ docs/
   ├─ README.md                    # English documentation index
   ├─ design/
   │  ├─ product-design.md         # Product behavior and scope
   │  └─ data-model.md             # Logical business data
   ├─ architecture/
   │  └─ project-layout.md         # This document
   ├─ backend/
   │  ├─ README.md                 # Stack, layers, and workflows
   │  └─ 01-… through 13-…         # Numbered module references
   ├─ zh-CN/
   │  ├─ README.md                 # Chinese project introduction
   │  ├─ index.md                  # Chinese documentation index
   │  ├─ design/
   │  ├─ architecture/
   │  └─ backend/
   └─ archive/
      └─ initial-project-outline.zh-CN.md
```

The [backend index](../backend/README.md) lists every module document. English and Chinese subject documents use matching relative layouts. Historical drafts are linked from the indexes and kept outside the current specification.

## 2. Backend implementation

This describes the current directory responsibilities. Individual files are listed in the relevant module references; the tree is not an exhaustive file inventory.

```text
backend/
├─ main.py                    # Application entry point and lifecycle
├─ config.py                  # Runtime settings
├─ api/                       # HTTP routing, input validation, responses
├─ schemas/                   # API and intermodule data contracts
├─ workflows/                 # Cross-module orchestration
├─ modules/                   # Business rules and services
│  ├─ characters/             # Character resources and copies
│  ├─ users/                  # User identity resources and copies
│  ├─ chats/                  # Chat reads and configuration
│  ├─ definitions/            # Entry management and Jinja2 rendering
│  ├─ memory/                 # X/Y history selection
│  ├─ presets/                # JavaScript presets and QuickJS runtime
│  ├─ models/                 # Model configuration and purpose bindings
│  ├─ state/                  # Schema execution, snapshots, JSON Patch
│  ├─ round_summary/          # Per-round summarization
│  ├─ episode_decision/       # Method dispatch and day-boundary rule
│  ├─ episode_summary/        # Range summarization and episode editing
│  └─ admin/                  # Full data reads and consistency checks
├─ llm/                       # HTTP client, parameters, API adapters, text extraction
├─ repository/                # ORM models, database sessions, queries, archive/admin writes
├─ shared/                    # Content extraction and common errors
├─ migrations/                # Alembic versions and migration environment
└─ tests/                     # Module, API, persistence, and workflow tests
```

The implemented layout groups ordinary queries in `repository/queries.py`, archive persistence in `repository/archive.py`, and data management in `repository/admin.py`. HTTP resources are likewise grouped where appropriate, such as `api/catalog.py` and `api/models.py`. Native adapters reside in `llm/google.py` and `llm/deepseek.py`; `llm/generation.py` shares text request construction across archive generators. This tree does not prescribe a separate adapter directory.

## 3. Request and persistence boundaries

```text
API → Service                         # Reads and edits
API → Workflow → Services             # Chat creation, writing, archiving
Service / Workflow → Repository       # Database operations
Workflow / generation module → LLM    # Model requests
```

The API handles transport. Workflows control sequence and persistence timing. Modules implement business behavior. Repository code performs database operations without committing on its own. Model requests use the LLM layer.

Creating a chat copies resources and generates its initial state in one transaction. Writing reads a consistent snapshot, closes the session, then renders definitions, executes presets, and invokes the model. Archiving saves confirmed text first, then commits each result and step transition together. Network calls do not hold database transactions.

## 4. Runtime data and configuration

- `data/`: default SQLite database location.
- `alembic.ini` and `backend/migrations/`: database migration configuration and versions.
- `pyproject.toml`: package metadata, compatible dependencies, and test settings.
- `requirements-dev.lock`: pinned validation environment.

Virtual environments, caches, generated package metadata, and temporary work are outside the maintained documentation structure. Deployment packaging and the frontend directory layout remain future design work.
