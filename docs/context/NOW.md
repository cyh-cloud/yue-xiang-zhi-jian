# Current Work

**目标**: 完成 Vue 3 学员首页原型、评审修复和后端 uv 依赖迁移。

**已完成**:
- 按评审修复 7 项：Grid named-area 布局、运行时数据库还原、根目录忽略规则、弹窗模式切换焦点、文档迁入 `docs/`、锚点 `scroll-margin-top`、Vite TypeScript project input。
- 根目录 `.gitignore` 已排除本地工具、IDE、缓存和构建产物，同时保留 `.agents/memories/AGENTS.md`。
- `.agents/memories/AGENTS.md` 与项目根 `AGENTS.md` 已建立项目记忆路由。
- 根目录 `README.md` 已补齐双进程启动、构建、测试和故障排查说明。
- 后端虚拟环境和依赖已迁移到 `uv`：`pyproject.toml` 与 `uv.lock` 为权威来源；`requirements.txt` 由 `uv export` 生成，仅保留 Vercel Python Runtime 兼容入口。

**已验证**:
- `npm run build` 通过，生成 `frontend/dist`。
- `npx tsc -b --noEmit` 通过。
- `uv sync --frozen` 成功创建并同步 `.venv`。
- `uv run --frozen python -m unittest test_app.py` 14 个测试通过；AI 401 是测试内预期未授权路径。
- 1440px 桌面浏览器几何验证：6 个模块的 Grid area 与行/列关系正确，就业列表与 footer 为整行。
- 1000px 锚点滚动验证：头部底部 112px，模块标题顶部 181px，标题未被遮挡；`scroll-margin-top` 为 110px。
- AuthDialog 登录/注册双向切换后焦点均在面板内；320px 无横向溢出。

**运行与验证口径**:
- 后端：`uv sync --frozen` 后执行 `uv run --frozen python run.py`，默认 `http://127.0.0.1:5000`。
- 前端：`npm run preview`，实际由 `scripts/vite.mjs` 固定到 `http://127.0.0.1:4173`；`--port` 参数不会被该脚本解析。
- 前端浏览器检查需使用 `agent-browser --args "--no-sandbox"`。
- `eval --stdin` 在当前 Windows 环境易触发 agent-browser daemon 重启失败，改用短内联 `eval` 或 Base64 结果执行。

**工作树边界**: 本次任务已获得本地提交授权；提交后不 push。运行时数据库在提交前恢复，`.venv`、缓存、IDE 状态和构建产物不提交。
