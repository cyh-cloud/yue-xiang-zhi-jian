"""E2E 专用启动器：每次用一份全新的种子库起 Flask，避免写坏真实数据。

由 Playwright 的 webServer 拉起；库路径经 YUEXIANG_DB 指定（见 database.py 的开关）。
AI 默认不配置（AI_API_KEY 由 webServer 置空），AI 接口据此返回 503，便于断言契约。
"""
import os
import pathlib
import sys

# 后端代码整体迁入 backend/ 后，Flask 应用与 database 都在 backend/ 下。
ROOT = pathlib.Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(ROOT))

db = os.environ["YUEXIANG_DB"]
# 每次启动都从零开始：删掉可能残留的库及其 WAL/SHM，保证已知初始状态。
for suffix in ("", "-wal", "-shm", "-journal"):
    candidate = pathlib.Path(db + suffix)
    if candidate.exists():
        candidate.unlink()


import db_init  # noqa: E402

db_init.init_db()

from app import app  # noqa: E402

app.run(
    host="127.0.0.1",
    port=int(os.environ.get("E2E_PORT", "5057")),
    debug=False,
    use_reloader=False,
)
