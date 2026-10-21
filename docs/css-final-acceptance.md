# CSS 组件化最终验收

状态：T10 复审验收记录，对应 Issue #121，服务 Issue #96。T9 的验收入口和历史结果仍保留在 git 历史中。

## 终态

- `tokens.css`：全局语义 token、明暗主题、大字模式和断点契约。
- `base.css`：reset、根元素、焦点、减少动效、共享控件的大字基础和打印基础规则。
- `components.css`：跨页面共享的按钮、字段、标签、卡片、表格、状态、弹窗和消息中心。
- `public-shell.css` / `backoffice.css`：公开站和后台外壳、页面外框、角色 token 覆盖。
- `views/<domain>/*.css`：页面域私有样式，只由同域视图导入。
- `legacy/reference/frontend/legacy-public.css`：只读历史参照，禁止活动代码引用。

活动入口 `frontend/src/main.ts` 不再导入旧全局样式。旧类名前缀已经切换为语义名，
模板、`id`、`data-testid`、活动 CSS 和 e2e 选择器使用同一套语义命名。
`.bewly-*` 公开站侧栏、启动页残留、无引用的引导卡和旧表格样式已删除，
没有活动写入点需要迁移。

## 验收结果

| 检查 | 结果 |
| --- | --- |
| CSS 样式检查 | 通过，116 个活动文件，2 个只读参照样式文件 |
| Python 静态检查 | 通过，294 个文件 |
| 后端架构检查 | 通过，21 个领域路由目录，18 个共享层模块 |
| 前端类型检查 | 通过 |
| 前端构建 | 通过 |
| 前端单测 | 48 passed |
| ESLint | 通过 |
| CSS / 旧样式 / 选择器契约单测 | 34 passed |
| 目标行为 e2e | 63 passed，一次调用完成 |
| 完整视觉矩阵 | 25/25 passed，一次调用完成，未更新截图基线 |

实际验收命令（2026-10-21，T10 复审树，仓库根与 `frontend/` 分别执行）：

```powershell
python tools/check_frontend_styles.py
python -m unittest tests.test_frontend_styles tests.test_e2e_selector_contract tests.test_css_semantic_aliases tests.test_legacy_retirement -v
python tools/check_python.py
python tools/check_architecture.py
cd frontend
npm run typecheck
npm run build
npm run lint
npm run test:unit
$env:YUEXIANG_BASELINE_DB='E:\Project\skipped_work\粤乡智匠v1\data\baseline.db'
npx playwright test e2e/agriculture.spec.ts e2e/crafts.spec.ts e2e/employment.spec.ts e2e/employment-resume.spec.ts e2e/operator-crafts-dialects.spec.ts e2e/operator-content.spec.ts e2e/resources.spec.ts e2e/public-shell.spec.ts e2e/ecommerce-training.spec.ts --grep-invert 'visual baseline stays stable'
npm run test:visual:matrix
```

环境与边界：

- Windows Chromium，桌面视口 `1280 x 900`，移动抽样 `390 x 844`。
- 视觉矩阵正常态和 CDN 降级态都由 Playwright 显式控制，25 个场景在 T10
  当前树的一次 `npm run test:visual:matrix` 中全部通过，没有失败后重跑。
- E2E 使用 `YUEXIANG_BASELINE_DB` 指向的基线库，由 `e2e/serve.py` 复制到临时库；
  没有把数据库、`node_modules/`、`dist/` 或测试结果加入提交。
- `npm ci` 在 Node `v24.14.0` 下报告 `abbrev` / `nopt` 的 engine 警告，
  但安装成功，类型检查、构建、单测、ESLint 和 e2e 均通过。

## 已知环境边界

- Python 全量 578 个用例在当前工作树缺少完整内容基线时出现大量既有的数据夹具失败，
  不是本次 CSS 变更引入；本次运行的是 CSS、旧样式、选择器与前端契约相关的聚焦测试。
- Windows Chromium 是正式截图环境，Linux 像素基线不在本次范围。
- AI 上游真实成功链未在本次 CSS 验收中重新验证。
