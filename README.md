# 粤乡智匠

粤乡智匠是一个面向农村本土人才培训的原型系统。项目由 Flask 后端和 Vue 3 前端组成：

- 后端：`backend/`，提供 Flask REST API 和 SQLite 数据层。
- 新前端：`frontend/`，使用 Vue 3、Vite、Pinia 和 Vue Router。
- 旧版静态页面保留在仓库根目录，不属于 v2 开发范围。

## 环境要求

- Python 3.12 或 3.13
- Node.js 18 或更新版本，建议使用 Node.js 20 LTS
- npm 9 或更新版本
- uv 0.11 或更新版本

## 快速启动

后端和前端需要分别启动。推荐使用两个终端窗口。

### 1. 启动后端

后端使用 `uv` 管理虚拟环境和依赖。在项目根目录执行：

```powershell
uv sync --frozen --directory backend
Copy-Item backend\.env.example backend\.env
uv run --directory backend --env-file .env python -m app.seed_dev
uv run --directory backend --env-file .env python run.py
```

macOS 和 Linux 使用：

```bash
uv sync --frozen --directory backend
cp backend/.env.example backend/.env
uv run --directory backend --env-file .env python -m app.seed_dev
uv run --directory backend --env-file .env python run.py
```

复制环境模板后，至少填写 `DEV_SEED_PASSWORD` 和 `SECRET_KEY`。本地种子会拒绝在 `FLASK_ENV=production` 时运行，不会输出密码，并会更新六个本地角色账号、默认兴趣标签和已上架课程。账号用户名可通过 `DEV_SEED_<ROLE>_USERNAME` 覆盖；未设置时使用 `student_demo`、`teacher_demo`、`enterprise_demo`、`government_demo`、`super_admin_demo` 和 `admin_demo`。本地凭据不得提交到版本库或用于生产环境。

后端启动后会自动初始化 SQLite 数据库，默认地址是：

```text
http://127.0.0.1:5000
```

健康检查地址：

```text
http://127.0.0.1:5000/api/health
```

### 2. 启动 Vue 前端

新开一个终端，进入 `frontend/`：

```bash
cd frontend
npm install
npm run dev
```

开发环境地址：

```text
http://127.0.0.1:5173
```

Vite 开发服务器会把 `/api` 请求代理到 `http://127.0.0.1:5000`，所以启动前端前应先启动 Flask 后端。

## 本地种子

```powershell
$env:DEV_SEED_PASSWORD = "<本地密码>"
$env:SECRET_KEY = "<本地密钥>"
uv run --directory backend python -m app.seed_dev
```

重复运行会更新同一批本地角色账号和课程种子，不会打印密码。命令只用于本地开发数据库。

## 构建和预览

在 `frontend/` 目录构建前端：

```bash
npm run build
```

构建完成后可以启动本地预览：

```bash
npm run preview
```

预览地址：

```text
http://127.0.0.1:4173
```

`npm run preview` 也会把 `/api` 请求代理到 Flask 后端，因此预览时仍需要保持后端运行。

## 测试

在项目根目录运行后端测试：

```bash
uv run --directory backend python -m unittest discover -s tests -v
```

在 `frontend/` 目录运行前端测试、类型检查和构建：

```bash
npm test
npx tsc -b --noEmit
npm run build
```

## 目录说明

| 路径 | 说明 |
| --- | --- |
| `backend/` | v2 Flask 应用、SQLite 数据层、测试和本地种子 |
| `frontend/` | Vue 3 + Vite 前端源码 |
| `specs/` | spec-kit 功能需求契约 |
| `docs/` | 产品、设计和项目上下文文档 |
| `data/` | 本地 SQLite 数据库和运行时数据 |
| `uploads/` | 本地上传文件 |

## 常见问题

### 更新后端依赖

后端依赖以 `pyproject.toml` 和 `uv.lock` 为准。修改依赖后执行：

```bash
uv lock
uv sync
uv export --format requirements-txt --output-file requirements.txt --no-hashes
```

`requirements.txt` 只用于 Vercel 的 Python Runtime，不作为本地开发入口。

### 5000 端口被占用

Flask 后端在 `run.py` 中固定使用 `5000` 端口。先确认是否有旧的 Python 进程仍在运行，停止它后重新执行 `python run.py`。

### 5173 或 4173 端口被占用

Vue 开发端口和预览端口由 `frontend/scripts/vite.mjs` 固定，`--port` 参数不会被当前启动脚本解析。停止占用端口的进程后重新启动。

### 页面能打开但接口报错

确认 Flask 后端是否在运行，并检查后端健康检查：

```text
http://127.0.0.1:5000/api/health
```

### AI 功能不可用

检查 `.env` 中是否正确配置了 `AI_API_KEY`、`AI_API_URL` 和 `AI_MODEL`。修改 `.env` 后需要重启后端。
