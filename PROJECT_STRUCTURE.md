# 粤乡智匠 - 项目目录结构

本文件描述仓库的职责分区，不枚举具体文件：文件会改名搬家，按职责找才找得准。

## 顶层分区

| 目录 | 放什么 |
| --- | --- |
| `backend/` | 全部后端代码：应用工厂、领域路由蓝图、数据访问层、共享层 |
| `frontend/` | Vue 3 + TypeScript + Vite 单页应用、前端测试与构建产物 |
| `legacy/reference/` | 迁移前多页面前端与旧 e2e 的只读参照 |
| `deploy/` | nginx 等部署层配置，不承载业务逻辑 |
| `docs/` | ADR、重构方案、运维说明 |
| `e2e/` | Playwright 共用的真实 Flask 启动器与临时目录清理 |
| `tests/` | 领域级与前端运行契约单测 |
| `tools/` | 机械检查、上传上限同步等仓库工具 |
| `images/` `uploads/` | 固定图片素材、用户上传产物 |
| `data/` | SQLite 库与运行日志，不进版本库 |
| `migrations/` | 一次性内容迁移脚本与测试探针（ADR 0002） |

仓库根保留 `requirements.txt`、`.env.example` 与运行配置。旧多页面 HTML、全局脚本、
门户脚本和旧 Service Worker 只在 `legacy/reference/` 中作为只读参照存在。

## 前端

活动前端只有 `frontend/` 的 Vue 3 + TypeScript + Vite 单页应用。Vue Router 管理公开
页面与六类角色的后台路径，Pinia 管理会话，Axios 负责普通请求与 multipart 上传，
SSE 使用流式 `fetch`。

开发时 Vite 代理 `/api`。生产由 nginx 伺服 `frontend/dist`、`/uploads/` 与
`/images/`，并把 `/api/*` 反向代理到 Flask。Flask 是业务 API 与上传写入方，不再
伺服旧多页面前端。旧 `.html` 地址由前端路由静默重定向。

视觉迁移期的公共样式位于 `frontend/src/styles/`；旧站参照不再维护第二份活动样式。
CSS 组件化改写与移动端适配不属于本次收口。

## 后端分层

后端按领域拆分，一个领域一个蓝图目录。改后端前先读
`docs/adr/0001-backend-domain-split.md`（边界与裁决）与
`docs/adr/0002-content-into-database.md`（内容落库）。术语见 `GLOSSARY.md`。

- **共享层**：`core`（应用工厂、会话与角色鉴权、限流、统一错误响应）、
  `ai`（上游模型调用的唯一出口）、`shared`（零领域状态的纯函数与纯配置）。
- **领域路由层**：`domains/<领域>/`，一个领域一个目录。
- **数据访问层**：`db_domains/<领域>.py`，一个领域一个模块。
- **基础设施**：连接工厂、建表定义、口令散列、播种逻辑，各自独立成模块。
- **路径基准**：`repo_paths.py` 的 `REPO_ROOT` 指向仓库根。

## 部署

自托管单机是当前唯一部署形态：

1. `cd frontend; npm run build` 生成 `frontend/dist/`。
2. nginx 使用 `deploy/nginx.conf.template` 渲染出的配置伺服 SPA 与媒体，并代理 `/api/*`。
   Windows 开发机可用 `tools/nginx_runtime.py` 与 `tools/nginx_control.py` 生成 ASCII
   运行目录、检查配置、启动、冒烟和停止 nginx；运行目录不进入仓库。
3. Flask 通过 `python backend/run.py` 启动，负责 API 与上传写入。

没有多 worker、没有容器编排。SQLite 单文件库放在 `data/` 下，`.gitignore` 忽略
`data/*.db`；新环境用基线库还原。

### 新环境怎么起

    python migrations/0001_content_to_db.py --make-baseline
    cp data/baseline.db data/yuexiang.db
    python backend/run.py

详见 `docs/baseline-database.md`。

## 演示账户

- 教师：`teacher_demo` / `123456`
- 学员：`student_demo` / `123456`

其余后台角色账号由演示播种与测试基线提供。

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Vue Router、Pinia、Axios
- 后端：Python Flask、SQLite
- AI：SiliconFlow 兼容接口
