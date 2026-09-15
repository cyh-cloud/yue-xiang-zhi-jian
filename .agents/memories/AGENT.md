# Project Memory Router

Template version: 2026-09-11
Project: YueXiang Artisan Training

This file routes an agent to project memory. It is not the project root `AGENTS.md`.

## Read Triggers

| Situation | Read |
|---|---|
| Nontrivial task | `PROJECT_INDEX.md` |
| Current implementation work | `NOW.md` |
| Runtime, verification, or recovery | `RUNBOOK.md` |
| Design or architecture conflict | `DECISIONS.md` and relevant source |
| Same approach failed twice | `failures/INDEX.md`; create/update case before probing |
| Matching failure exists | matching case and `failures/GUARDRAILS.md` |
| Create or update memory | this file, then the relevant guide or template |
| Project handoff or audit | this file, `PROJECT_INDEX.md`, and `NOW.md` |

## File Index

- `PROJECT_INDEX.md`: project identity, current milestone, verification summary, and topic links.
- `NOW.md`: agent-facing current work and handoff state.
- `RUNBOOK.md`: build, run, test, browser, and recovery commands.
- `DECISIONS.md`: durable implementation and design decisions.
- `failures/INDEX.md`: project failure case index.
- `failures/GUARDRAILS.md`: stable prevention rules.
- `guides/failure-protocol.md`: failure capture, lifecycle, and minimal-probe protocol.
- `guides/memory-boundaries.md`: project, global, and human-document boundaries.
- `templates/failure-case.md`: reusable failure case format.
- `history/`: archived legacy memory and completed historical records.

## Hard Rules

- Do not load the whole memory tree by default.
- Do not use `docs/` as the agent routing authority; it is human-facing documentation.
- Do not store secrets, full logs, runtime databases, or raw private data.
- After two failed attempts in the same direction, stop and use failure routing.
- Create or update the matching failure case before running the next probe.
- An unresolved case permits only one minimal probe before re-evaluation.
- Keep this file within 80 lines; move detail into `guides/` when it grows.
