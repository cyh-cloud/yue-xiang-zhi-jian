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

## AI Companion Conversation Retention

- 180-day retention is computed from `ai_companion_conversations.updated_at`:
  a conversation whose `updated_at` is older than 180 days is pruned on the next
  write for that user.
- The conversation cap is 100 per user and the message cap is 200 per
  conversation, both enforced inside the same write path.