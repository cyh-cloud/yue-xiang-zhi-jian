# CSS 组件化最终验收

状态：T14 收口记录，对应 Issue #81。

## 终态

- `tokens.css`：全局语义 token、明暗主题、大字模式和断点契约。
- `base.css`：reset、根元素、焦点、减少动效和打印基础规则。
- `components.css`：跨页面共享的按钮、字段、标签、卡片、表格、状态、弹窗、消息中心，
  以及从旧表按原顺序迁出的跨页共享规则。
- `public-shell.css` / `backoffice.css`：公开站和后台外壳、角色 token 覆盖。
- `views/<domain>/*.css`：页面域私有样式，只由同域视图导入。
- `legacy/reference/frontend/legacy-public.css`：只读历史参照，禁止活动代码引用。

活动入口 `frontend/src/main.ts` 不再导入旧全局样式。旧类名前缀已经切换为语义名，
模板、活动 CSS 和 e2e 选择器使用同一套命名。

## 验收结果

| 检查 | 结果 |
| --- | --- |
| CSS 样式检查 | 通过，116 个活动文件，2 个只读旧样式文件 |
| Python 静态检查 | 通过，294 个文件 |
| 后端架构检查 | 通过 |
| 前端类型检查 | 通过 |
| 前端构建 | 通过 |
| 前端单测 | 48 passed |
| ESLint | 通过 |
| CSS 契约单测 | 8 passed |
| 视觉矩阵 | 24/25 passed；唯一失败为外部 CDN 加载抖动，单跑 home 矩阵 4/4 passed |
| 农业、手工、就业、运营行为 e2e | 37/38 passed；唯一失败为 SSE 时序抖动，单跑该用例通过 |

## 已知环境边界

- Python 全量 578 个用例在当前工作树缺少完整内容基线时出现大量既有的数据夹具失败，
  不是本次 CSS 变更引入；CSS 相关契约测试全部通过。
- Windows Chromium 是正式截图环境，Linux 像素基线不在本次范围。
- AI 上游真实成功链未在本次 CSS 验收中重新验证。
