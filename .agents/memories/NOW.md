# Current Work

## 006 Local Resources

- 2026-09-20: Final whole-branch review passed on the 基元律动 channel after
  one fix wave for ASR failure semantics, category validation, provider error
  mapping, request ordering, subscription feedback, and TTS timeout handling.
- Rebased `v2/lixKRT/006-local-resources` onto `v2/lixKRT/dev` at `c0cbddc`
  and fast-forwarded the integration branch to rebased feature tip `b97a9ef`.
- Rebased verification: backend `941/941`, frontend `100` files / `625` tests,
  TypeScript check and production build passed. The browser acceptance set
  contains 24 screenshots across 8 views and 320/375/1280.
- Rebase resolution preserved both the merged 007 job-matching routes/wiring
  and the new 006 routes, providers, and portal entry.
- Deferred minor: rapid category switching can still clear a newer view-level
  error notice through an older promise; data selection remains correct.
- The 006 worktree and branch are retained. No push or branch/worktree cleanup
  has been performed.

## 007 Job Matching Specification and Plan

- 2026-09-19: Specification frozen at
  `specs/007-job-matching/spec.md`; feature pointer now resolves to
  `specs/007-job-matching`.
- Branch and worktree: `v2/lixKRT/007-job-matching` in
  `.worktrees/007-job-matching`.
- Implementation plan:
  `.agents/memories/plans/2026-09-19-007-job-matching.md`.
- Frozen contracts: 07 owns skill-profile aggregation, per-item visibility,
  and submission snapshots; 03/04/05 remain outcome producers. The existing
  09 `JobPositionProvider` and `JobApplicationIntakeProvider` are reused
  unchanged. A new 09-owned `JobApplicationStatusProvider` supplies
  student-side application reads.
- Clarified decisions: resume snapshots freeze on successful submission;
  AI adoption is explicit and atomic; closed handled applications retain the
  latest manual status plus a closed marker; favorites retain a full display
  snapshot until manual removal.
- Independent plan review passed with no remaining High or Medium findings.
- Implementation Tasks 1-18 completed on
  `v2/lixKRT/007-job-matching`; final feature tip `1bdd893`.
- Verification before merge: backend `885/885`, frontend `542/542`,
  TypeScript check and production build passed; browser interaction and
  geometry covered favorites add/cancel plus the affected views.
- Final whole-branch review found one Critical and five Important findings.
  The single authorized fix wave addressed favorites controls, resume bounds,
  in-flight UI safety, 07 provider error mapping, provider-backed seed reads,
  and the provider-contract/NOW handoff documentation.
- The scoped re-review passed with all six findings addressed.
- 2026-09-20: 007 was merged into `v2/lixKRT/dev`; merge commits `4e1bbd6`
  and `01b2dfe` include a CRLF-compatible test fix from `1bdd893`.
- Merged-result verification: backend `885/885`, frontend `542/542`,
  TypeScript check and production build passed.
- The feature worktree and branch are retained. No push has been performed.

## 009 Enterprise Console

- 2026-09-19: Feature source `0f5950c` merged into `v2/lixKRT/dev` as
  `dbeadb2` before 010.
- `backend/app/enterprise_console/providers.py` now owns
  `DatabaseEmploymentStatisticsProvider` for all-platform active-job and
  cumulative-application counts.
- The provider uses the shared extension key
  `government_employment_statistics_provider`; 010 consumes that existing slot
  instead of creating a second registry.
- Enterprise jobs, applications, notifications, review facade, provider
  contracts, frontend routes, and browser-responsive tests are integrated on
  `v2/lixKRT/dev`.

## 010 Government Console Specification and Plan

- 2026-09-18: Created branch `v2/lixKRT/010-government-console` in
  `.worktrees/010-government-console`, based on `v2/lixKRT/dev` at `01fff52`.
- Specification: `specs/010-government-console/spec.md`.
- Implementation plan:
  `.agents/memories/plans/2026-09-18-010-government-console.md`.
- Clarified policy three-state/news two-state behavior, immediate 02 policy
  push, no re-push on re-list, hard delete, idempotent view events, and
  non-deduplicated cumulative application counts.
- Frozen 09 employment placeholder as unavailable `None` values with
  `set_employment_statistics_provider` as the replacement point.
