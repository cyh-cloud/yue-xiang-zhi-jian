# -*- coding: utf-8 -*-
"""Static media domain: uploads and fixed images only.

The Vue SPA is served by nginx in production and by the dedicated test proxy in
e2e. Flask is the API and upload writer, so this blueprint deliberately has no
root page and never serves the retired multi-page frontend.
"""

import os

from flask import Blueprint, jsonify, send_from_directory

from core.app_factory import BASE_DIR

static_bp = Blueprint('static_files', __name__)


# ⚠️ 这条路由此前是 send_from_directory(BASE_DIR, filename) ——
# 等于把**项目根下的任何文件**挂到了公网：`GET /.env` 可以直接读走 AI_API_KEY 与
# SECRET_KEY，`/database.py` 拿到全部源码，`/data/yuexiang.db` 拿到整个数据库。
# 现在收敛为「uploads / images 媒体目录 + 拒绝敏感后缀」，并显式拒绝隐藏文件、
# 源码、数据与备份。
#
# Only runtime media is served by Flask. Vite assets and index.html belong to
# the nginx root (or the e2e static proxy), never to the API process.
_ALLOWED_STATIC_DIRS = frozenset(('uploads', 'images'))
# 即使落在被放行的目录里，这些后缀（源码 / 配置 / 数据 / 密钥 / 备份）也一律不提供下载。
_FORBIDDEN_STATIC_EXTS = frozenset((
    '.py', '.pyc', '.pyo', '.pyd', '.pyw',
    '.env', '.ini', '.cfg', '.conf', '.toml', '.yaml', '.yml',
    '.sql', '.sh', '.bash', '.zsh', '.bat', '.cmd', '.ps1',
    '.db', '.sqlite', '.sqlite3', '.log', '.bak', '.old', '.orig', '.swp', '.tmp',
    '.pem', '.key', '.crt', '.cer', '.p12', '.pfx',
))
# 顶层的敏感目录（源码 / 数据 / 部署配置），整目录拒绝
_FORBIDDEN_STATIC_DIRS = frozenset((
    'data', 'db', 'api', 'logs', '__pycache__', 'venv', '.venv', 'node_modules',
))


def _static_not_found():
    """统一以 404 + JSON 返回，避免用不同响应暴露「这个文件到底存不存在」。"""
    return jsonify({"success": False, "code": "not_found", "message": "文件不存在"}), 404


@static_bp.route('/')
def root_not_found():
    return _static_not_found()


@static_bp.route('/<path:filename>')
def serve_static(filename):
    # 逐段归一化；send_from_directory 自身也带路径穿越防护，这里再挡一层更直观
    parts = [p for p in filename.replace('\\', '/').split('/') if p not in ('', '.')]
    if not parts or '..' in parts:
        return _static_not_found()
    # 1) 任何一段以「.」开头（.env / .env.example / .git / .workbuddy ...）一律拒绝
    for seg in parts:
        if seg.startswith('.'):
            return _static_not_found()
    # 2) 敏感目录整目录拒绝（放行目录只可能是 parts[0]）
    head = parts[0].lower()
    if head in _FORBIDDEN_STATIC_DIRS:
        return _static_not_found()

    if len(parts) < 2 or head not in _ALLOWED_STATIC_DIRS:
        return _static_not_found()

    ext = os.path.splitext(parts[-1])[1].lower()
    if ext in _FORBIDDEN_STATIC_EXTS:
        return _static_not_found()

    return send_from_directory(BASE_DIR, filename)
