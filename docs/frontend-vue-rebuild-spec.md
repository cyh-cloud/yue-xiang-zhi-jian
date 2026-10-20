# 前端 Vue 重构规格

状态：accepted，已由 Issue #39 与 ADR 0003 完成收口

## 目标

把现行 HTML + 全局 JavaScript 多页面前端完整迁移为 Vue 3 + TypeScript 单页应用。
公开页面视觉保持不变；教师、政府、企业、运营后台与超级管理员后台统一外壳语言，
保留各角色主题色。后端继续作为 API 与上传写入方，本次允许同步调整上传上限。

## 已确认约束

- 分支：`frontend/vue-rebuild`，在独立 worktree 中完成。
- 源码目录：仓库根 `frontend/`；构建产物：`frontend/dist/`。
- 技术栈：Vue 3、TypeScript strict、Vite、Vue Router、Pinia、Axios。
- Axios 负责普通请求与 FormData；SSE 保留 `fetch` 流式实现。
- 采用标准 SPA history 路由，不使用 hash，不保留 `.html` 页面。
- 生产由 nginx 伺服 SPA、`/uploads/`、`/images/`，并把 `/api/*` 反向代理到 Flask。
- 开发由 Vite 代理 `/api`，不引入 `VITE_API_BASE_URL`，不依赖第二台 API 主机。
- 旧 `.html` 地址与 `teacher-panel.html` 静默重定向到新路径。
- 删除 `teacher-panel.html` 与主站“教学面板”入口，只保留 `/teacher` 教师后台。
- 公开页面视觉不变；后台统一采用超管页的顶栏、可折叠侧栏、卡片、表格与反馈规范，
  保留教师、政府、企业、运营各自主题色。
- 本次只面向桌面端，不做移动端适配；现有移动样式不主动删除，但不作为验收项。
- 迁移期间复用旧站视觉规则；收口后公共样式只保留在 `frontend/src/styles/`，
  `portal.css` 随旧站进入只读参照。CSS 组件化改写另立阶段。
- 旧 Service Worker 停用并清理缓存，离线策略留待最终定稿。
- 背景色、图标、字体、文案、业务权限与现有可见功能保持等价；不新增课程材料展示等
  旧前端不存在的新功能。
- 媒体路径统一规范为同源绝对 URL，兼容有无前导 `/` 与反斜杠路径。
- 3D 模型上传上限为 50MB，Flask 与 nginx 同步调整。
- 旧前端保留在 `legacy/reference/` 作为只读参考，不参与构建、运行或测试。
- e2e 可以重写；既有行为断言不得削弱。
- 验收包含 TypeScript、构建、前端单测、Python 单测、Playwright、关键页面视觉对比，
  以及迁移完成后的 CSS 改写复核。

## 路由

公开层：

- `/`
- `/agriculture`
- `/ecommerce`
- `/crafts`
- `/resources`
- `/employment`
- `/case-detail/:id`
- `/login`

教师层：

- `/teacher`
- `/teacher/dashboard`
- `/teacher/announcements`
- `/teacher/analytics`
- `/teacher/trainings`
- `/teacher/models`

管理门户层：

- `/admin/*`
- `/government/*`
- `/enterprise/*`
- `/operator/*`

后端角色与能力仍为权限真相源。前端守卫在恢复会话、刷新能力后校验角色与能力；
后端接口校验仍是最终安全边界。无会话进入受保护页面时记录目标并转到 `/login`；
角色不符或能力不足时静默进入该角色默认页。

## 组件边界

- 基础组件：按钮、输入框、选择器、标签、卡片、表格容器、弹窗、空态、加载态。
- 后台基础组件：统一后台外壳、侧栏、顶栏、消息中心、页面头部、筛选栏、数据表格。
- 业务区块组件：农时日历、AI 问答、病虫害诊断、直播实训、简历编辑、学员名册、
  内容审核等。
- 通用组件只在出现第二处真实复用时上提；不为每个元素包装组件。

## 实施顺序

1. 创建分支与独立 worktree。
2. 搭建 `frontend/` 基础设施、路由、会话仓库、API 客户端与统一资源规则。
3. 迁移公开页面并建立视觉基线。
4. 迁移超管、教师、政府、企业、运营后台。
5. 接入 nginx、旧链接重定向、Service Worker 清理。
6. 重写 e2e，完成行为与视觉验收。
7. 迁移完成后独立进行 CSS 改写。
8. 对最终分支做完整复核。

## 收口后的后续阶段

以下事项在 grill 阶段已经明确为后续阶段，不属于本次 Vue 迁移未完成：

- CSS 组件化改写与全局覆盖清理。
- 移动端适配与移动端视觉验收。
- PWA 与离线缓存策略重新设计。
- AI 模块整体改造，包括提示词、降级文案与上游模型选择。
- 课程材料展示与上传界面。旧站没有该入口，本次不新增。
