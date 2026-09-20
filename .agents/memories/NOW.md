# Current Work

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
  `v2/lixKRT/007-job-matching`; reviewed baseline HEAD `a76a1db`.
- Verification at `a76a1db`: backend `881/881`, frontend `535/535`,
  TypeScript check and production build passed; Task 18 browser geometry
  passed `18/18` seeded and `15/15` empty-state route/width checks.
- Final whole-branch review found one Critical and five Important findings.
  The single authorized fix wave addressed favorites controls, resume bounds,
  in-flight UI safety, 07 provider error mapping, provider-backed seed reads,
  and the provider-contract/NOW handoff documentation.
- The final fix commit is the current branch tip at handoff; no merge or push
  has been performed.

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
