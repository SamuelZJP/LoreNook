# Milestone 1: Personal Deployment

[中文](../zh-CN/releases/milestone-1.md) | [Documentation](../README.md)

Completed: 2026-10-20. Code baseline: `7317344` (`Add floor display limit, collapsed summaries, and reading font settings`), before this documentation cleanup. This records acceptance and does not imply that a Git tag was created.

## Delivered scope

The backend implements characters and identities, independent chat copies, definitions, layered memory, writing presets, model calls, writing, state updates, round summaries, episode decisions and summaries, sequential archiving/recovery, and data management. The Vue frontend provides chats, resource editors, state and memory panels, data management, and browser-local display preferences.

The owner accepted the first milestone as working correctly. Production uses Ubuntu 26.04 LTS, systemd, the existing Caddy/Authelia/frp entry point, and SQLite. See [deployment and operations](../deployment/ubuntu.md).

## Validation record

- Windows review: 666 backend tests passed; frontend type checking and production build passed.
- Initial Ubuntu Python 3.14 run: 664 passed and 2 failed because ISO time parsing began accepting `24:00`. Explicit hour/minute validation now retains the `00:00–23:59` contract. All 45 related Windows tests passed; the owner confirmed successful validation after synchronizing the fix on Ubuntu.
- The Windows database was migrated to Ubuntu and existing chats were accessible.
- The owner confirmed backend startup, LAN Caddy Host routing, HTTPS hostname/authentication, and access from LAN and mobile data.
- The owner confirmed generation, confirmation/archive, state and summaries, detail-page refresh, persistence after restart, and boot enablement.
- Same-machine consistent backup, restoration to an independent file, and migration revision checks passed. Daily backup at 03:00 Asia/Shanghai was configured and tested, with 30-day automatic-backup retention.

Earlier mock-backed browser smoke checks remain in the [archived frontend testing handoff](../archive/frontend-test-handoff.temporary.md). No automated frontend test framework was added; milestone acceptance does not assert that every item in that historical checklist was individually rerun.

## Current boundaries

- Unconfirmed candidates exist only in browser memory. Candidate restoration, streaming, multi-user accounts, avatar upload, image generation, and speech generation are outside this release.
- Authentication belongs to the external entry point. Access is for trusted users; state Schemas execute Python.
- LAN access uses the public hostname and existing cloud tunnel, without an independent offline access path.
- Backups remain on the production machine. Off-machine backups were explicitly deferred.
- Deployment needs no additional schema migration. The Python 3.14 fix is included in the code baseline.
