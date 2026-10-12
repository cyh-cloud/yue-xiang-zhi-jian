# 粤乡智匠 E2E（Playwright）

以后端功能性 bug 排查为主的端到端测试。每次对一份全新种子库自起 Flask（127.0.0.1:5057），不碰真实 `data/yuexiang.db`。

## 运行

- 首次：`npm install` 然后 `npx playwright install chromium`
- 跑：`npx playwright test`

## 结构

- `serve.py`：每次启动删旧库、`init_db()` 种子、起 Flask。库路径由环境变量 `YUEXIANG_DB` 指定（见根 `database.py` 的开关，默认行为不变）。
- `playwright.config.js`：用 webServer 拉起 `serve.py` 并等 `/api/health`；把 `AI_API_KEY` 置空，使 AI 接口返 503，便于稳定断言。
- `specs/`：
  - `ownership.spec.js` 越权矩阵（各端点 × 各登录态）
  - `notifications-idor.spec.js` 通知越权（当前应失败 = 缺陷在；修复后转绿）
  - `review-gate.spec.js` 案例审核门禁
  - `messages.spec.js` 消息状态机 + 护栏
  - `smoke.spec.js` / `portals-smoke.spec.js` 前端加载巡查（无 5xx、无未捕获异常）
- `findings/`：运行产出的证据与 `BUG-REPORT.md`。

## 说明

- 通知越权用例当前**故意失败**，用于固化缺陷；修好应转绿。
- 前端默认连 `localhost:5000`，测试用 `page.addInitScript` 注入 `window.APP_CONFIG.apiBaseUrl` 指向同源 5057。
- AI 流程契约测试待 `.env` 配置（见 `docs/ai-setup.md`）或接本地 mock 后补充。
