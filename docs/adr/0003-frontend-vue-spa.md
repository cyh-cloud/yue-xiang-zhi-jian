# 0003 前端改为 Vue 3 + TypeScript 单页应用

状态：accepted

原前端由 13 个独立 HTML、约 1 万行全局 `script.js`、页面内联脚本和必须按顺序加载的全局函数组成。
改为 Vue 3 + TypeScript + Vite 的单页应用，由 Vue Router 管理现有业务路径，生产环境由 nginx
伺服构建产物并反向代理 `/api/*`，Flask 继续作为业务 API 与上传写入方。

## Consequences

- 旧 `.html` 地址由前端路由静默重定向到 SPA 路径，`teacher-panel.html` 统一重定向至 `/teacher`。
- 会话仍使用 `yuexiang_session` 与 `X-Session-Id`，由 Pinia 会话仓库在首次路由前恢复并向后端校验。
- 前端路由守卫按角色和能力限制后台入口，后端能力校验仍是最终权限边界。
- 媒体路径统一经前端规范化函数补前导 `/`，避免 SPA 深层路径把 `uploads/...` 解析到错误的相对目录。
- 生产使用 nginx 的 SPA fallback，并直接伺服 `/uploads/`、`/images/` 和构建资源。
- 本次删除旧 Service Worker 注册，离线能力留待最终视觉定稿后重新设计。
- 后端 `MAX_CONTENT_LENGTH` 调整为 50MB，与 3D 模型上传提示一致；nginx 同步放行 50MB。
- Windows 本地 nginx 运行在 ASCII 运行目录，通过 junction 指向仓库，避免 nginx 对中文
  路径的编码问题；监听端口与 Flask 反代端口分别由 `.env` 的 `NGINX_PORT`、`PORT` 决定。

## 收口

- 旧多页面前端、全局脚本与旧 Playwright 套件移到 `legacy/reference/`，只读，不参与
  构建、运行或测试。
- SPA 继续复用的公共视觉样式留在 `frontend/src/styles/`，不再从仓库根读取。
- Flask 不再伺服首页或旧静态前端，只保留 API 与 `uploads/`、`images/` 媒体；
  nginx 负责 SPA fallback、构建资源、媒体和 API 反向代理。
