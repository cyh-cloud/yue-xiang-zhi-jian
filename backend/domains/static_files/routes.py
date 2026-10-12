# -*- coding: utf-8 -*-
"""静态资源域路由：首页与静态文件兜底。

从 app.py 迁出（后端按领域拆分 T07）。URL、响应结构与状态码保持不变。

`/<path:filename>` 是全站唯一一条能匹配任意单段路径的规则，原文件要求它最后注册。
core.app_factory._register_blueprints 保留了这一约定，并在那里记录了为什么仍然
值得写死顺序（当前 Werkzeug 靠权重排序已不会误匹配，但顺序不应依赖版本行为）。

静态资源根目录 BASE_DIR 仍从 core.app_factory 取，与上传落盘目录同源于仓库根：
白名单放行的 uploads/ 与上传写入的目录必须是同一处，否则会「存得下却取不回」。
"""

import os

from flask import Blueprint, jsonify, send_from_directory

from core.app_factory import BASE_DIR

static_bp = Blueprint('static_files', __name__)


@static_bp.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')


# ⚠️ 这条路由此前是 send_from_directory(BASE_DIR, filename) ——
# 等于把**项目根下的任何文件**挂到了公网：`GET /.env` 可以直接读走 AI_API_KEY 与
# SECRET_KEY，`/database.py` 拿到全部源码，`/data/yuexiang.db` 拿到整个数据库。
# 现在收敛为「资源目录 + 静态资源后缀」双白名单，并显式拒绝隐藏文件、源码、数据与备份。
#
# 前端实际引用（已逐文件核对）：*.html、*.css、*.js、js/core.js、images/**、sw.js。
# uploads/ 下是教师上传的课程材料与 3D 模型（后缀不定），因此按**目录**整体放行。
_ALLOWED_STATIC_DIRS = frozenset((
    'js', 'css', 'images', 'img', 'assets', 'fonts', 'uploads', 'vendor',
))
_ALLOWED_STATIC_EXTS = frozenset((
    '.html', '.htm', '.css', '.js', '.mjs', '.map',
    '.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg', '.ico', '.bmp', '.avif',
    '.woff', '.woff2', '.ttf', '.otf', '.eot',
    '.mp4', '.webm', '.ogv', '.ogg', '.mp3', '.wav', '.m4a',
    '.pdf',
    '.glb', '.gltf', '.obj', '.fbx', '.stl', '.dae', '.ply', '.mtl', '.usdz',
))
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

    ext = os.path.splitext(parts[-1])[1].lower()
    if ext in _FORBIDDEN_STATIC_EXTS:
        return _static_not_found()
    # 3) 放行条件：位于资源目录内，或根目录下的白名单后缀
    in_allowed_dir = len(parts) > 1 and head in _ALLOWED_STATIC_DIRS
    if not in_allowed_dir and ext not in _ALLOWED_STATIC_EXTS:
        return _static_not_found()

    return send_from_directory(BASE_DIR, filename)
