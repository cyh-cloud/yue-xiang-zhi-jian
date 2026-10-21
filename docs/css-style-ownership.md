# CSS 终态与样式归属

状态：T10 复审终态。后续 CSS ticket 以本文件为样式归属的单一真相源。

## 定位

CSS 组件化的目标是降低样式影响面，不改变现有视觉。判断一段样式该放哪里时，按
「token -> 全局基础层 -> 共享组件 -> 外壳 -> 页面域 -> 动态状态」的顺序落位。
组件只在第二个真实使用点出现后上提为共享组件，不为每个 DOM 元素建立 Vue 组件。

## 层级职责

| 层 | 目标位置 | 允许职责 | 不允许 |
| --- | --- | --- | --- |
| token | `frontend/src/styles/tokens.css`，角色和主题覆盖在对应外壳根节点 | 语义颜色、表面、文字、边框、间距、圆角、阴影、层级、字体、动效、断点、角色主题 token | 组件选择器、页面布局、业务状态样式 |
| 全局基础层 | `frontend/src/styles/base.css` | reset、`html` / `body` / `#app` 基础规则、全站焦点与可访问性约定、全站滚动基础 | 组件外观、页面布局、角色条件样式 |
| 共享组件层 | `frontend/src/styles/components.css`，或确有第二处复用的组件 SFC scoped 样式 | 公开站跨页复用的按钮、标签、面板、弹窗、消息中心、空态与加载态 | 后台专属原语、页面专属布局、角色选择器、跨页覆盖、token 定义 |
| 公开站外壳 | `frontend/src/layouts/PublicLayout.vue`、`frontend/src/components/public/`、`frontend/src/styles/public-shell.css` | 顶栏、导航、页脚、用户菜单、主题与大字开关、CDN 降级提示、公开站根布局 | 具体页面内容、教师或后台页面规则 |
| 后台外壳 | `frontend/src/layouts/BackofficeLayout.vue`、`frontend/src/components/backoffice/`、`frontend/src/styles/backoffice.css` | 顶栏、侧栏、页面框架、连接状态、消息中心挂载点、角色根节点 token 覆盖，以及多后台页面复用的 `backoffice-*` 控件原语 | 具体角色页面布局、业务表格字段样式 |
| 社区外壳 | `frontend/src/views/community/community.css`，由社区列表与详情共同消费 | 社区外壳、列表与详情共享的社区级结构 | 公开站其他页面或后台页面规则 |
| 页面域 | `frontend/src/views/<domain>/`、`frontend/src/components/<domain>/`，私有样式与 SFC 同域存放 | 页面布局、页面专属区块、领域组件样式、领域内状态排列 | 其他页面域的私有样式、全局根选择器、角色选择器 |
| 动态状态 | 根节点 `data-theme` / `data-large-text` / `data-role`，组件状态类或语义属性，数值用 CSS 自定义属性 | 主题、大字、角色、加载、空、错误、未读、已读、选中、悬停、焦点、校验、进度与比例 | 在组件里复制角色色值、用页面选择器覆盖其他域、把静态装饰写成内联样式 |

## 页面域清单

公开页面域：

- `home`
- `agriculture`
- `ecommerce`
- `crafts`
- `resources`
- `employment`
- `community`
- `case-detail`
- `login`

后台页面域：

- `teacher`
- `government`
- `enterprise`
- `operator`
- `admin`

公开站跨页原语进入 `frontend/src/styles/components.css`，后台跨页原语进入
`frontend/src/styles/backoffice.css`，
由 `main.ts` 在 `base.css` 之后加载。跨域复用先判断是否
真的出现第二个使用点，再决定上提为共享组件样式。

## 主题、角色与动态值

- 明暗主题与大字模式只在 `html` 根节点设置数据属性，由 token 和基础层响应。
- 角色差异集中在外壳根节点的 token 覆盖，例如
  `.backoffice-shell[data-role="government"]`。
  页面和共享组件只消费 token，不写 `[data-role]` 条件样式。
- 数据驱动的颜色、宽度、进度和比例使用 CSS 自定义属性或受限内联绑定。
- 静态装饰、固定间距、固定颜色不得以内联样式表达。
- 无法证明无引用的动态类、第三方注入类和旧站稳定外部契约先保留并标记，
  不以“看起来没用”为删除依据。

