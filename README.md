# yue-xiang-zhi-jian
响应乡村振兴
# 粤乡智匠

粤乡智匠是一个面向农村本土人才培训的原型系统。项目由 Flask 后端和 Vue 3 前端组成：

- 后端：`app.py`、`database.py`、`run.py`，提供 REST API 和 SQLite 数据层。
- 新前端：`frontend/`，使用 Vue 3、Vite、Pinia 和 Vue Router。
- 旧版静态页面：保留在仓库根目录，由 Flask 服务继续访问。

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
uv sync --frozen
Copy-Item .env.example .env
uv run --frozen python run.py
```

macOS 和 Linux 使用：

```bash
uv sync --frozen
cp .env.example .env
uv run --frozen python run.py
```

`uv sync --frozen` 会自动创建 `.venv`，并按 `uv.lock` 安装依赖，不需要手动激活虚拟环境。如果还没有 `.env`，先复制 `.env.example` 并填写必要配置。AI 相关功能需要 `AI_API_URL`、`AI_API_KEY` 和 `AI_MODEL`。生产环境必须替换 `SECRET_KEY`。没有 AI 配置时，基础页面和大部分 API 仍可运行，AI 功能会不可用或降级。

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

## 演示账号

数据库首次初始化后会创建以下演示账号：

| 角色 | 用户名 | 密码 |
| --- | --- | --- |
| 学员 | `student_demo` | `123456` |
| 教师 | `teacher_demo` | `123456` |
| 企业 | `enterprise_demo` | `123456` |
| 政府人员 | `gov_demo` | `123456` |
| 管理员 | `admin_demo` | `admin123` |

这些账号只用于本地演示，不要用于生产环境。

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
uv run --frozen python -m unittest test_app.py
```

在 `frontend/` 目录运行前端类型检查：

```bash
npx tsc -b --noEmit
```

## 目录说明

| 路径 | 说明 |
| --- | --- |
| `app.py` | Flask 应用和 REST API |
| `database.py` | SQLite 数据层和初始化逻辑 |
| `run.py` | 本地后端启动脚本 |
| `pyproject.toml` | 后端依赖和 Python 版本声明 |
| `uv.lock` | 后端依赖锁文件 |
| `requirements.txt` | 从 `uv.lock` 导出的 Vercel 兼容依赖清单 |
| `frontend/` | Vue 3 + Vite 前端源码 |
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