- Frozen 06 policy/news producer registration and read/view contract; 06
  remains the final signature owner.
- User confirmed all four recommended decisions on 2026-09-18: strong
  consistency between policy publication and 02 push, no re-push on re-list,
  no published-content editing in this release, and repeated views counted per
  distinct view event.
- 2026-09-19: SDD Tasks 1-13 completed in the adjusted order
  `1,2,3,4,5,7,8,9,10,6,11,12,13`; final code head `8815045`.
- Verification: backend `557/557`, frontend `355/355`, TypeScript build,
  production build, and browser geometry `12/12` page/width combinations
  passed. The browser pass fixed one 320px policy-copy wrapping defect.
- Final whole-branch review found one Important FR-052 database-error mapping
  issue; it was fixed in `8815045` and the scoped re-review passed.
- Deferred non-blocking items remain for later hardening: management-route
  SQLite error mapping, explicit retry-after-hidden and validator-negative
  tests, duplicated time helper, partial-09-provider edge handling, and
  duplicated portal hrefs.
- 009 is merged first so the 010 dashboard consumes the real
  `EmploymentStatisticsProvider`; the post-merge dashboard integration check is
  part of the 010 merge verification.
- 2026-09-19: 010 source `4045c41` merged as `850b345`; compatibility test
  isolation committed as `a00e061`.
- Post-merge verification: backend `644/644`, frontend `406/406`, TypeScript
  check and production build passed; 009 targeted `83/83` and 010 targeted
  `54/54` passed.
- Real application dashboard check returned
  `{"active_job_count":1,"cumulative_application_count":5,"available":true}`
  after government login, confirming the 009 provider is registered in the
  shared extension slot.
## 008 Teacher Console Task 19

- Worktree: `.worktrees/008-teacher-console` on
  `v2/lixKRT/008-teacher-console`, base `6b97652`.
- Task commits 1-18: `c116d3e`, `f571467`, `b5ca1d0`, `bb327a4`,
  `b3a0b85`, `2041cf8`, `e9c78c4`, `ce6c01a`, `d1a953e`, `a5e5e77`,
  `e08dba6`, `867dc43`, `87e52a1`, `65eef00`, `35fc277`, `cb34e1f`,
  `5839d77`, `e1276a9`, `6b97652`.
- Task 19 commits: `75f2dcc` for acceptance tests and `75075c6` for the
  provider-authoritative teacher course read fix.
- Review status: Tasks 1-18 are complete with clean task review at `6b97652`.
  Task 19 is the cross-module acceptance/regression task and does not perform
  the final whole-branch review.
- Verified commands:
  - `uv run --directory backend python -m unittest discover -s tests -v`:
    `613` tests ran, `613` passed.
  - `cd frontend && npm test`: `69` files and `365` tests passed.
  - `cd frontend && npx tsc -b --noEmit`: passed with no output.
  - `cd frontend && npm run build`: passed; `1761` modules transformed.
  - Browser geometry at `320`, `375`, and `1280` for the teacher shell,
    course editor, quiz editor, announcement view, comment view, and
    dashboard: `clientWidth == scrollWidth`, no horizontal overflow.
- Provider replacement status: the replacement `ContentReviewProvider`
  acceptance test passes through `set_content_review_provider` and
  `CourseReviewAdapter` without consumer changes.
- Resolved provider-authority defect: `get_teacher_course()` now reads
  `review_status`, rejection opinion, and review update time from the
  `ContentReviewProvider`; the exact Task 19 acceptance assertion passes.
  Internal mutation paths intentionally continue to use local state.
- Browser screenshots are stored under
  `.superpowers/sdd/2026-09-18-008-teacher-console/task-19-screenshots/`.
  Visual content is `待人工复核` because image inspection was not delegated.
- Task 19 report:
  `.superpowers/sdd/2026-09-18-008-teacher-console/task-19-report.md`.
## Integration Branch

- 2026-09-18: `v2/lixKRT/dev` fast-forwarded `e527d34 -> 8e27da8`,
  integrating `v2/lixKRT/005-heritage-craft`.
- Feature ancestry on `v2/lixKRT/dev`: 001, 003, 004, and 005 are merged.
- No `002` feature branch exists locally or on the fetched remotes; only
  002 specification/plan commits are present.

