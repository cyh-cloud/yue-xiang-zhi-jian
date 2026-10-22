# -*- coding: utf-8 -*-
"""Build and validate an ASCII-only nginx runtime for the project.

Windows nginx cannot reliably open configuration or root paths containing the
repository's Chinese directory names. Keep the repository config as a template,
then render an ASCII runtime directory next to it and expose the project through
a directory junction.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.render_nginx_config import (  # noqa: E402
    default_listen_port,
    render as render_template,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "YueXiangNginx"
PROJECT_LINK = "project"


def _ascii_path(path):
    value = str(Path(path).resolve())
    try:
        value.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError("nginx runtime path must be ASCII-only: %s" % value)
    return value


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def _ensure_project_link(runtime):
    link = runtime / PROJECT_LINK
    if link.exists() or link.is_symlink():
        if link.is_dir():
            return link
        raise ValueError("project link exists but is not a directory: %s" % link)
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(REPO_ROOT)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError("failed to create project junction: %s" % result.stderr)
    else:
        link.symlink_to(REPO_ROOT, target_is_directory=True)
    return link


def render_runtime(runtime=DEFAULT_RUNTIME, listen_port=None, proxy_port=None):
    listen_port = listen_port or default_listen_port()
    runtime = Path(_ascii_path(runtime))
    for name in ("conf", "logs", "temp", "client_body_temp", "proxy_temp",
                 "fastcgi_temp", "uwsgi_temp", "scgi_temp"):
        (runtime / name).mkdir(parents=True, exist_ok=True)
    mime_types = nginx_home() / "conf" / "mime.types"
    if not mime_types.is_file():
        raise FileNotFoundError("nginx mime.types not found: %s" % mime_types)
    shutil.copyfile(mime_types, runtime / "conf" / "mime.types")
    project = _ensure_project_link(runtime)

    project_for_nginx = str(project).replace("\\", "/")
    source = render_template(project, listen_port, proxy_port)

    # nginx resolves relative include paths against its prefix. Pin every
    # process-owned path so it never writes into the repository or Scoop's conf.
    source = source.replace("worker_processes auto;", "worker_processes 1;")
    source = source.replace(
        "events {",
        "error_log %s/logs/error.log warn;\npid %s/logs/nginx.pid;\n\nevents {"
        % (runtime.as_posix(), runtime.as_posix()),
        1,
    )
    source = source.replace(
        "http {",
        "http {\n    access_log %s/logs/access.log;\n"
        "    client_body_temp_path %s/client_body_temp;\n"
        "    proxy_temp_path %s/proxy_temp;\n"
        "    fastcgi_temp_path %s/fastcgi_temp;\n"
        "    uwsgi_temp_path %s/uwsgi_temp;\n"
        "    scgi_temp_path %s/scgi_temp;"
        % tuple([runtime.as_posix()] * 6),
        1,
    )
    _write(runtime / "conf" / "nginx.conf", source)
    return runtime, runtime / "conf" / "nginx.conf"


def nginx_executable():
    executable = shutil.which("nginx")
    if not executable:
        raise FileNotFoundError("nginx is not installed or not on PATH")
    return executable


def nginx_home():
    configured = os.getenv("NGINX_HOME", "").strip()
    if configured and Path(configured).is_dir():
        return Path(configured).resolve()
    scoop_home = Path.home() / "scoop" / "apps" / "nginx" / "current"
    if scoop_home.is_dir():
        return scoop_home.resolve()
    executable = Path(nginx_executable()).resolve()
    if executable.parent.name.lower() == "shims":
        candidate = executable.parent.parent / "apps" / "nginx" / "current"
        if candidate.is_dir():
            return candidate.resolve()
    return executable.parent


def run_nginx(runtime, config, *args):
    command = [
        nginx_executable(),
        "-p", str(runtime) + os.sep,
        "-c", str(config),
        "-t",
    ]
    command.extend(args)
    return subprocess.run(command, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", default=str(DEFAULT_RUNTIME))
    parser.add_argument("--port", type=int)
    parser.add_argument("--proxy-port", type=int)
    parser.add_argument("--output", help="path for the rendered nginx config")
    parser.add_argument("--check", action="store_true", help="run nginx -t")
    args = parser.parse_args()

    try:
        runtime, config = render_runtime(args.runtime, args.port, args.proxy_port)
        if args.output:
            output = Path(args.output)
            _write(output, config.read_text(encoding="utf-8"))
        if args.check:
            result = run_nginx(runtime, config)
            sys.stdout.write(result.stdout)
            sys.stderr.write(result.stderr)
            return result.returncode
        print("runtime=%s" % runtime)
        print("config=%s" % config)
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print("nginx runtime setup failed: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
