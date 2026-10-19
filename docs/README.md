# LoreNook Documentation

[中文](zh-CN/index.md) | [Project README](../README.md)

English is the primary documentation language. The [Chinese edition](zh-CN/index.md) follows the same subject structure. Current documents describe LoreNook's rules and backend contracts; archived drafts preserve earlier ideas.

## Suggested reading order

1. [Project README](../README.md): setup, migration commands, and API capabilities.
2. [Product design](design/product-design.md): user experience, round lifecycle, and memory rules.
3. [Data model](design/data-model.md): logical entities, fields, and ownership.
4. [Project layout](architecture/project-layout.md): documentation and code directories.
5. [Backend overview](backend/README.md): implementation layers and end-to-end workflows.
6. Read the relevant module reference below for detailed contracts.

The product design describes product behavior and scope. The data model describes logical business data; the data-access reference adds physical database constraints. Module references describe the implemented backend interfaces. The frontend and first personal deployment have been accepted; see the release record for the validation scope.

## Deployment and release

- [Ubuntu deployment and operations](deployment/ubuntu.md): existing Caddy routing, systemd, database migration, updates, backup, and restoration.
- [Milestone 1](releases/milestone-1.md): accepted scope, validation evidence, Python 3.14 compatibility fix, and current boundaries.
- [Frontend implementation](../frontend/README.md): commands, structure, rendering, and browser-local preferences.

## Backend reference

| Document | Subject |
| --- | --- |
| [01 — Data access](backend/01-data-access.md) | Storage, constraints, queries, transactions, and migrations |
| [02 — Characters and chats](backend/02-characters-and-chats.md) | Source resources, copies, chat creation, and configuration |
| [03 — Definition rendering](backend/03-definition-rendering.md) | Entry management, ordering, and Jinja2 templates |
| [04 — Memory assembly](backend/04-memory-assembly.md) | X/Y selection and chronological history representations |
| [05 — Writing presets](backend/05-writing-presets.md) | JavaScript execution, build/parse trials, and request previews |
| [06 — Model calls](backend/06-model-calls.md) | Configuration, parameter merging, Google/DeepSeek adapters, recording, and errors |
| [07 — Writing workflow](backend/07-writing-workflow.md) | Consistent materials, one model call, and an unconfirmed candidate |
| [08 — State updates](backend/08-state-updates.md) | Python/Pydantic Schemas, JSON Patch, and state editing |
| [09 — Round summaries](backend/09-round-summaries.md) | Summarization using the current round's saved state |
| [10 — Episode decisions](backend/10-episode-decisions.md) | Day boundary, candidate selection, and saved ranges |
| [11 — Episode summaries](backend/11-episode-summaries.md) | Selected-range summarization and episode editing |
| [12 — Archiving workflow](backend/12-archiving-workflow.md) | Confirmation, sequential persistence, progress, and recovery |
| [13 — Data management](backend/13-data-management.md) | Full reads, revision checks, atomic changes, and consistency |

## Terminology

| English | Chinese | Meaning |
| --- | --- | --- |
| Chat | 聊天 | One independent conversation |
| User identity | 用户身份 | The user's roleplay persona |
| Definition | 定义 | A character- or identity-owned setting entry |
| Round | 回合 | One user input and approved AI output |
| Round summary | 回合摘要 | Summary of one round |
| Episode | 情节 | Summary of a continuous range of rounds |
| State snapshot | 状态快照 | Complete JSON state at a point in the conversation |
| Writing preset | 写作预设 | JavaScript request and response transformations |
| Archiving | 归档 | Saving confirmed text and completing its derived results |
| First Message | 开场消息 / 第 0 楼 | Separate character opening text |

API identifiers, paths, tags, and executable example keys keep their original spelling. In particular, the built-in day-boundary method reads the Chinese JSON path `世界.日期` (world/date); translating that key would change behavior.

## Historical material

The [initial project outline](archive/initial-project-outline.zh-CN.md) is preserved in its original Chinese with a status notice. It records early ideas, including flows superseded by the current design, and is not a current specification. A full English translation is not maintained for this historical draft.

The [frontend functional brief](archive/frontend-handoff.temporary.md) and [testing handoff](archive/frontend-test-handoff.temporary.md) preserve the implementation-stage requirements and smoke-test checklist. Their pending-work statements are historical; use the current frontend README and milestone record for present status.
