# Memory Boundaries

## Project Memory

Use `.agents/memories/` for agent-facing project context, routing, decisions, risks, runbooks, failures, and handoff state.

## Human Documentation

Use `docs/` for documentation intended for people: architecture explanations, usage guides, operational documentation, and reviewed summaries.

## Global Memory

Use the global memory only for cross-project or cross-tool lessons, reusable workflow rules, templates, people context, and project summaries.

## Promotion Rules

- Keep project-specific failures in the project failure index.
- Promote a lesson globally only after it repeats across projects or is clearly toolchain-level.
- Keep the detailed project evidence local and put only the generalized rule or summary in global memory.
- Do not create duplicate authority. Link to the authoritative record instead.

## Privacy

- Do not store secrets, tokens, private user paths, customer data, or full logs.
- Sanitize a shared lesson before adding it to global memory.
