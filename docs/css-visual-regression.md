# CSS 视觉回归矩阵

状态：T10 复审通过。矩阵用于 CSS 组件化期间的视觉等价验证，不重新定义产品视觉。

## 覆盖范围

截图由 `frontend/e2e/visual-matrix.spec.ts` 生成，基线保存在
`frontend/e2e/visual-matrix.spec.ts-snapshots/`。Windows Chromium 是正式门槛，
Linux 基线属于独立环境任务。

| 范围 | 截图 | 状态 |
| --- | --- | --- |
| 公开页 | `public-home-desktop-light.png` | 匿名，桌面浅色 |
| 公开页 | `public-agriculture-desktop-light.png` | 匿名，固定 2026 年 3 月日历 |
| 公开页 | `public-ecommerce-desktop-light.png` | 匿名，三个实训面板 |
| 公开页 | `public-crafts-desktop-light.png` | 匿名，固定广绣详情与空模型态 |
| 公开页 | `public-resources-desktop-light.png` | 匿名，方言、案例、政策 |
| 公开页 | `public-employment-desktop-light.png` | 匿名，固定岗位与招募公告 |
| 公开页 | `public-case-detail-desktop-light.png` | 固定成功案例 |
| 公开页 | `public-login-desktop-light.png` | 匿名登录页 |
| 公开页 | `public-community-desktop-light.png` | 固定两条讨论 |
| 主题 | `public-home-desktop-dark-large.png` | 公开站深色加大字 |
| 后台 | `backoffice-teacher-dashboard-desktop-light.png` | 教师角色默认页 |
| 后台 | `backoffice-government-dashboard-desktop-light.png` | 政府角色默认页 |
| 后台 | `backoffice-enterprise-dashboard-desktop-light.png` | 企业角色默认页 |
| 后台 | `backoffice-operator-dashboard-desktop-light.png` | 运营角色默认页 |
| 后台 | `backoffice-super-admin-dashboard-desktop-light.png` | 超管角色默认页 |
| 主题 | `backoffice-super-admin-dark-large.png` | 后台深色加大字 |
| 状态 | `community-empty-desktop-light.png` | 公开页空态 |
| 状态 | `community-error-desktop-light.png` | 公开页错误态 |
| 状态 | `admin-announcements-loading-desktop-light.png` | 后台加载态 |
| 状态 | `admin-announcements-empty-desktop-light.png` | 后台空态 |
| 状态 | `admin-announcements-error-desktop-light.png` | 后台错误态 |
| 打印 | `resume-print.png` | 学员简历打印媒体 |
| 移动抽样 | `public-home-mobile-light.png` | 390 x 844 视口抽样 |
| 移动抽样 | `backoffice-super-admin-mobile-light.png` | 390 x 844 视口抽样 |
| CDN 降级 | `public-home-desktop-cdn-degraded.png` | Font Awesome 与 model-viewer 均失败 |

移动截图是现有响应式结果的抽样，不是完整移动端适配验收。

## 准备基线库

视觉矩阵依赖固定种子库，不把二进制库提交到 git。工作树可以从主检出复制：

```powershell
New-Item -ItemType Directory -Force data | Out-Null
Copy-Item -LiteralPath "E:\Project\skipped_work\粤乡智匠v1\data\baseline.db" `
  -Destination "data\baseline.db" -Force
```

也可以在仓库根重新生成：

```powershell
python migrations/0001_content_to_db.py --make-baseline
```

`data/baseline.db` 已被 `.gitignore` 忽略。不要把库文件加入提交。需要从其他路径
读取时，设置 `YUEXIANG_BASELINE_DB`，Playwright 的 `e2e/serve.py` 会复制该文件到
临时库，结束后由 global teardown 清理。

## 运行

首次安装依赖：

```powershell
cd frontend
npm ci
```

运行完整矩阵：

```powershell
npm run test:visual:matrix
```

该命令先执行构建和 TypeScript 检查，再由 `e2e/serve.py` 启动真实 Flask 和构建后的
SPA。正常态与降级态都在 Playwright 中显式控制 CDN，不依赖外部网络。只跑某个状态时：

```powershell
npx playwright test e2e/visual-matrix.spec.ts -g "community error state"
```

矩阵需要登录账号来自基线库，账号与现有行为 e2e 相同：

- `teacher_demo` / `123456`
- `gov_demo` / `123456`
- `enterprise_demo` / `123456`
- `operator_demo` / `123456`
- `admin_demo` / `admin123`
- `student_demo` / `123456`

## 确定性约定

- 浏览器：Playwright Chromium，Windows 基线。
- 桌面视口：`1280 x 900`，全页截图。
- 移动抽样：`390 x 844`，视口截图。
- 语言与时区：`zh-CN`、`Asia/Shanghai`。
- 媒体：`prefers-reduced-motion: reduce`，截图配置同时禁用动画并隐藏光标。
- 字体：截图前等待 `document.fonts.ready`。
- 图片：截图前等待现有图片请求完成。
- CDN 正常态：Font Awesome 的 CSS 与字体由锁定的本地
  `@fortawesome/fontawesome-free@6.0.0` 响应，model-viewer 由本地就绪桩响应；
  两个数据属性都必须到达 `loaded` 后才截图。
- CDN 降级态：显式拦截两个 CDN，两个数据属性必须到达 `failed`，并确认降级提示
  同时列出 Font Awesome 与 model-viewer 后才截图。
- 失败分类：资源状态失败、就绪超时与截图差异分别报告，不把环境抖动误报成视觉回归。
- 数据：公开页和五个角色默认页使用 `visual-matrix.fixtures.ts` 的固定响应；
  登录与权限仍走真实 Flask 和临时基线库。

## 基线更新规则

1. 先运行矩阵，不要看到差异就直接更新。
2. 检查 Playwright 的 expected、actual、diff，确认差异来自预期 CSS 变化。
3. 如果差异来自时序、字体、数据或环境，先修确定性，不更新截图。
4. 只有视觉结果已确认等价或产品明确批准变化后，才运行：

```powershell
npm run test:visual:matrix:update
```

5. 单独审查新增或变化的 PNG，不把行为回归拍成新基线。

T1 的新基线均在 CSS 组件化改写前从当前实现生成。现有
`public-shell.spec.ts-snapshots/`、`visual-regression.spec.ts-snapshots/` 等旧基线
不得在 T1 中更新或删除。

## 验收记录

最终一次完整矩阵的实际命令、结果和环境边界统一记录在
`docs/css-final-acceptance.md`，避免双份验收记录漂移。
