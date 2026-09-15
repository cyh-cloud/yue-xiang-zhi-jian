# Windows Agent-Browser Verification Loop

- Case ID: yuexiang-20260909-agent-browser-windows
- Date: 2026-09-09
- Status: FIXED
- Scope: project
- Keywords: agent-browser, Chrome, daemon, no-sandbox, eval, a11y, Windows
- Owner: YueXiang project
- Template version: 2026-09-11

## Scene

- Project or path: repository root containing this `.agents/memories/` directory
- Branch or commit: frontend rebuild branch; exact commit was not captured in the source note.
- OS and shell: Windows with PowerShell.
- Relevant versions: agent-browser and Chrome versions were not captured.
- Relevant configuration: `scripts/vite.mjs` selects the preview URL; Windows headless Chrome requires launch arguments.

## Expectation and Evidence

- Expected: browser checks open the live preview, inspect DOM geometry, and complete without repeated daemon restarts.
- Observed: daemon restarts and launch failures occurred without the required launch arguments; `eval --stdin` was unstable; one accessibility audit was incorrectly scoped to `#app`.
- Reproduction: see the related global case `global-20260909-agent-browser-loop` and its sanitized evidence.
- Evidence: the project verification record documents successful checks only after applying URL probing, launch flags, short evaluation, and confirmed page-root behavior.

## Attempts

- Attempt 1: Ran browser commands without consistent launch configuration and sometimes used the wrong page-root assumption.
- Attempt 2: Probed the URL, kept `--no-sandbox` on the launching invocation, avoided `eval --stdin`, and verified the page root before scoped checks.

## Diagnosis

- Facts: the frontend preview URL and browser launch state are both live dependencies.
- Hypotheses: the apparent browser loop combined environment, command, and selector failures.
- Root cause: retries did not isolate URL state, launch configuration, browser process state, and selector scope.

## Resolution

- Fix or workaround: use the verified launch pattern and browser-check procedure in `RUNBOOK.md`.
- Verification: the documented build, geometry, focus, anchor, and overflow checks passed under the corrected procedure.
- Confidence: high for this Windows environment and frontend workflow.

## Prevention

- Guardrail: follow `failures/GUARDRAILS.md`.
- Forbidden: do not repeat the same browser command after a daemon restart and long failure without new evidence.
- Next probe: check the target URL and browser session state before reopening with launch arguments.
- Stop condition: after two failures, record or update this case and ask the user if the next minimal probe still fails without new evidence.

## Review

- Last reviewed: 2026-09-12
- Review interval: review when agent-browser, Chrome, or the preview script changes.
- Reopen count: 0
- Supersedes or duplicates: related to global case `global-20260909-agent-browser-loop`; this case retains project-specific evidence.
- Expiry or obsolescence condition: superseded when the browser toolchain or preview workflow no longer exhibits these failure modes.
