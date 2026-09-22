# Repository Guidelines

<!-- agent-memory-routing:v1 -->
## Agent Memory Routing

- Agent memory: `.agents/memories/`; human documentation: `docs/`
- Project constitution (read before any requirement work): `.specify/memory/constitution.md`
- Before nontrivial work, read `.agents/memories/PROJECT_INDEX.md`; load only linked topic files, never the whole tree.

## Project Routes

- Current work: `.agents/memories/NOW.md`
- Runtime, build, test, and browser checks: `.agents/memories/RUNBOOK.md`
- Durable design decisions: `.agents/memories/DECISIONS.md`
- Failure handling: `.agents/memories/failures/INDEX.md`
- superpowers 设计/实现计划: `.agents/memories/plans/`（首次 writing-plans 落盘时生成；其 Spec 字段指向 `specs/<NNN>/spec.md`）
- superpowers 非 feature 探索设计: `.agents/memories/specs/`
- Feature 工件（需求权威源，首个 `$speckit-specify` 生成）: `specs/<NNN-feature>/`
- Frontend: `frontend/`; Backend（v2 完全重写，首个实现计划生成后创建）: `backend/`; 旧系统代码（根目录 `app.py`/`database.py`/旧 HTML 页面）冻结：不可参考、不可导入、不可迁移

## Toolchain Composition

- Feature 需求定义只走 spec-kit（`$speckit-specify` 起）；同一 feature 禁止再产出 superpowers 设计文档（双规格源禁止）。
- 实现与执行走 superpowers：writing-plans → subagent-driven-development。
- superpowers worktree 挂当前 `v2/lixKRT/NNN-<slug>` feature 分支（spec-kit 生成 `NNN-<slug>` 后立即改名），不另开分支；`.superpowers/`、`.worktrees/` 不入 git，`.specify/`、`specs/` 入 git，`.agents/` 按仓库现有策略（memories 进，skills 不进）。
- 模型阶梯（spawn 必须显式传 model+effort）：实现者=`step-5-preview`（high）；任务级审查=`step-5-preview`（high）；修复 4-5 轮升档=`step-5-preview`（high）；最终全分支审查=`step-5-preview`（high）。图片agent=`step-3.7-flash`（high）
- 模块合并后跑 `$speckit-converge`（弱化版：只对照 `specs/<NNN>/spec.md`）；发现缺口回填 superpowers 计划或记 `NOW.md`，不新建 tasks.md 权威。
- SDD 门禁与修复循环按全局豁免执行（Agent Memory `AGENTS.md` 规则 5/7/13）。

## Failure Handling

- 同方向连续失败两次即停；读 `.agents/memories/failures/INDEX.md` 与命中案例，记录 `Next probe`/`Forbidden`/`Stop condition` 后只做一次最小探针；无新证据时标记 `BLOCKED` 并询问用户。
- SDD 修复循环不适用两次即停（全局规则 5 豁免），其 BLOCKED 出口仍按本协议记录案例。

## Memory Maintenance

- 创建或更新记忆前先读 `.agents/memories/AGENT.md`；失败记录用 `guides/failure-protocol.md` 与 `templates/failure-case.md`。
<!-- /agent-memory-routing:v1 -->

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
