# Runbook

## Backend

- Install or synchronize dependencies: `uv sync --frozen`.
- Start locally: `uv run --frozen python run.py`.
- Default backend URL: `http://127.0.0.1:5000`.
- Run tests: `uv run --frozen python -m unittest test_app.py`.

## Frontend

- Install dependencies: `cd frontend` then `npm install`.
- Build and type-check: `cd frontend` then `npm run build`.
- Preview through the repository script: `npm run preview`.
- The preview script uses `http://127.0.0.1:4173`; its `--port` argument may not be honored.

## Browser Verification

- Probe the target URL with a lightweight request before launching a browser.
- On Windows/headless Chrome, keep `--args "--no-sandbox"` on the same `agent-browser` invocation that launches or restarts the browser.
- Avoid `eval --stdin` in this environment; use a short inline expression or Base64 result execution.
- Confirm the actual page root before using a selector such as `#app`.
- Prefer snapshot, short eval, and DOM geometry checks over speculative selectors.
- After a daemon restart followed by failure, stop and inspect session state before another attempt.

## Worktree Boundaries

- Do not commit runtime database changes, uploads, `.venv`, caches, IDE state, or build artifacts.
- Treat commit, push, cleanup, restore, and deletion as separate authorizations.
