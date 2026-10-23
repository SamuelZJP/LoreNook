# Agent notes

- Personal project, single `main` branch. Commit directly to `main`.
- Keep communication and docs short and direct. No defensive caveats or repeated disclaimers.
- Write docs and code comments in English. User-facing UI text, prompts and the `世界` state keys stay Chinese.
- Docs are minimal: `README.md`, `docs/design.md`, `docs/deployment.md`. The code is the reference for implementation details. Update `design.md` only when a concept or rule changes, and only once a discussion has reached a conclusion.
- Run `.venv/bin/python -m pytest -q` after backend changes and `npm run typecheck` in `frontend/` after frontend changes.
