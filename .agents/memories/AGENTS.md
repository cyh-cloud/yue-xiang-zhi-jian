# Project Memory Operating Rules

1. 本文件维护粤乡智匠项目内的持久记忆。只保存跨会话有价值的项目定位、边界、验收口径、复用经验与路由规则；不保存完整聊天记录或一次性调试过程。

2. 读取顺序：
- 每次接手或跨会话续作时，先读项目根目录 `AGENTS.md`，再读本文件。
- 随后按需读取 `docs/PROJECT_INDEX.md`，再按任务读取 `docs/context/NOW.md`、`docs/DESIGN.md` 或相关源码。
- 不默认读取全部文档、旧截图或历史记录。

3. 写入边界：
- 当前阶段、验证结果和临时风险写入 `docs/context/NOW.md`。
- 设计口径写入 `docs/DESIGN.md`。
- 产品边界写入 `docs/PRODUCT.md`。
- 固定规则、安全边界和路由规则写入项目根目录 `AGENTS.md` 或本文件。
- 新事实与旧记录冲突时，先核验源码、测试或实时服务状态，再更新权威来源。

4. 项目固定事实：
- 当前前端为 Vue 3 + Vite + Pinia，后端为 Flask；前端通过内部 API adapter 与后端解耦。
- 后端虚拟环境和依赖由 `uv` 管理；`pyproject.toml` 与 `uv.lock` 是权威来源，`requirements.txt` 是 Vercel 兼容导出。
- 设计口径使用 Ark `family=ark`、`depth=maximal`。
- 分支以现场 `git status` 为准；文档不替代实时核验。

5. 工作树与验证边界：
- 运行时数据库、上传文件、本地工具目录、IDE 状态和构建产物不得提交。
- 代码、视觉或接口修改后至少运行相关构建或测试；浏览器视觉检查优先使用 DOM/几何验证，不把图片交给非图片理解代理处理。
- 提交、推送、清理、恢复和删除是不同授权，未经明确要求不得执行。

6. 已验证项目经验：
- Vue 组件使用 CSS Grid named areas 时，子元素必须显式绑定 `grid-area`；仅用源码顺序依赖 auto-placement 会在宽屏模板下错位，局部 `grid-column`/`grid-row` 也可能覆盖 named area。
- 对话框内切换登录/注册时，表单会被 `v-if`/`v-else` 卸载重建；需要监听模式变化并重新聚焦面板内首个控件，关闭时恢复触发焦点。
- `frontend/tsconfig.node.json` 只能引用实际存在的 Vite/启动脚本入口；标准 `npx tsc -b` 与 `npm run build` 的检查范围不同，二者都要核验。
- Windows/headless 下使用 agent-browser 时，每次启动或重启浏览器的同一命令都要带 `--args "--no-sandbox"`；先 curl 探活目标端口，优先用 snapshot/short eval/DOM 几何断言，不要以 `#app` 作为 a11y 作用域。

7. 交接原则：
- 用文件路径和短摘要续接，不复制完整旧对话。
- 更新记忆时区分已验证事实、风险、计划和建议。
