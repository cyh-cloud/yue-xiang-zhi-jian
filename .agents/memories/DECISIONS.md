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

## Producer Provider Contracts

- Cross-feature producer provider shapes, registration, review state contracts,
  errors, alignment rules, and consumer ownership are frozen in
  `.agents/memories/guides/provider-contract.md`.

## Employment Statistics Provider

- 009 owns `DatabaseEmploymentStatisticsProvider`, which returns all-platform
  active-job and cumulative-application counts.
- The provider is registered under the existing extension key
  `government_employment_statistics_provider`.
- 010 consumes that slot without direct job/application table access or a
  second registry.

## 011 Admin Console Provider Decisions

- 011 owns eight provider slots and installs them last in `create_app`, after
  every consumer default and before `register_messaging_source_provider`.
- Slot replacement is unconditional for `agri_preset_provider`,
  `handcraft_craft_preset_provider`, `local_resource_case_provider`, and
  `handcraft_reward_catalog_provider`: 03/05/06 install their own defaults
  earlier, so a "not in app.extensions" guard would silently keep the
  consumer placeholder and 011 would never take effect.
- `content_review_provider` is replaced only when the installed slot is absent
  or is the `UnavailableContentReviewProvider` placeholder; a non-placeholder
  provider installed by a test or a later feature is left alone.
- `knowledge` and `feedback_intake` slots are replaced unconditionally; the
  "pre-installed sentinel is replaced" behavior is pinned by tests so a future
  guard regression fails loudly.
- One `DatabasePointsPolicyProvider` instance fans out to both
  `handcraft_points_policy_provider` (05 read slot) and
  `admin_points_policy_provider` (011 management read slot).
- `configure_admin_providers()` only delegates to the unique per-slot setters;
  a `None` parameter leaves the installed default in place, so a later feature
  can override one slot after `create_app`.
- Ordinary-admin content dashboard metrics are an exact ten-key contract and
  the forbidden-key exclusion is recursive over the full JSON response; the
  implemented forbidden set is the union of spec FR-102 and the 010 historical
  exclusion list (16 keys).
- Cross-console rejection semantics stay as implemented (401 for
  `abort_session_required` on 03/05/08/09, 403 for 06/011); unifying them
  would touch three consumer write sets and is deferred.
