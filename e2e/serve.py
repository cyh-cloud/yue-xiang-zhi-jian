"""E2E 专用启动器：用一份全新的库起真实 Flask，可选伺服构建后的 SPA。

由 Playwright 的 webServer 拉起；库路径经 YUEXIANG_DB 指定（见 db_connection 的开关）。
AI 默认不配置（AI_API_KEY 由 webServer 置空），AI 接口据此返回 503，便于断言契约。

T10 之后 init_db() 只建表补列加灌演示账号，**不写任何内容行**（ADR 0002：内容由基线库
交付，启动路径碰内容就等于覆盖运营改过的数据）。所以 e2e 的初始状态改成「从基线库复制
一份」：内容表有行，登录与内容接口才跑得通；而每次跑测试都从同一份基线出发，结果可复现。

基线库缺失时（例如新 clone 的机器还没生成过）退回 init_db() 的空库：接口会返回空列表，
spec 里依赖内容的断言会失败并提示缺基线库，不会静默给出一个看似通过的假绿。

同一个进程另起测试专用静态入口，伺服 frontend/dist 的 history fallback，并把
/api/* 原样转发给 Flask。E2E_START_API=0 时该配置不启动 Flask，静态入口因此返回
502，供后端不可达用例观察真实代理失败。这里没有 Vite preview、第二个业务 API
或第二份基线数据，也不再有旧多页前端模式。
"""
import atexit
import os
import pathlib
import shutil
import socket
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


START_API = os.environ.get("E2E_START_API", "1") != "0"
API_PORT = int(os.environ.get("E2E_API_PORT", "0")) or free_port()
if not START_API:
    # Reserve-and-release gives a port on which nothing is listening, so the
    # static entry observes a genuine connection failure against Flask.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        API_PORT = probe.getsockname()[1]
STATIC_PORT = int(os.environ.get("E2E_PORT", "5157"))
API_ORIGIN = "http://127.0.0.1:%d" % API_PORT
STATIC_ROOT = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "dist"

if not (STATIC_ROOT / "index.html").is_file():
    print("[e2e/serve.py] 找不到构建产物 %s，先运行 npm run build" % STATIC_ROOT,
          file=sys.stderr)
    raise SystemExit(1)


class SpaRequestHandler(SimpleHTTPRequestHandler):
    """静态入口：/api 代理到 Flask，其余路径按 SPA history fallback 处理。"""

    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript; charset=utf-8",
        ".mjs": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".json": "application/json",
        ".svg": "image/svg+xml",
        ".wasm": "application/wasm",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_ROOT), **kwargs)

    def log_message(self, fmt, *args):
        if os.environ.get("E2E_VERBOSE"):
            super().log_message(fmt, *args)

    def do_GET(self):
        if self._is_api_path():
            self._proxy_api()
            return
        if self._proxy_media():
            return
        if not self._serve_static_file():
            self.path = "/index.html"
            try:
                super().do_GET()
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                pass

    def do_POST(self):
        if self._is_api_path():
            self._proxy_api()
            return
        self.send_error(405)

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST

    def do_OPTIONS(self):
        if self._is_api_path():
            self._proxy_api()
            return
        self.send_error(405)

    def _is_api_path(self):
        return self.path == "/api" or self.path.startswith("/api/")

    def _proxy_media(self):
        """Mirror the production nginx media split without a second API."""
        prefixes = ("/uploads/", "/images/")
        if not self.path.startswith(prefixes):
            return False
        if not START_API:
            self.send_error(502)
            return True
        upstream = Request(
            API_ORIGIN + self.path,
            headers={name: self.headers[name] for name in ("Accept",) if self.headers.get(name)},
            method=self.command,
        )
        try:
            with urlopen(upstream, timeout=30) as response:
                status = response.status
                response_headers = response.headers
                payload = response.read()
        except HTTPError as error:
            status = error.code
            response_headers = error.headers
            payload = error.read()
        except (URLError, OSError) as error:
            print("[e2e/serve.py] Flask 不可达：%s" % error, file=sys.stderr)
            self.send_error(502)
            return True

        self.send_response(status)
        for name in ("Content-Type", "Cache-Control", "ETag"):
            value = response_headers.get(name)
            if value:
                self.send_header(name, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # Browsers abort lazy image requests during navigation.
            pass
        return True

    def _serve_static_file(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            path = os.path.join(path, "index.html")
        if not os.path.isfile(path):
            return False
        relative = os.path.relpath(path, STATIC_ROOT).replace(os.sep, "/")
        if relative == "index.html":
            self.path = "/index.html"
        try:
            super().do_GET()
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # Playwright aborts in-flight asset requests during navigation.
            # A disconnected static client is not a server failure.
            return True
        return True

    def _proxy_api(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else None
        headers = {}
        for name in ("Content-Type", "X-Session-Id", "Accept"):
            value = self.headers.get(name)
            if value:
                headers[name] = value
        upstream = Request(API_ORIGIN + self.path, data=body, headers=headers,
                           method=self.command)
        try:
            with urlopen(upstream, timeout=30) as response:
                status = response.status
                response_headers = response.headers
                payload = response.read()
        except HTTPError as error:
            status = error.code
            response_headers = error.headers
            payload = error.read()
        except (URLError, OSError) as error:
            print("[e2e/serve.py] Flask 不可达：%s" % error, file=sys.stderr)
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            try:
                self.wfile.write(
                    b'{"success":false,"code":"backend_unreachable","message":"backend unreachable"}'
                )
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                # The browser may abort while the proxy is reporting an outage.
                pass
            return

        self.send_response(status)
        for name in ("Content-Type", "Cache-Control", "ETag"):
            value = response_headers.get(name)
            if value:
                self.send_header(name, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # The browser may navigate away while an auth response is in flight.
            # That is a normal client disconnect, not a server failure.
            pass


class FlaskThread(threading.Thread):
    def __init__(self):
        super().__init__(name="e2e-flask", daemon=True)
        self.server = None

    def run(self):
        from werkzeug.serving import make_server
        try:
            self.server = make_server("127.0.0.1", API_PORT, app, threaded=True)
            self.server.serve_forever()
        except Exception as error:
            print("[e2e/serve.py] Flask 启动失败：%s" % error, file=sys.stderr)
            raise

    def stop(self):
        if self.server:
            self.server.shutdown()


flask_thread = FlaskThread() if START_API else None
if flask_thread:
    flask_thread.start()


def wait_for_flask():
    for _ in range(100):
        try:
            with urlopen(API_ORIGIN + "/api/health", timeout=1):
                return
        except (URLError, OSError):
            time.sleep(0.05)
    raise RuntimeError("Flask 未在 5 秒内就绪")


if flask_thread:
    wait_for_flask()
static_server = ThreadingHTTPServer(("127.0.0.1", STATIC_PORT), SpaRequestHandler)


def shutdown():
    static_server.shutdown()
    if flask_thread:
        flask_thread.stop()


atexit.register(shutdown)

print("[e2e/serve.py] SPA http://127.0.0.1:%d -> Flask %s" % (STATIC_PORT, API_ORIGIN))
try:
    static_server.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    static_server.server_close()