## 旧样式退役

活动入口只加载 `tokens.css`、`base.css`、`components.css` 和外壳/页面域样式。
`frontend/src/styles/legacy-public.css` 已删除，旧样式只保留在
`legacy/reference/frontend/legacy-public.css` 作为历史参照，文件头包含
“历史参照，禁止活动代码引用”。任何活动代码都不得 import `legacy/reference/`。

尚未上提的跨页规则已经按原顺序并入 `components.css`，页面专属规则由各页面域
样式文件持有。新增规则一律进入上表的目标层。

### 启动页旧规则证据（#100）

2026-10-21 复核结果：

- 退役前 `components.css` 共有 70 处 `.startup-*` 命中：12 条深色主题覆盖和
  58 行 `Startup Detail Modal` 规则组（含分区注释）。
- 活动 `frontend/src`、`frontend/e2e`、活动入口和构建产物中没有 `.startup-*`
  模板、脚本、动态字符串或运行时引用；`backend/run.py` 的 `startup_url`
  只表示服务启动地址，与页面样式无关。
- `legacy/reference/frontend/legacy-public.css` 中的同组规则属于只读历史参照，
  不参与构建或运行，按本文件约定保留。
- 上述 70 处已从 `components.css` 删除，没有活动代码需要迁移到
  `frontend/src/views/home/home.css`，也没有行为等价例外。

### 公开站侧栏旧规则证据（#105）

2026-10-21 复核结果：

- 活动 `frontend/src`、模板、脚本和动态字符串中没有 `.bewly-sidebar`、
  `.bewly-nav-item`、`.bewly-nav-tip`、`.bewly-nav-left` 或
  `.bewly-nav-toggle` 的写入点。
- `frontend/e2e/visual-matrix.spec.ts` 只把 `.bewly-sidebar` 作为布局断言，
  要求计数为 0，不是产品元素。T9 保留该断言，作为旧侧栏不得回流的运行时守卫。
- `public-shell.css` 中整套 Bewly 侧栏规则、深色 token 和媒体查询已删除。
  没有活动页面需要迁移到其他层级。
- 农业、电商、就业三个页面的 `--pa` 板块色变量已迁回各自页面域；
  `public-shell.css` 不再定义页面 ID token。

## 机械检查

在仓库根运行：

```powershell
python tools/check_frontend_styles.py
python -m unittest tests.test_frontend_styles tests.test_e2e_selector_contract tests.test_css_semantic_aliases tests.test_legacy_retirement -v
```

检查器负责：

- 只读旧样式 import；
- 活动入口对 `tokens.css` / `base.css` 的显式导入与顺序；
- `components.css` 在 `base.css` 之后的导入顺序；
- 共享组件层原语覆盖、禁止 token 定义、角色选择器和 `!important`；
- 共享组件层出现后台专属 `backoffice-*` 原语时拒绝；
- 全局语义 token 分组、明暗主题和大字模式覆盖完整性；
- 共享层不得重新定义全局 token、reset 或全站焦点规则；
- 页面私有样式跨域 import；
- 基础层与外壳之外的万能全局选择器，以及页面级 `[data-theme]` / `[data-large-text]` 根属性覆盖；
- 外壳与 token 层之外的 `[data-role]` 选择器；
- 共享组件层出现 Hero、农业问答、病虫害、文案训练、启动页等页面私有选择器时拒绝回流；
- `components.css` 的静态类选择器在活动模板或脚本中必须有消费点；
  动态状态类按 `docs/css-semantic-exceptions.md` 的数据前缀保留；
- 只读旧样式文件头的禁用标记。

视觉等价由 `docs/css-visual-regression.md` 的矩阵验证。机械检查通过不能替代截图。

## 改动前判断

1. 这段规则属于 token、基础、共享组件、外壳、页面域还是动态状态？
2. 是否已有共享组件或 token 可以复用？
3. 是否会让另一个页面域依赖本页私有样式？
4. 是否通过角色名、`!important` 或根选择器解决本应由归属解决的问题？
5. 改动后是否先跑机械检查，再跑对应视觉矩阵？
