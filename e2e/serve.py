"""E2E 专用启动器：每次用一份全新的库起 Flask，避免写坏真实数据。

由 Playwright 的 webServer 拉起；库路径经 YUEXIANG_DB 指定（见 db_connection 的开关）。
AI 默认不配置（AI_API_KEY 由 webServer 置空），AI 接口据此返回 503，便于断言契约。

T10 之后 init_db() 只建表补列加灌演示账号，**不写任何内容行**（ADR 0002：内容由基线库
交付，启动路径碰内容就等于覆盖运营改过的数据）。所以 e2e 的初始状态改成「从基线库复制
一份」：内容表有行，登录与内容接口才跑得通；而每次跑测试都从同一份基线出发，结果可复现。

基线库缺失时（例如新 clone 的机器还没生成过）退回 init_db() 的空库：接口会返回空列表，
spec 里依赖内容的断言会失败并提示缺基线库，不会静默给出一个看似通过的假绿。
"""
import os
import pathlib
import shutil
import sys

# 后端代码整体迁入 backend/ 后，Flask 应用与 db_init 都在 backend/ 下。
ROOT = pathlib.Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(ROOT))

db = os.environ["YUEXIANG_DB"]
# 每次启动都从零开始：删掉可能残留的库及其 WAL/SHM，保证已知初始状态。
for suffix in ("", "-wal", "-shm", "-journal"):
    candidate = pathlib.Path(db + suffix)
    if candidate.exists():
        candidate.unlink()

baseline = pathlib.Path(os.environ.get(
    "YUEXIANG_BASELINE_DB",
    pathlib.Path(__file__).resolve().parent.parent / "data" / "baseline.db"))
if baseline.is_file():
    pathlib.Path(db).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(baseline, db)
    # 基线库切回过 DELETE 模式，复制过来再确认一次，避免带上 WAL 附属文件
    import sqlite3
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.close()
else:
    print("[e2e/serve.py] 未找到基线库 %s，退回 init_db() 空库；"
          "依赖内容的 spec 会失败。生成基线库：python migrations/0001_content_to_db.py --make-baseline"
          % baseline, file=sys.stderr)


import db_init  # noqa: E402

db_init.init_db()

from app import app  # noqa: E402

app.run(
    host="127.0.0.1",
    port=int(os.environ.get("E2E_PORT", "5057")),
    debug=False,
    use_reloader=False,
)
