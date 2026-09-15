# Project Index

Updated: 2026-09-12
Project: YueXiang Artisan Training
Status: ACTIVE

## Identity

- Purpose: prototype platform for YueXiang artisan training.
- Architecture: Flask REST API and SQLite backend; Vue 3 + Vite + Pinia frontend; Vercel serverless entry.
- Repository root: the repository containing this `.agents/memories/` directory.
- Current branch: `v2/frontend/lixKRT-rebulid`; verify live Git state before release work.
- Dependency authority: `pyproject.toml` and `uv.lock`; `requirements.txt` is a generated Vercel export.

## Current Focus

- Active milestone: Vue 3 frontend rebuild and prototype review.
- Last completed work: review fixes, uv dependency migration, frontend build, backend tests, and browser geometry validation.
- Current blocker: none recorded.

## Verification

- Backend tests: `uv run --frozen python -m unittest test_app.py`.
- Frontend build/type check: `cd frontend` then `npm run build`.
- Runtime and browser checks: see `RUNBOOK.md`.
- Last application verification: 2026-09-09.
- Memory scaffold migration: 2026-09-12.

## Topic Links

- `NOW.md`: current agent work and handoff state.
- `RUNBOOK.md`: build, run, test, browser, and recovery procedures.
- `DECISIONS.md`: durable implementation decisions.
- `failures/INDEX.md`: project failure cases and blockers.

## Human Documentation

- `docs/PROJECT_INDEX.md`: human-facing project overview.
- `docs/DESIGN.md`: Ark visual and interaction direction.
- `docs/PRODUCT.md`: product goals and prototype scope.
- `README.md`: repository entrypoint and startup guide.

## Open Decisions

- None recorded.
