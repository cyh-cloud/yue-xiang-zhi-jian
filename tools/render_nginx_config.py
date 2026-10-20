# -*- coding: utf-8 -*-
"""Render the nginx template with repository and upload-limit values.

The deployment config intentionally stays a template in git. Rendering is
deterministic for a given repository path and backend upload constants.
"""

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO_ROOT, "backend")
TEMPLATE = os.path.join(REPO_ROOT, "deploy", "nginx.conf.template")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from shared.upload_limits import MAX_REQUEST_MEGABYTES  # noqa: E402

DEFAULT_LISTEN_PORT = 8081


def _env_value(name):
    value = (os.getenv(name) or "").strip()
    if value:
        return value
    env_path = os.path.join(REPO_ROOT, ".env")
    try:
        with open(env_path, encoding="utf-8") as handle:
            for line in handle:
                key, _, raw = line.strip().partition("=")
                if key == name:
                    return raw.strip()
    except OSError:
        pass
    return ""


def default_proxy_port():
    """Flask's configured port, read without importing the whole application."""
    value = _env_value("PORT")
    if value.isdigit():
        return int(value)
    return 5000


def default_listen_port():
    value = _env_value("NGINX_PORT")
    if value.isdigit():
        return int(value)
    return DEFAULT_LISTEN_PORT


def _project_dir(repo_root):
    return os.path.abspath(repo_root).replace("\\", "/").rstrip("/")


def render(
    repo_root=REPO_ROOT,
    listen_port=None,
    proxy_port=None,
):
    with open(TEMPLATE, encoding="utf-8") as handle:
        source = handle.read()
    project_dir = _project_dir(repo_root)
    listen_port = listen_port or default_listen_port()
    proxy_port = proxy_port or default_proxy_port()
    rendered = (
        source.replace("{{PROJECT_DIR}}", project_dir)
        .replace("{{MAX_REQUEST_MEGABYTES}}", str(MAX_REQUEST_MEGABYTES))
        .replace("{{LISTEN_PORT}}", str(listen_port))
        .replace("{{PROXY_PORT}}", str(proxy_port))
    )
    validate(rendered, project_dir, listen_port, proxy_port)
    return rendered


def validate(
    rendered,
    project_dir,
    listen_port=None,
    proxy_port=None,
):
    listen_port = listen_port or default_listen_port()
    proxy_port = proxy_port or default_proxy_port()
    if "{{" in rendered or "}}" in rendered:
        raise ValueError("nginx template contains an unresolved placeholder")
    required = (
        "root %s/frontend/dist;" % project_dir,
        "listen %d;" % listen_port,
        "proxy_pass http://127.0.0.1:%d;" % proxy_port,
        "alias %s/uploads/;" % project_dir,
        "alias %s/images/;" % project_dir,
        "client_max_body_size %dm;" % MAX_REQUEST_MEGABYTES,
    )
    for fragment in required:
        if fragment not in rendered:
            raise ValueError("rendered nginx config is missing: %s" % fragment)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    parser.add_argument("--repo-root", default=REPO_ROOT)
    parser.add_argument("--listen-port", type=int)
    parser.add_argument("--proxy-port", type=int)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    try:
        rendered = render(args.repo_root, args.listen_port, args.proxy_port)
        if render(args.repo_root, args.listen_port, args.proxy_port) != rendered:
            raise ValueError("nginx rendering is not deterministic")
    except (OSError, ValueError) as exc:
        print("nginx config check failed: %s" % exc, file=sys.stderr)
        return 1

    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)
    elif not args.check:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
