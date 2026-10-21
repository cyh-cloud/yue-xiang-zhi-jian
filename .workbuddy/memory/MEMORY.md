# 项目长期记忆（粤乡智匠）

## 技术栈与启动

- 分支 `frontend/vue-rebuild`：Flask 后端在 `backend/`（入口 `backend/run.py`），Vue3 + TS + Vite 前端在 `frontend/`，旧 MPA 只读存档在 `legacy/reference/`。
- 一键启动：根目录 `start-dev.bat`（起后端 + 前端并打开 5173）。手动：`OPEN_BROWSER=0 python backend/run.py` + `cd frontend && npm run dev`。
- 后端解释器优先用 `C:\Users\c'y'h\.workbuddy\binaries\python\envs\default\Scripts\python.exe`（有 flask 2.3.3）。
- 前端装依赖必须带可写缓存：`npm install --cache "%LOCALAPPDATA%\npm-cache-yx" --registry=https://registry.npmmirror.com`，否则 `C:\Program Files\nodejs\node_cache` 无写权限会 `EPERM -4048`。

## 数据库（最容易出事的地方）

- **`data/yuexiang.db` 自提交 `57822a0` 起被 force-add 进版本库**（3.4MB 快照），而 `.gitignore` 里仍有 `data/*.db`。后果：切分支/拉取会静默覆盖本地库，运行时会一直显示 ` M`。
- 现行运行库 = 本地业务数据 + 从上游快照搬来的 22 张内容表（696KB，59 表）。**切任何分支前先复制 `data/` 到仓库外。**
- 备份保留（勿删）：`yuexiang.db.upstream-57822a0.bak`（上游快照原件）、`mine-20261021-1922.bak`（用户原库）、`merged-20261021-1930.bak`（合并产物）、`from-main-20261020.bak`（最原始数据）、`seed-20261020-2245.bak`（空种子库）。
- 老库升新库靠 `backend/db_schema.py` 的 `ALTER TABLE` 链，`init_db()` 会自动补列补表；实测 36 表 → 59 表无损。
- 内容（手艺/病虫害/案例/招聘/方言）只存在于 SQLite，代码里没有副本（ADR 0002）；`data/baseline.db` 不入库，由 `migrations/0001_content_to_db.py --make-baseline` 从现库复制生成。

## 本机网络

- GitHub 不可达，用镜像：`git remote add mirror https://ghfast.top/https://github.com/cyh-cloud/yue-xiang-zhi-jian.git`（`gh-proxy.com` 亦可用）。
