# Durable Decisions

## Frontend and Backend Boundary

- The current frontend is Vue 3 + Vite + Pinia.
- Flask owns REST API and SQLite access.
- The frontend uses an internal API adapter rather than coupling directly to backend implementation details.

## Dependency Management

- `pyproject.toml` and `uv.lock` are authoritative.
- `requirements.txt` is generated only for Vercel compatibility.

## Integration Branch

- `v2/lixKRT/dev` is the long-lived integration branch.
- Feature and maintenance branches merge into `v2/lixKRT/dev` before release work.

## Visual Direction

- Use Ark `family=ark` and `depth=maximal`.
- Use light page and surface colors with dark readable text as the primary palette.
- Preserve accent, success, warning, and error color differentiation.
- Human-facing design details remain in `docs/DESIGN.md`.

## Grid Layout

- Components using CSS Grid named areas must bind each child explicitly with `grid-area`.
- Do not rely on source order for named-area placement; partial `grid-column` or `grid-row` rules can override named areas.

## Dialog Focus

- Switching login/register modes with `v-if`/`v-else` unmounts and recreates the form.
- Re-focus the first control after mode changes and restore the trigger focus on close.

## TypeScript Verification

- `frontend/tsconfig.node.json` may reference only files that actually exist.
- `npx tsc -b` and `npm run build` have different validation scopes; run both for frontend changes.
