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

## AI Companion Jump Target Validation

- AI 学伴 jump_target 校验:空 meta.roles 数组视为无限制,对齐既有 authGuard(roleRoutes)。
## AI Companion Knowledge Provider Ownership

- 012 consumes the 011-owned `assistant_feature_knowledge_provider` contract
  through `app/ai_companion/knowledge_provider.py`, which only imports and
  re-exports the objects owned by `app/admin_console/providers.py`.
- There is no second registry: the setter, the getter,
  `AssistantFeatureKnowledgeProvider` and
  `UnavailableAssistantFeatureKnowledgeProvider` are the same objects, and the
  acceptance suite asserts identity (`is`) for all four.
- A repository-wide AST scan finds exactly one
  `def set_assistant_feature_knowledge_provider` and one
  `def get_assistant_feature_knowledge_provider`, both in
  `app/admin_console/providers.py`.

## Missing 011 Assistant Feature Knowledge Table

- On the `012-ai-companion` branch there is no `CREATE TABLE` for
  `admin_assistant_feature_knowledge` anywhere under `backend/app`.
- `DatabaseAssistantFeatureKnowledgeProvider.list_entries` reads
  `FROM admin_assistant_feature_knowledge`, so the real provider raises
  `sqlite3.OperationalError: no such table: admin_assistant_feature_knowledge`
  on this branch. The acceptance suite asserts this fact instead of creating the
  table or stubbing around it.
- 012 must not create the 011 table and must not register admin routes; that is
  cross-module work owned by 011.
- End-to-end real answering requires, in order: 011 creates the
  `admin_assistant_feature_knowledge` table, then the real
  `DatabaseAssistantFeatureKnowledgeProvider` is registered in the shared
  `assistant_feature_knowledge_provider` slot. Until then 012 keeps the
  `UnavailableAssistantFeatureKnowledgeProvider` placeholder, which surfaces as
  `暂无法回答，请稍后再试` (HTTP 422).

## AI Companion Vendored 011 admin_console Snapshot

- The `012-ai-companion` branch vendors `backend/app/admin_console/` as a
  verbatim snapshot of 011 taken at commit `e5d70f2` (13 files, 4837 lines:
  routes, accounts, dashboard, presets, content_review_provider,
  handcraft_review_adapter, content_review_service, seed, audit, time_utils,
  providers, errors, `__init__`). It satisfies the plan Task 1 hard
  prerequisite (the 011 provider contract) while 011 has not merged into
  `v2/lixKRT/dev`, keeping the two branches independent. This is a conscious
  replacement of the plan Task 16 Step 3 "011 missing -> BLOCKED" branch.
- The snapshot is intentionally larger than the knowledge provider dependency
  (only the four objects re-exported by
  `app/ai_companion/knowledge_provider.py` are used). No minimal slicing was
  performed: the knowledge provider chain in `providers.py` is entangled with
  `presets.py` (`DatabaseAssistantFeatureKnowledgeProvider` is defined in
  `presets.py` and imported by `providers.py`) and the package `__init__.py`
  actively imports presets and routes, so importing the provider loads the
  whole tree; slicing would require refactoring 011-owned code and would widen
  the divergence, making the 011 merge reconciliation harder. A verbatim
  snapshot keeps that merge a path-by-path reconciliation.
- Accepted cost: importing `app.admin_console.providers` transitively loads
  presets, routes and their dependencies (larger runtime import surface), but
  `create_app` registers no admin routes and
  `install_default_ai_companion_services` only fills the
  `assistant_feature_knowledge_provider` slot with the 011 placeholder.
- Constraints: the snapshot files must not be edited on this branch (change 011
  and re-snapshot instead), no admin route may be registered, and no 011 table
  (`admin_assistant_feature_knowledge`) may be created here.
  `backend/tests/test_ai_companion_acceptance.py` guards these as facts.
- Reclaim plan: when 011 merges into `v2/lixKRT/dev`, replace this snapshot
  wholesale with 011's own code during the same merge reconciliation, then
  register the real `DatabaseAssistantFeatureKnowledgeProvider` and mark this
  section reclaimed.
- 2026-09-22: Reclaimed by the 011 merge into `v2/lixKRT/dev`. The snapshot
  was replaced wholesale with 011's own `backend/app/admin_console/` (19
  files), `install_default_admin_services(app)` runs after
  `install_default_ai_companion_services(app)` in `create_app`, so the real
  `DatabaseAssistantFeatureKnowledgeProvider` holds the shared
  `assistant_feature_knowledge_provider` slot, and
  `admin_assistant_feature_knowledge` now ships in `backend/app/db.py`. The
  branch-relative constraints above no longer apply on the integration branch.

## AI Companion Conversation Retention

- 180-day retention is computed from `ai_companion_conversations.updated_at`:
  a conversation whose `updated_at` is older than 180 days is pruned on the next
  write for that user.
- The conversation cap is 100 per user and the message cap is 200 per
  conversation, both enforced inside the same write path.
