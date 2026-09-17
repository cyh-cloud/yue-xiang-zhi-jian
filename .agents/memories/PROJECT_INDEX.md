# Project Index

Updated: 2026-09-17
Project: YueXiang Artisan Training
Status: ACTIVE

## Identity

- Purpose: prototype platform for YueXiang artisan training.
- Architecture: Flask REST API and SQLite backend; Vue 3 + Vite + Pinia frontend; Vercel serverless entry.
- Repository root: the repository containing this `.agents/memories/` directory.
- Current integration branch: `v2/lixKRT/dev`; latest 004 merge `bc58a2a`.
  Feature source head: `10af068`.
- Dependency authority: `pyproject.toml` and `uv.lock`; `requirements.txt` is a generated Vercel export.

## Current Focus

- Active milestone: post-review repair for `004-ecommerce-training`.
- Last completed work: Tasks 10-17 and final branch review (`31821dc`);
  post-review Batch A and Batch B repairs through `10af068`; memory handoff
  `f0b00e7`; integration merge `bc58a2a`.
- Current blocker: Batch B round 4 cannot start because the mandated
  `基元律动/glm-5.3` provider returned HTTP 402 (`余额不足`). See
  `failures/INDEX.md`.

## Verification

- Backend tests: `uv run --directory backend python -m unittest discover -s tests -v` (`344/344` at Batch A).
- Frontend tests: `cd frontend` then `npm test` (`246/246` at `10af068`).
- Frontend build/type check: `cd frontend` then `npx tsc -b --noEmit` and `npm run build`.
- Runtime and browser checks: see `RUNBOOK.md`.
- Last application verification: 2026-09-17.
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
