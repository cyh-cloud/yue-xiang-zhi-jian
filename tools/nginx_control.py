# -*- coding: utf-8 -*-
"""Start, stop, and smoke-test the project nginx runtime."""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import nginx_runtime
from tools.render_nginx_config import default_listen_port


def _url(port, path):
    return "http://127.0.0.1:%d%s" % (port, path)


def _get(url, timeout=3):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.status, response.read()


def _login(base):
    body = json.dumps({
        "username": "student_demo",
        "password": "123456",
    }).encode("utf-8")
    request = urllib.request.Request(
        base + "/api/auth/login",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status, json.loads(response.read())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("start", "stop", "status", "smoke"))
    parser.add_argument("--runtime", default=str(nginx_runtime.DEFAULT_RUNTIME))
    parser.add_argument("--port", type=int)
    parser.add_argument("--proxy-port", type=int)
    args = parser.parse_args()

    listen_port = args.port or default_listen_port()
    runtime, config = nginx_runtime.render_runtime(
        args.runtime,
        listen_port,
        args.proxy_port,
    )
    nginx = nginx_runtime.nginx_executable()

    if args.action == "status":
        result = nginx_runtime.run_nginx(runtime, config)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        return result.returncode

    if args.action == "stop":
        result = subprocess.run(
            [nginx, "-p", str(runtime) + os.sep, "-c", str(config), "-s", "quit"],
            capture_output=True,
            text=True,
        )
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        return result.returncode

    if args.action == "start":
        result = nginx_runtime.run_nginx(runtime, config)
        if result.returncode != 0:
            sys.stderr.write(result.stderr)
            return result.returncode
        # nginx daemonizes on Windows and keeps the inherited stdout/stderr
        # handles alive. Start it detached so the control command returns.
        process = subprocess.Popen(
            [nginx, "-p", str(runtime) + os.sep, "-c", str(config)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=(
                getattr(subprocess, "DETACHED_PROCESS", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            ),
        )
        time.sleep(0.5)
        if process.poll() not in (None, 0):
            return process.returncode
        print("nginx started: http://127.0.0.1:%d/" % listen_port)
        return 0

    base = _url(listen_port, "")
    checks = []
    try:
        status, body = _get(base + "/api/health")
        checks.append(("health", status, body[:200].decode("utf-8", "replace")))
        status, body = _get(base + "/",)
        checks.append(("spa-root", status, body[:80].decode("utf-8", "replace")))
        status, body = _get(base + "/agriculture")
        checks.append(("spa-history", status, body[:80].decode("utf-8", "replace")))
        status, login = _login(base)
        checks.append(("login", status, login.get("user", {}).get("role", "")))
        status, body = _get(base + "/uploads/models_3d/chaoshan_mudiao_preview.png")
        checks.append(("media", status, str(len(body))))
    except (urllib.error.URLError, OSError) as exc:
        print("smoke failed: %s" % exc, file=sys.stderr)
        return 1

    for name, status, detail in checks:
        print("%s: %d %s" % (name, status, detail))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
