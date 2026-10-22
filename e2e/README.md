# 粤乡智匠 E2E 启动器

活动 Playwright 测试位于 `frontend/e2e/`，由 `frontend/playwright.config.ts` 和
`frontend/playwright.backend-unavailable.config.ts` 驱动。本目录只保留两者共用的
真实 Flask 启动器与临时目录清理脚本。

`serve.py` 每次从 `data/baseline.db` 复制一份临时库，启动真实 Flask，并由测试静态
入口伺服构建后的 `frontend/dist`、代理 `/api`、`/uploads/` 与 `/images/`。旧多页面
前端模式已删除，不再接受 `E2E_FRONTEND=legacy`。

运行入口：

```powershell
cd frontend
npm run test:e2e
```

基线库缺失时依赖内容的用例会明确失败，不会退化成假绿。
