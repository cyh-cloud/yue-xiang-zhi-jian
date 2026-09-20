# Project Index

Updated: 2026-09-20
Project: YueXiang Artisan Training
Status: ACTIVE

## Identity

- Purpose: prototype platform for YueXiang artisan training.
- Architecture: Flask REST API and SQLite backend; Vue 3 + Vite + Pinia frontend; Vercel serverless entry.
- Repository root: the repository containing this `.agents/memories/` directory.
- Current integration branch: `v2/lixKRT/dev`; 009 merged as `dbeadb2`,
  010 merged as `850b345`, 007 merged through `01b2dfe`, and 006 rebased and
  integrated as `b97a9ef`.
- Dependency authority: `pyproject.toml` and `uv.lock`; `requirements.txt` is a generated Vercel export.

## Current Focus

- Active milestone: 006 local resources, 007 job matching, 009 enterprise
  console, and 010 government console are integrated on `v2/lixKRT/dev`.
- 009 owns the real employment-statistics provider; 010 consumes it through
  `government_employment_statistics_provider`.
- Current blocker: none.

## Verification

- Backend tests: `uv run --directory backend python -m unittest discover -s tests`
  (`941/941` after 006 rebase integration).
- Frontend tests: `cd frontend` then `npm test` (`100` files / `625` tests
  after 006 rebase integration).
- Frontend build/type check: `cd frontend` then `npx tsc -b --noEmit` and `npm run build`.
- Browser acceptance for 006: 8 views x 320/375/1280, 24 screenshots.
- Runtime and browser checks: see `RUNBOOK.md`.
- Last application verification: 2026-09-20.
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