## 005 Role and Points Revision

- 2026-09-18: `v2/lixKRT/dev` fast-forwarded `c8ecf0d -> 633b456`,
  integrating `v2/lixKRT/005-fix-role-points`.
- Project-defined weak convergence ran against
  `specs/005-heritage-craft/spec.md`; zero actionable gaps were found.
  No `tasks.md` authority was created, per project routing.
- Independent review and scoped re-review approved the revision. Final
  backend regression passed `507/507`.
- No push was performed.

## 005 Task 20 Browser Acceptance

- Completed on 2026-09-18 in `.worktrees/005-heritage-craft`.
- DOM geometry at 320, 375, and 1280 reported no horizontal overflow on the
  handcraft home, craft/AR, points, or rewards flows.
- The exact `AI 服务暂时不可用` copy remained visible after resizing, and the
  points/redemption/cancellation flow preserved balance, stock, status, and
  reward availability.
- Residual visual risk: none found in the Task 20 browser pass.

## Goal

Finish the post-review repair set for `004-ecommerce-training` after the feature's
whole-branch review.

## Completed

- Tasks 10-17 are complete and the whole-branch review approved commit `31821dc`.
- Batch A completed: SQLite-safe simulation writes, course-store request epochs,
  precise course/quiz DTOs, unified busy UI, and test-name correction.
  Commits: `a064b50`, `08a26c3`.
- Batch B partially completed: quiz disabled contrast, retake state/focus, mobile
  navigation affordances, CJK layout improvements, and mobile empty-state wording.
  Commits: `dcbfa24`, `92900e7`, `f04403e`, `10af068`.
- Memory handoff committed as `f0b00e7`.
- Feature branch merged into `v2/lixKRT/dev` with merge commit `bc58a2a`.

## Verified

- Batch A: backend `344/344`, frontend `244/244`, type-check and production build pass.
- Batch B at `10af068`: frontend `246/246`, type-check and production build pass.
- Integration branch `v2/lixKRT/dev` at `bc58a2a`: backend `344/344`,
  frontend `246/246`, type-check and production build pass.
- Browser checks at 320/375/1280 show no horizontal overflow or active-tab clipping.
- Image-understanding review closed most visual items; remaining CJK details are listed below.

## Blocked

- Batch B round 4/5 required the model-ladder upgrade to
  `基元律动/glm-5.3`, effort high. The subagent could not start because the
  CC Switch local proxy returned HTTP 402 (`余额不足`).
- Do not downgrade the mandated round-4 model or repeatedly retry while the
  provider balance remains unavailable. See
  `failures/cases/2026-09-17-glm-balance-402.md`.

## Handoff

- The integrated feature is on `v2/lixKRT/dev`. Continue the next repair from the
  feature source commit `10af068` or a fresh worktree based on the integration branch.
- Required next repair is structural CJK wrapping in Batch B:
  - home-1280 still has a 2-character `获得` orphan and mid-word splits in
    `参考`, `分析`, and `记录`;
  - simulation-375 empty state still leaves `练。` alone and its hero splits
    `文字`;
  - copy-training-320 still leaves `异。` alone.
- Correct the layout/copy structurally, then rerun code review and
  image-understanding review.
- Batch C is not started: use a controlled AI stub in an isolated environment
  to capture browser failure evidence for AI-04, AI-05, AI-06, AI-09, AI-10,
  and AI-11.
- The browser-acceptance database was archived and the tracked database was
  restored to HEAD. Archive:
  `E:\Project\skipped_work\粤乡智匠项目\.superpowers\archive\runtime-data\yuexiang-004-batch-b-stop-20260917-124139.db`;
  SHA-256 `F384F4C1F200499CFE87EE6F09DCEB26C9324E5ED6FF27878C55E51A0C09DBE1`.
- Both the feature worktree and integration worktree are clean.
## 012 AI Companion

