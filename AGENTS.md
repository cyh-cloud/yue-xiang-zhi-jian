# Repository Guidelines

## Project Memory

Project-specific durable memory lives in `.agents/memories/AGENTS.md`. Read it after this file for cross-session handoff, layered context, verification boundaries, and worktree routing.

## Project Structure & Module Organization

This is a Flask web application for the YueXiang artisan training platform. `app.py` contains the Flask app and REST API handlers; `database.py` initializes and accesses the SQLite database; `run.py` is the local launcher. Backend virtual environments and dependencies are managed with `uv`; `pyproject.toml` and `uv.lock` are authoritative, while `requirements.txt` is a generated Vercel compatibility export.

The current Vue 3 frontend lives in `frontend/`; legacy frontend pages remain at the repository root (`index.html`, `admin.html`, `teacher.html`, `enterprise.html`, `government.html`, and `case-detail.html`), with styles and behavior in `styles.css`, `script.js`, `portal.css`, `portal.js`, and `js/core.js`. Runtime SQLite data belongs under `data/`; uploaded files belong under `uploads/`. Product requirements and notes are in `docs/`. The root `README.md` is the repository entrypoint; store all other project documentation files under `docs/` and do not add new documentation files at the repository root. The Vercel serverless entry point is `api/index.py`.

## Build, Test, and Development Commands

- `uv sync --frozen`: create `.venv` and install locked backend dependencies.
- `uv run --frozen python run.py`: initialize the database and start the app at `http://localhost:5000`.
- `uv run --frozen python -m unittest test_app.py`: run the existing API and page tests.
- `cd frontend && npm install`: install frontend dependencies.
- `cd frontend && npm run build`: type-check and build the Vue 3 frontend.

Copy `.env.example` to `.env` for local configuration. AI-related endpoints require `AI_API_URL`, `AI_API_KEY`, and `AI_MODEL`; `SECRET_KEY` should be changed outside local demo environments.

## Coding Style & Naming Conventions

Use Python 3-compatible Flask patterns with 4-space indentation. Keep route helpers in `app.py`, data access and initialization in `database.py`, and name routes with lowercase kebab-case paths plus snake_case Python functions. Prefer explicit JSON responses with the existing `success` and payload fields.

Frontend files use 2- to 4-space indentation and vanilla HTML, CSS, and JavaScript. Use kebab-case for file names, camelCase for JavaScript functions and variables, and `setup*` or `render*` prefixes where they already clarify lifecycle behavior. No formatter or linter is configured, so match surrounding code before committing.

## Testing Guidelines

Tests use Python `unittest` and are currently in `test_app.py`. Name new tests `test_<behavior>`, add one test class per major area if the suite grows, and include fixture-driven assertions for API status codes and response payloads. Run the unittest command before submitting changes. There is no coverage threshold; cover new routes and regressions.

## Commit & Pull Request Guidelines

Git history uses short, direct subject lines, often in Chinese, such as `添加 vercel.json 修复 404 问题`. Keep commits focused and write a concise imperative subject.

Pull requests should describe the user-facing change, list commands run, link related issues, and include screenshots for HTML/CSS changes. Note any migration, database, environment-variable, or Vercel deployment impact.

## Security & Configuration Tips

Never commit `.env`, API keys, new secrets, upload contents, or disposable runtime database changes. Treat demo accounts as non-production data.
