# 旧前端只读参照

这里保存 Vue SPA 收口前的多页面前端与旧 Playwright 套件，只用于核对迁移前的
页面结构、交互和接口调用，不参与构建、运行或测试。

- `mpa/`：旧 HTML、全局脚本、门户脚本、Service Worker 与旧静态模块。
- `e2e/`：旧 Playwright 配置和 specs，已不可从活动 `e2e/` 目录直接运行。
- `maintenance/`：迁移期间用过的一次性清理脚本。

活动前端只有 `frontend/` 的 Vue SPA。Flask 只提供 API 与 `uploads/`、`images/`
媒体；生产由 nginx 伺服 `frontend/dist`，e2e 由测试静态入口伺服同一份构建产物。

旧站页面里对 `styles.css` 的引用保留为迁移时原样。SPA 实际复用的公共样式已经移到
`frontend/src/styles/legacy-public.css`，避免在只读参照里维护第二份活动样式。

旧测试中的行为已迁到 `frontend/e2e/`，覆盖六角色登录与回退、会话恢复、权限拒绝、
上传、消息、AI 降级、审核门禁、就业、运营内容维护和桌面视觉基线。旧套件不得恢复
到活动测试命令中。
