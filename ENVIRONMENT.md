# 环境配置说明

本文覆盖从零拉起开发环境、配置 AI 服务、准备数据、部署到 nginx 的全过程，以及本项目实际踩过的故障与处置方式。

- 变量逐项模板：[`.env.example`](.env.example)
- 架构与分层：[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- 基线库生成：[`docs/baseline-database.md`](docs/baseline-database.md)

---

## 1. 运行环境

| 组件 | 最低版本 | 推荐版本 | 用途 |
| --- | --- | --- | --- |
| Python | 3.9 | 3.11 / 3.13 | 后端运行时 |
| Node.js | 20 LTS | 22 LTS | 前端构建、单测、端到端 |
| npm | 10 | 随 Node 安装 | 依赖管理 |
| SQLite | 3.35+ | 随 Python 内置 | 数据库（无需单独安装） |
| nginx | 1.24 | 1.26 | 仅生产部署 |
| Chrome / Edge | 最新版 | 最新版 | 3D 模型查看与 Playwright |

操作系统：Windows 10/11、macOS、Linux 均可。项目路径含中文时，Windows 上的 nginx 需要走 ASCII junction（见第 8 节）。

## 2. 依赖清单

### 2.1 后端

`requirements.txt` 只列 5 个直接依赖，其余均为标准库：

```text
flask==2.3.3
flask-cors==4.0.0
requests==2.31.0
python-dateutil==2.8.2
python-dotenv==1.0.0
```

| 包 | 作用 |
| --- | --- |
| Flask | Web 框架与蓝图路由 |
| flask-cors | `/api/*` 跨域放行（默认只放行本机来源） |
| requests | 调用上游 OpenAI 兼容接口 |
| python-dateutil | 农事日历与日期推算 |
| python-dotenv | 加载仓库根 `.env` |

安装：

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
pip install -r requirements.txt
```

### 2.2 前端

`frontend/package.json` 的直接依赖：

| 分类 | 包 |
| --- | --- |
| 运行时 | `vue` 3.5、`vue-router` 4.5、`pinia` 2.3、`axios` 1.7 |
| 构建 | `vite` 6、`@vitejs/plugin-vue` 5、`typescript` 5.7、`vue-tsc` 2.2 |
| 测试 | `vitest` 2.1、`@vue/test-utils` 2.4、`jsdom` 25、`@playwright/test` 1.48 |
| 规范 | `eslint` 9、`eslint-plugin-vue` 9、`@vue/eslint-config-typescript` 14 |

安装：

```bash
cd frontend
npm install
```

若 npm 缓存目录不可写（Windows 上常见 `EPERM -4048`），改用可写缓存：

```bash
npm install --cache "%LOCALAPPDATA%\npm-cache-yx" --registry=https://registry.npmmirror.com
```

### 2.3 端到端测试的浏览器

```bash
cd frontend
npx playwright install chromium
```

## 3. 环境变量

所有变量集中在仓库根 `.env`，完整模板与注释见 [`.env.example`](.env.example)。按用途分为六组：

### 3.1 基础运行

| 变量 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `SECRET_KEY` | 生产必填 | 随机生成 | 会话签名密钥；留空时每次启动变化，重启后旧会话失效 |
| `PORT` | 否 | `5000` | Flask 监听端口；非法值回落默认端口 |
| `NGINX_PORT` | 否 | `8081` | 生产 nginx 监听端口 |
| `YUEXIANG_DB` | 否 | `data/yuexiang.db` | 覆盖数据库路径，测试与 e2e 用 |

### 3.2 AI 服务

| 变量 | 必填 | 代码默认值 | 说明 |
| --- | --- | --- | --- |
| `AI_API_URL` | 否 | `https://api.siliconflow.cn/v1/chat/completions` | OpenAI 兼容端点 |
| `AI_API_KEY` | 建议 | 空 | 留空时 AI 接口返回 503，其余功能正常 |
| `AI_MODEL` | 否 | `Qwen/Qwen3-32B` | 文本模型，病害结构化诊断与兜底 |
| `AI_VL_MODEL` | 否 | `Qwen/Qwen3-VL-32B-Instruct` | 视觉模型，留空即关闭图片诊断 |
| `AI_CHAT_MODEL` | 否 | 空（跟随 `AI_MODEL`） | 问答类模型，换非推理模型可降低首字延迟 |
| `AI_REASONING_EFFORT` | 否 | 空 | 推理强度，仅推理模型有效 |
| `AI_REASONING_TOKEN_RESERVE` | 否 | `600` | 思考余量（token） |

`AI_API_KEY` 是「AI 是否可用」的唯一开关：`backend/ai/client.py` 的 `ai_configured()` 只认它非空。未配置时接口明确返回 503，不会返回假结果。

### 3.3 安全与跨域

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `TRUST_PROXY` | `0` | 是否信任 `X-Forwarded-For`；仅可信反代后设为 `1` |
| `CORS_ORIGINS` | 空 | 额外放行的来源，逗号分隔；本机来源已默认放行 |

### 3.4 限流额度

滑动窗口 300 秒，按「用户 + 端点」计数。默认值见 `.env.example`，一般无需修改。调低可保护上游额度，调高适合演示环境。

### 3.5 开发调试

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `FLASK_DEBUG` | `0` | 设为 `1` 开启调试器，仅本机可信环境 |
| `OPEN_BROWSER` | `1` | 启动时自动打开浏览器；脚本化启动设为 `0` |
| `STARTUP_URL` | 空 | 启动后打开的地址，留空打开健康检查页 |
| `YX_DEV_RELOAD` | `0` | 后端热重载，仅开发期 |

### 3.6 前端开发代理

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `VITE_PROXY_TARGET` | 空 | 覆盖 Vite 代理目标，留空为 `http://127.0.0.1:${PORT}` |

## 4. 启动方式

### 4.1 方式一：两个终端（推荐，跨平台）

终端 A：

```bash
python backend/run.py
```

终端 B：

```bash
cd frontend
npm run dev
```

访问 `http://127.0.0.1:5173`。后端健康检查在 `http://127.0.0.1:5000/api/health`。

### 4.2 方式二：Windows 一键脚本

```bat
start-dev.bat
```

脚本会定位带 Flask 的 Python、检查 `frontend/node_modules`、打开两个命令行窗口并拉起浏览器。首次使用前仍需在 `frontend/` 执行一次 `npm install`。

### 4.3 方式三：生产形态（nginx + 构建产物）

```bash
cd frontend
npm run build

cd ..
python tools/render_nginx_config.py --output deploy/nginx.conf
python backend/run.py
```

nginx 伺服 `frontend/dist`、`/uploads/`、`/images/`，并把 `/api/*` 代理到 Flask。Windows 可用：

```bash
python tools/nginx_runtime.py --check
python tools/nginx_control.py start
python tools/nginx_control.py smoke
python tools/nginx_control.py stop
```

运行目录为 `%LOCALAPPDATA%\YueXiangNginx`，通过 ASCII junction 指向仓库，规避 nginx 对中文路径的限制。

## 5. 数据库与初始数据

### 5.1 首次启动

`backend/run.py` 调用 `db_init.init_db()`，依次完成：

1. `apply_schema()`：建表、给既有库补列、清理已下线表；
2. 空库时写入六个演示账号（`db_seed_accounts.seed_demo_accounts`）；
3. 已有库时补齐缺失角色（`ensure_demo_accounts`）。

全流程幂等，重复启动不会重复建号，也不会改写内容表。

### 5.2 内容数据

仓库内含一份约 1.4 MB 的演示库 `data/yuexiang.db`：69 条病虫害（8 类作物、25 个来源、29 条实拍图）、123 条农事任务、5 个成功案例、14 条招募、24 条方言短语、4 项手工技艺、9 个社区讨论。

删除该文件后重新启动会得到「只有表结构与演示账号」的空库，此时页面可以进入，但内容列表为空。恢复方式三选一：

```bash
# A. 从版本库恢复随仓库提交的演示库
git checkout -- data/yuexiang.db

# B. 从自己留的备份恢复
copy 你的备份.db data\yuexiang.db

# C. 按基线库文档重建（需要一份已有内容的库）
python migrations/0001_content_to_db.py --make-baseline
copy data\baseline.db data\yuexiang.db
```

## 6. AI 服务配置与验证

1. 复制模板：`copy .env.example .env`
2. 填入密钥：`AI_API_KEY=sk-...`
3. 重启后端
4. 验证：

```bash
# 启动日志不应出现「未配置 AI_API_KEY」
# 前端进入「农业技能 → 农技问答」，提问应流式返回
```

换服务商时同时修改 `AI_API_URL`、`AI_MODEL`、`AI_VL_MODEL`。注意两类模型不能混用：

- `AI_MODEL` 与 `AI_VL_MODEL` 必须支持结构化 JSON 输出（病害诊断要解析字段）；
- `AI_CHAT_MODEL` 只承担纯文本对话，不能填只支持图片的模型；
- 推理模型的思考会占用 `max_tokens`，若正文为空串，优先调低 `AI_REASONING_EFFORT` 或增大 `AI_REASONING_TOKEN_RESERVE`。

## 7. 端口与网络

| 服务 | 默认端口 | 可配置项 |
| --- | --- | --- |
| Flask API | 5000 | `PORT` |
| Vite 开发服务器 | 5173 | `vite.config.ts`（固定） |
| nginx | 8081 | `NGINX_PORT` |

开发期前端把 `/api`、`/uploads`、`/images` 代理到 Flask。生产期前端与 API 同源，由 nginx 分流，不引入独立 API 域名。

## 8. 常见故障

| 现象 | 原因 | 处置 |
| --- | --- | --- |
| `端口已被占用` / 前端代理 502 | 上一个实例未退出，或 `PORT` 与代理目标不一致 | 结束占用进程；确认 `.env` 的 `PORT` 与前端 `VITE_PROXY_TARGET` 一致 |
| 改了 `.env` 但不生效 | `load_dotenv()` 只在进程启动时执行 | 重启后端；不要只刷新浏览器 |
| AI 接口 503「未启用」 | `AI_API_KEY` 为空 | 填入密钥并重启 |
| AI 返回空正文 | 推理模型把 `max_tokens` 全用于思考 | 调低 `AI_REASONING_EFFORT` 或调高 `AI_REASONING_TOKEN_RESERVE` |
| 图片诊断 400 | `AI_VL_MODEL` 指向了不支持图片的模型 | 换成视觉模型；或留空以关闭图片诊断 |
| 前端图片全部裂开 | Vite 未代理 `/images` 与 `/uploads` | 确认 `vite.config.ts` 的 proxy 配置，重启 dev server |
| `npm install` 报 `EPERM -4048` | 默认缓存目录在 `Program Files` 下不可写 | 指定可写缓存与镜像（见 2.2） |
| e2e 大量用例失败 | 缺少 `data/baseline.db` | 按 `docs/baseline-database.md` 生成基线库 |
| 上传返回 413 | 超过 50 MB 上限 | 上限唯一真相源为 `backend/shared/upload_limits.py`，修改后运行 `python tools/sync_upload_limit.py` |
| 访问 `data/` 下文件返回 404 | 静态路由对 `data/` 整目录拒绝，资质证件只经鉴权接口下发 | 属预期行为，不要放开 |
| nginx 启动失败且路径含中文 | nginx 对中文路径支持不佳 | 使用 `tools/nginx_control.py`，它会把运行目录放在 `%LOCALAPPDATA%` 并用 junction 指向仓库 |
| 切换分支后数据变了 | `data/*.db` 曾被 force-add 进版本库 | 切换前备份 `data/`；不要用分支操作覆盖运行库 |

## 9. 验收自检

```bash
# 1. 健康检查
curl http://127.0.0.1:5000/api/health

# 2. 后端单测
python -m unittest discover -s . -p "test_*.py" -t .

# 3. 架构与静态检查
python tools/check_architecture.py
python tools/check_python.py

# 4. 前端类型、单测、构建
cd frontend
npm run typecheck
npm run test:unit
npm run build
```

四项全部通过，且浏览器能完成「学员登录 → 农技问答 → 病虫害诊断 → 电商实训 → 投递岗位」主流程，即视为环境就绪。
