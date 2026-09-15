# Project Index

This file is human-facing documentation. Agent routing and durable agent memory live under `.agents/memories/AGENT.md`; do not treat this file as the agent context authority.

**定位**: 粤乡智匠学员培训平台原型。Flask 后端与 Vue 3 前端分离；当前分支 `v2/frontend/lixKRT-rebulid`。

**当前状态**: 学员首页 Vue 3 视觉原型已完成评审修复、构建/类型检查、后端测试与浏览器几何验证。

**活动里程碑**: Vue 3 前端重建（原型优先、农村学员、演示原型）。

**主要阻塞**: 无。

**人类文档**:
- `docs/DESIGN.md`: Ark `family=ark`、`depth=maximal` 的前端设计口径。
- `docs/PRODUCT.md`: 产品目标、用户与原型范围。
- `docs/context/NOW.md`: 已归档的旧上下文快照，不再是当前状态。
- `frontend/`: Vue 3 + Vite 前端源码。
- `pyproject.toml`, `uv.lock`: uv 管理的后端依赖与锁文件。
- `app.py`, `database.py`, `run.py`: Flask 后端与 SQLite 数据层。
- `api/index.py`: Vercel serverless 入口。

**最后核验**: 2026-09-09。
