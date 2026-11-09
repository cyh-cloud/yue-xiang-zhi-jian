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
from db_domains import community
from shared import sensitive_words


community_bp = Blueprint('community', __name__)

# 与前端表单校验保持同一口径。路由层负责最终边界，避免绕过浏览器直接写入超长正文。
DISCUSSION_TITLE_MAX_LEN = 80
DISCUSSION_CONTENT_MAX_LEN = 5000
COMMENT_CONTENT_MAX_LEN = 1000


def _moderation_state(hits):
    """命中敏感词 → 待审；否则直接公开。返回 (状态, 命中词串)。"""
    return ('pending' if hits else 'published'), '、'.join(hits)


@community_bp.route('/api/comments', methods=['GET'])
def public_get_comments():
    target_type = request.args.get('target_type', '')
    target_id = request.args.get('target_id', 0, type=int)
    if not target_type or not target_id:
        return jsonify({"success": False, "message": "参数不完整"}), 400
    comments = community.get_comments(target_type, target_id)
    return jsonify({"success": True, "comments": comments})


@community_bp.route('/api/comments', methods=['POST'])
def public_add_comment():
    user = get_session_user()
    if not user:
        return jsonify({"success": False, "message": "请先登录"}), 401
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    target_type = data.get('target_type', '')
    target_id = data.get('target_id', 0)
    content = str(data.get('content') or '').strip()
    if not target_type or not target_id or not content:
        return jsonify({"success": False, "message": "参数不完整"}), 400
    if len(content) > COMMENT_CONTENT_MAX_LEN:
        return jsonify({
            "success": False,
            "code": "content_too_long",
            "message": "评论过长，请控制在 %d 字以内" % COMMENT_CONTENT_MAX_LEN,
        }), 400
    # 命中敏感词只转人工审核，不直接拒绝：词表必然误伤（「无抵押贷款」是黑产，
    # 「农业贷款」是正经讨论），机器不做最终裁定。
    hits = sensitive_words.scan(content)
    status, matched = _moderation_state(hits)
    comment_id = community.add_comment(target_type, target_id, user['username'], content,
                                       moderation_status=status, matched_words=matched)
    if hits:
        return jsonify({
            "success": True, "id": comment_id, "pending": True, "matched": hits,
            "message": "评论包含需人工复核的词语（%s），已提交审核，通过后展示"
                       % sensitive_words.describe(hits),
        })
    return jsonify({"success": True, "id": comment_id, "pending": False,
                    "message": "评论成功"})

@community_bp.route('/api/discussions', methods=['GET'])
def public_get_discussions():
    category = request.args.get('category', '')
    page = request.args.get('page', 1, type=int)
    discs, total = community.get_discussions(category=category or None, page=page)
    return jsonify({"success": True, "discussions": discs, "total": total})


@community_bp.route('/api/discussions', methods=['POST'])
def public_create_discussion():
    user = get_session_user()
    if not user:
        return jsonify({"success": False, "message": "请先登录"}), 401
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    title = str(data.get('title') or '').strip()
    content = str(data.get('content') or '').strip()
    category = data.get('category', 'general')
    if not title or not content:
        return jsonify({"success": False, "message": "标题和内容不能为空"}), 400
    if len(title) > DISCUSSION_TITLE_MAX_LEN:
        return jsonify({
            "success": False,
            "code": "title_too_long",
            "message": "标题过长，请控制在 %d 字以内" % DISCUSSION_TITLE_MAX_LEN,
        }), 400
    if len(content) > DISCUSSION_CONTENT_MAX_LEN:
        return jsonify({
            "success": False,
            "code": "content_too_long",
            "message": "帖子内容过长，请控制在 %d 字以内" % DISCUSSION_CONTENT_MAX_LEN,
        }), 400
    hits = sensitive_words.scan(title, content)
    status, matched = _moderation_state(hits)
    disc_id = community.create_discussion(title, content, category, user['username'],
                                          moderation_status=status,
                                          matched_words=matched)
    if hits:
        return jsonify({
            "success": True, "id": disc_id, "pending": True, "matched": hits,
            "message": "帖子包含需人工复核的词语（%s），已提交审核，通过后自动展示"
                       % sensitive_words.describe(hits),
        })
    return jsonify({"success": True, "id": disc_id, "pending": False,
                    "message": "发布成功"})


@community_bp.route('/api/discussions/<int:disc_id>', methods=['GET'])
def public_get_discussion(disc_id):
    disc = community.get_discussion(disc_id)
    if not disc:
        return jsonify({"success": False, "message": "帖子不存在"}), 404
    comments = community.get_comments('discussion', disc_id)
    return jsonify({"success": True, "discussion": disc, "comments": comments})
