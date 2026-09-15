# Current Work

## Goal

Complete and verify the Vue 3 student-home prototype, frontend review fixes, and uv-based backend dependency migration.

## Completed

- Fixed Grid named-area layout behavior, runtime database restoration, repository ignore rules, dialog focus restoration, documentation placement, anchor scroll spacing, and Vite TypeScript project inputs.
- Moved backend dependency management to `uv`; `pyproject.toml` and `uv.lock` are authoritative.
- Established the agent-facing project memory scaffold under `.agents/memories/`.

## Verified

- `npm run build` passed and generated `frontend/dist`.
- `npx tsc -b --noEmit` passed.
- `uv sync --frozen` completed successfully.
- `uv run --frozen python -m unittest test_app.py` passed 14 tests; the observed AI 401 path is expected by the test.
- Desktop grid geometry, anchor scrolling, dialog focus, and 320px overflow checks passed.
- Last application verification date: 2026-09-09.

## Handoff

- Read `PROJECT_INDEX.md` before starting nontrivial work.
- Read `RUNBOOK.md` before running or validating the application.
- Verify the live branch, worktree, port, and process state before release or handoff.
- Do not treat this snapshot as proof of current runtime state.
