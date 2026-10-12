# -*- coding: utf-8 -*-
"""社区域路由：讨论帖与评论的读写。

从 app.py 迁出（后端按领域拆分 T09），URL、请求响应结构、状态码、错误码保持不变。

读路径对匿名访客开放：讨论区列表与详情、评论列表都不带登录门禁。写路径
（发帖、发评论）只认会话头 X-Session-Id，取当前用户的方式与其余领域一致，
一律走共享层 core.session.get_session_user，本域不再复制一份会话实现。

软删除只影响读路径：管理员删帖/删评论是把 is_deleted 置 1，列表按 is_deleted=0
过滤，因此删后列表不再返回；详情接口不过滤该标志，删后仍可读。这两条行为都与
拆分前一致，不趁机改成 404。
"""

from flask import Blueprint, jsonify, request

from core.session import get_session_user

import database

community_bp = Blueprint('community', __name__)


@community_bp.route('/api/comments', methods=['GET'])
def public_get_comments():
    target_type = request.args.get('target_type', '')
    target_id = request.args.get('target_id', 0, type=int)
    if not target_type or not target_id:
        return jsonify({"success": False, "message": "参数不完整"}), 400
    comments = database.get_comments(target_type, target_id)
    return jsonify({"success": True, "comments": comments})


@community_bp.route('/api/comments', methods=['POST'])
def public_add_comment():
    user = get_session_user()
    if not user:
        return jsonify({"success": False, "message": "请先登录"}), 401
    data = request.get_json()
    target_type = data.get('target_type', '')
    target_id = data.get('target_id', 0)
    content = data.get('content', '').strip()
    if not target_type or not target_id or not content:
        return jsonify({"success": False, "message": "参数不完整"}), 400
    comment_id = database.add_comment(target_type, target_id, user['username'], content)
    return jsonify({"success": True, "id": comment_id, "message": "评论成功"})


@community_bp.route('/api/discussions', methods=['GET'])
def public_get_discussions():
    category = request.args.get('category', '')
    page = request.args.get('page', 1, type=int)
    discs, total = database.get_discussions(category=category or None, page=page)
    return jsonify({"success": True, "discussions": discs, "total": total})


@community_bp.route('/api/discussions', methods=['POST'])
def public_create_discussion():
    user = get_session_user()
    if not user:
        return jsonify({"success": False, "message": "请先登录"}), 401
    data = request.get_json()
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    category = data.get('category', 'general')
    if not title or not content:
        return jsonify({"success": False, "message": "标题和内容不能为空"}), 400
    disc_id = database.create_discussion(title, content, category, user['username'])
    return jsonify({"success": True, "id": disc_id, "message": "发布成功"})


@community_bp.route('/api/discussions/<int:disc_id>', methods=['GET'])
def public_get_discussion(disc_id):
    disc = database.get_discussion(disc_id)
    if not disc:
        return jsonify({"success": False, "message": "帖子不存在"}), 404
    comments = database.get_comments('discussion', disc_id)
    return jsonify({"success": True, "discussion": disc, "comments": comments})
