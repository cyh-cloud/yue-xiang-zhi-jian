# Failure Guardrails

Stable prevention rules derived from verified project failure cases.

## Rules

- Before browser automation, verify the target URL with a lightweight request.
- Keep `--args "--no-sandbox"` on the same agent-browser launch or restart command.
- Do not use `eval --stdin` in this Windows environment; use a short inline expression or Base64 result execution.
- Do not scope accessibility checks to `#app` unless the current page root has been verified.
- After a daemon restart followed by failure, stop repeating the command and inspect session/daemon state.
- After two failed browser attempts, record or update the failure case before one final minimal probe.
