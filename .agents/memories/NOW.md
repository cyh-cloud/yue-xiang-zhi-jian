# Current Work

## Integration Branch

- 2026-09-18: `v2/lixKRT/dev` fast-forwarded `e527d34 -> 8e27da8`,
  integrating `v2/lixKRT/005-heritage-craft`.
- Feature ancestry on `v2/lixKRT/dev`: 001, 003, 004, and 005 are merged.
- No `002` feature branch exists locally or on the fetched remotes; only
  002 specification/plan commits are present.

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