- 2026-09-21: SDD Tasks 1-16 complete on branch `v2/lixKRT/012-ai-companion` in
  `.worktrees/012-ai-companion`. Commit sequence on top of the Task 1-13 head
  `aa3118e`: Task 14 `22bfebf`, Task 15 `33031ac`, Task 16 acceptance
  (`test(ai-companion): 全 feature 验收、provider 对账与记忆交接`), then two
  deepseek-flash review-hardening commits (`test(ai-companion): 权限拒绝零调用断言改为按
  URL 扫描`, `test(ai-companion): 响应式断言剥离 CSS 注释以消除误报`). Branch tip is the
  latest hardening commit (read with `git rev-parse HEAD`). A subsequent
  strictly-scoped `基元律动/deepseek-flash` review of Tasks 1-13 found 1 in-scope
  issue (Task 13: reopening the panel while parked on the history tab did not
  reload history, contradicting the plan criterion) fixed by
  `fix(ai-companion): 重开面板停留在历史 tab 时从服务端重载历史`; the other 12 tasks were
  APPROVE with zero findings.
  Stopped before merge: no push, no merge into `v2/lixKRT/dev`; worktree and
  branch retained.
- Verification: backend acceptance `20/20`; backend full suite `1018/1018`;
  frontend whole-feature `12/12`; frontend full `110` files / `736` tests
  (includes the Task 13 reopen-reload regression test);
  `npx vue-tsc --noEmit` silent; `npm run build` succeeded.
- 2026-09-22: Browser acceptance (Task 15 Step 4) COMPLETED. Ports 5000/5173
  verified free before start; real app (uv run --directory backend python run.py
  + npm run dev) run in the worktree with a scratch DB outside git;
  worktree-scoped agent-browser session; student login. Geometry at
  320/375/1280: no horizontal overflow (scrollWidth == viewport), launcher
  inset 16px (mobile) / 24px (desktop), no overlap with header/primary
  submit/bottom actions, panel opens/scrolls/composer visible/Escape closes
  with focus return. Screenshots under
  .superpowers/sdd/2026-09-20-012-ai-companion/task-15-screenshots/
  (gitignored). Image inspection delegated to the 图片理解 subagent
  (step-3.7-flash, high). The pass surfaced one 320px composer-overflow defect
  (submit button pushed past the viewport edge), fixed the same day; see the
  2026-09-22 final-review entry below.
- Provider reconciliation: 012 consumes the 011-owned
  `assistant_feature_knowledge_provider` contract by re-export only, asserted by
  object identity for the setter, the getter and both provider classes. Exactly
  one definition of each contract function exists, in
  `app/admin_console/providers.py`.
- The `admin_assistant_feature_knowledge` table is MISSING on this branch: no
  `CREATE TABLE` for it exists under `backend/app`, so the real
  `DatabaseAssistantFeatureKnowledgeProvider` raises
  `no such table: admin_assistant_feature_knowledge`. 012 must not add the 011
  table.
- Deferred items (not fixed): business-proxy prefilter misjudging
  "帮忙…怎么…" style questions (fail-safe direction);
  `app/ai_companion/__init__.py` not re-exporting `AI_UNAVAILABLE_MESSAGE` and
  `ASR_FAILURE_MESSAGE`; the 7-field knowledge whitelist test needing hardening;
  180-day retention computed by `updated_at`; 011 real-provider assembly order.
- 2026-09-22: Final whole-branch review over 1a62cf9..2d7c376 (36 commits,
  independent read-only reviewer, step-5-preview high): no Critical; Important
  I-1 (vendored 011 admin_console snapshot broader than the provider dependency
  and unregistered as a decision) and Minor M-1 (.specify/feature.json pointer)
  / M-2 (retention exact-threshold cases missing; registered, not fixed). Fix
  wave by an independent implementer: 2081b8a
  fix(ai-companion): 修复 320px 视口下对话面板 composer 溢出面板与视口
  and 467d488
  docs(ai-companion): 登记 011 admin_console 快照策略并补无管理路由守卫.
  Scoped re-review: both ADDRESSED, no new breakage. Post-fix verification:
  backend full 1019/1019, frontend full 110 files / 737 tests, vue-tsc silent,
  build success. DECISIONS.md now carries "AI Companion Vendored 011
  admin_console Snapshot" with the reclaim plan at 011 merge. v2/lixKRT/dev
  fast-forwarded to the 012 tip afterwards; the merged result was re-verified
  with the full suites.
- The 012 worktree and branch are retained. No push and no worktree cleanup
  has been performed; the only merge was the authorized fast-forward of
  v2/lixKRT/dev onto the 012 branch tip.
