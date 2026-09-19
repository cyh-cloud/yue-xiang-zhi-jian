# Project Index

Updated: 2026-09-19
Project: YueXiang Artisan Training
Status: ACTIVE

## Identity

- Purpose: prototype platform for YueXiang artisan training.
- Architecture: Flask REST API and SQLite backend; Vue 3 + Vite + Pinia frontend; Vercel serverless entry.
- Repository root: the repository containing this `.agents/memories/` directory.
- Current integration branch: `v2/lixKRT/dev`; 009 merged as `dbeadb2` and
  010 merged as `850b345`; post-merge compatibility fix `a00e061`.
- Dependency authority: `pyproject.toml` and `uv.lock`; `requirements.txt` is a generated Vercel export.

## Current Focus

- Active milestone: 009 enterprise console and 010 government console are
  integrated on `v2/lixKRT/dev`.
- 009 owns the real employment-statistics provider; 010 consumes it through
  `government_employment_statistics_provider`.
- Current blocker: none.

## Verification

- Backend tests: `uv run --directory backend python -m unittest discover -s tests`
  (`644/644` after 009+010 integration).
- Frontend tests: `cd frontend` then `npm test` (`406/406` after integration).
- Frontend build/type check: `cd frontend` then `npx tsc -b --noEmit` and `npm run build`.
- Runtime and browser checks: see `RUNBOOK.md`.
- Last application verification: 2026-09-19.
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
