# -*- coding: utf-8 -*-
"""应用工厂：创建 Flask 应用、装配跨域配置、注册蓝图。

为什么要有工厂：入口文件从此只负责「创建应用」与「注册蓝图」。测试客户端拿到的
应用对象仍由 `from app import app` 这条既有路径产出，拆分不改变任何启动约定。
"""

import os

from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import RequestEntityTooLarge

import repo_paths
from shared.upload_limits import MAX_REQUEST_BYTES, MAX_UPLOAD_MEGABYTES

# ---- CORS：只放行本机来源 ----
# 生产环境中前端由同源 nginx 伺服，跨域只可能出现在本地调试时（例如 Vite 端口
# 与 Flask 端口不同）。开发期由 Vite 代理 /api，也不需要为业务页面开放跨域。
# 此前是 CORS(app) —— 等于对**任意来源**开放。一旦填上 AI_API_KEY，任何站点都能借
# 用户浏览器直接调本站接口，把这里当成免费大模型代理刷额度（还可能顺带试出会话头）。
# 需要跨域部署（独立域名前端）时，用环境变量 CORS_ORIGINS 显式追加，逗号分隔。
_CORS_LOCAL_PATTERNS = [
    r'http://localhost(:\d+)?$',
    r'http://127\.0\.0\.1(:\d+)?$',
    r'http://\[::1\](:\d+)?$',
]
_CORS_EXTRA_ORIGINS = [o.strip() for o in os.getenv('CORS_ORIGINS', '').split(',') if o.strip()]

# 静态资源根目录：与上传落盘目录同源，都从仓库根推导。
# 这样模块搬进子目录后，静态白名单放行的 uploads/ 与上传写入的目录仍是同一处，
# 不会出现「存得下却取不回」。
BASE_DIR = repo_paths.REPO_ROOT


def create_app():
    """创建并配置应用，注册全部领域蓝图。返回可直接交给 WSGI / test_client 的应用。"""
    app = Flask(__name__)

    # 应用配置
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY', os.urandom(24).hex()),
        # Flask 限制的是整个 multipart 请求；文件本身的上限由领域路由校验。
        # 这里预留固定的 multipart 开销，避免恰好 50MB 的文件被边界字段顶成 413。
        MAX_CONTENT_LENGTH=MAX_REQUEST_BYTES,
        JSON_AS_ASCII=False
    )
    _register_error_handlers(app)

    # 仅对 /api/* 下发 CORS 头：静态资源一律不参与跨域（默认拒绝）。
    CORS(app, resources={r'/api/*': {
        'origins': _CORS_LOCAL_PATTERNS + _CORS_EXTRA_ORIGINS,
        'methods': ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
        'allow_headers': ['Content-Type', 'X-Session-Id'],
    }})

    _register_blueprints(app)
    return app


def _register_error_handlers(app):
    """Keep transport failures machine-readable for the SPA.

    A reverse proxy may reject an oversized body before Flask sees it; when Flask
    does see it, the frontend still needs the same code/message contract.
    """
    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_entity_too_large(_error):
        return jsonify({
            "success": False,
            "code": "file_too_large",
            "message": "文件过大，上传文件不能超过 %dMB" % MAX_UPLOAD_MEGABYTES,
        }), 413


def _register_blueprints(app):
    """注册领域路由蓝图。领域之间不互相 import，只由这里串起来。

    注册顺序保留 app.py 里的原始约定：静态资源域排最后。原文件里那条「必须放最后」
    的注释源于 Werkzeug 2.x 按注册顺序线性匹配的行为；当前 Werkzeug（3.1.9）改用
    状态机 + 权重排序，静态段优先、同权重按注册序，因此把静态蓝图调到最前也不会
    改变任何一条既有路由的匹配结果（已用全部 117 条规则正反各跑一遍比对，零差异）。

    仍然把它排在最后的理由是不把正确性寄托在版本行为上：`/<path:filename>` 是
    唯一能吃掉任意单段路径的规则，一旦将来有人引入一个与它同权重的单段动态规则
    （例如 `/<slug>`），注册顺序就成了唯一的裁判。写死顺序，比依赖 Werkzeug 的
    权重细节更稳。新增蓝图一律追加到静态蓝图之前。

    只 import 各域的包门面（`from domains import crafts_bp`），不写
    `from domains.crafts.routes import ...`：共享层不得 import 领域模块，而
    tools/check_architecture.py 正是用这条线来判定违规的（见 T01）。
    """
    from domains import (
        agriculture_bp,
        auth_bp,
        community_bp,
        crafts_bp,
        admin_bp,
        ecommerce_bp,
        employment_bp,
        employment_profile_bp,
        enterprise_bp,
        government_bp,
        live_training_bp,
        messages_bp,
        notifications_bp,
        operator_bp,
        pest_bp,
        public_bp,
        resources_bp,
        static_bp,
        teaching_support_bp,
        teacher_bp,
        user_profile_bp,
    )

    app.register_blueprint(agriculture_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(crafts_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(ecommerce_bp)
    app.register_blueprint(community_bp)
    app.register_blueprint(employment_bp)
    app.register_blueprint(employment_profile_bp)
    app.register_blueprint(enterprise_bp)
    app.register_blueprint(government_bp)
    app.register_blueprint(live_training_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(operator_bp)
    app.register_blueprint(pest_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(resources_bp)
    app.register_blueprint(teaching_support_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(user_profile_bp)
    # 静态兜底排在最后，理由见 docstring。
    app.register_blueprint(static_bp)
    return app


__all__ = ['create_app', 'BASE_DIR']
