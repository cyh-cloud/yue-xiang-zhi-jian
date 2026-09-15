# Failure Protocol

Use this protocol after a qualifying failure or when maintaining failure memory.

## Capture Triggers

- The same command, hypothesis, or repair direction fails twice.
- The user says the result is still wrong or asks the agent to stop.
- The agent is about to repeat a previously failed direction.
- A verification passes while the observed behavior remains broken.
- A failure caused material time loss or repeated invalid output.

## Case Lifecycle

- Before creating a new case, search the index by symptom, tool, error signature, and keywords.
- Use a stable case ID in the form `<scope>-YYYYMMDD-short-slug`.
- If the same root cause already exists, update or reopen the existing case instead of creating a duplicate.
- Merge duplicate cases and record the duplicate IDs or aliases in the retained case.
- Reopen a `FIXED` case under its original ID when the same root cause returns.
- Review `OPEN` and `BLOCKED` cases at the next relevant task and during periodic memory maintenance.
- Mark a case `OBSOLETE` only when the environment or code change makes reproduction impossible or irrelevant.
- Preserve the original evidence and resolution when marking a case obsolete.
- Update the index status, case path, and last reviewed date whenever a case changes.

## Status

- `OPEN`: unresolved and eligible for one minimal probe.
- `BLOCKED`: requires user input, permissions, external state, or new evidence.
- `FIXED`: solved and verified.
- `MITIGATED`: workaround exists but root cause remains.
- `OBSOLETE`: environment or code changed so the case no longer applies.

## Required Record

- Case ID: stable identifier used by the index.
- Facts: expected result, observed result, exact evidence, relevant environment.
- Attempts: what was tried and what each attempt proved or disproved.
- Diagnosis: separate facts, hypotheses, and confirmed root cause.
- Resolution: fix, verification, and confidence.
- Guardrail: a short prevention rule.
- For `OPEN`: `Next probe`, `Forbidden`, and `Stop condition`.

## Minimal Probe

- Change one variable only.
- Be reversible and small in scope.
- Define the expected signal before running it.
- Do not repeat the same failed repair direction.
- If it fails without new evidence, stop and mark the case blocked.

## Completion

- Mark `FIXED` only after verification passes.
- Update the failure index with the new status and case path.
- Update GUARDRAILS.md for repeatable prevention.
- If the lesson is cross-project, create a sanitized global case.
- Reopen the case if the same root cause returns.
