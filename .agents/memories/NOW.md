# Current Work

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

## Verified

- Batch A: backend `344/344`, frontend `244/244`, type-check and production build pass.
- Batch B at `10af068`: frontend `246/246`, type-check and production build pass.
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

- Resume from branch `v2/lixKRT/004-ecommerce-training`, HEAD `10af068`.
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
- Worktree currently has a runtime change in tracked `data/yuexiang.db`.
  Do not commit it. Decide with the user whether to restore it from HEAD or
  archive it before handoff.
