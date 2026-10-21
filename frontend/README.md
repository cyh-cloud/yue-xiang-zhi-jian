# 粤乡智匠前端

Vue 3 + TypeScript + Vite 单页应用。源码位于本目录，构建产物为 `dist/`。

活动前端只有这一套 SPA。迁移前的多页面页面、全局脚本与旧 Playwright 套件保存在
仓库根 `legacy/reference/`，只读，不参与构建、运行或测试。

## 开发

```powershell
cd frontend
npm install
npm run dev
```

开发服务器默认监听 `5173`，并将 `/api` 代理到 `http://127.0.0.1:5000`。
后端端口由仓库根 `.env` 的 `PORT` 决定；两个 worktree 并行运行时，请让两者的
`PORT` 与前端代理目标保持一致。

## 校验

```powershell
npm run typecheck
npm run test:unit
npm run build
npm run test:e2e
```

`test:e2e` 先构建 `dist/`，再由同一个 `e2e/serve.py` 启动真实 Flask 和测试专用静态
入口。第一条 Playwright 配置验证 history fallback 与 `/api` 代理；第二条独立配置
以 `E2E_START_API=0` 启动同一静态入口但不启动 Flask，验证代理返回 502 且 SPA 仍可取。
数据库来自临时目录中的基线副本，两条命令结束后都删除该目录。先准备
`data/baseline.db`，否则依赖内容的用例会按既有约定明确失败。

全站最终验收记录（执行 SHA、命令、结果、版本与未覆盖项）见
[`../docs/frontend-vue-rebuild-spec.md#最终验收记录`](../docs/frontend-vue-rebuild-spec.md#最终验收记录)；
CSS 专项证据见
[`../docs/css-final-acceptance.md`](../docs/css-final-acceptance.md)。

旧 `.html` 路径仍由前端路由静默重定向；它们不依赖旧页面文件，也不会回退到 Flask
静态路由。Flask 只提供 API 与 `/uploads/`、`/images/` 媒体。

## CSS 契约与视觉矩阵

样式归属、旧样式退役状态和机械检查边界见
`../docs/css-style-ownership.md`。视觉矩阵的基线库准备、运行方式与更新规则见
`../docs/css-visual-regression.md`。

全局语义 token 在 `src/styles/tokens.css`，reset、基础元素、焦点和减少动效规则在
`src/styles/base.css`，跨页面复用的按钮、字段、标签、卡片、表格、状态、弹窗和消息
中心原语在 `src/styles/components.css`。`src/main.ts` 只加载 token、基础、共享组件，
以及外壳和页面域样式；旧全局样式已退出活动入口。

```powershell
python tools/check_frontend_styles.py
npm run test:visual:matrix
```

在仓库根运行 Python 检查；第二条命令在 `frontend/` 目录运行。矩阵需要
`data/baseline.db`，该文件不提交。

## 生产

构建后由 nginx 伺服 `frontend/dist`。完整模板见仓库根
`deploy/nginx.conf.template`，用 `python tools/render_nginx_config.py --output <path>`
渲染出实际配置；
该配置同时负责 SPA fallback、静态媒体和 `/api/*` 反向代理。AI 流式问答单独关闭
代理缓冲，其他 API 保持正常缓冲。

Windows 本地可用项目自带运行器。它会把配置、日志、PID 与临时文件放到
`%LOCALAPPDATA%\YueXiangNginx`，并用 ASCII junction 指向仓库，避开 nginx 对中文路径
的限制：

```powershell
python tools/nginx_runtime.py --check
python tools/nginx_control.py start
python tools/nginx_control.py smoke
python tools/nginx_control.py stop
```

nginx 监听端口由 `.env` 的 `NGINX_PORT` 决定，默认 `8081`；反代目标由 `PORT`
决定，默认 `5000`。`VITE_PROXY_TARGET` 可覆盖开发代理目标，但生产仍使用同源
`/api/*`，不引入独立 API 域名。

上传上限的唯一真相源是 `backend/shared/upload_limits.py`。修改它之后运行
`python tools/sync_upload_limit.py` 更新前端常量；`--check` 模式会拒绝陈旧副本。
nginx 的 `client_max_body_size` 由 `tests/test_upload_deployment_contract.py`
解析后与同一常量比较。
