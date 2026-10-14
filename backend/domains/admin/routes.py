# -*- coding: utf-8 -*-
"""超级管理员域路由：用户管理、内容审核、系统公告、评论与帖子删除。

从 app.py 迁出（后端按领域拆分 T17），URL、请求响应结构、状态码、错误码保持不变。

三条边界：

1. 角色把关走能力表（core.permissions.require_capability），未登录与能力不符都回 403，
   与拆分前逐字一致。四个能力：user.manage / review.moderate /
   announcement.manage / community.manage。
2. 审核状态变更只调 database.approve_review / reject_review / revoke_review，
   由 db_domains.reviews.set_review_status 按内容类型分派回写各领域表，
   路由层不直接写任何领域表。
3. 数据访问一律走 database 契约层。
"""

from flask import Blueprint, jsonify, request

from core.permissions import require_capability
from core.session import get_session_user

import database

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/api/admin/dashboard', methods=['GET'])
@require_capability('review.moderate')
def admin_dashboard():
    """超级管理员仪表盘统计。
    user = get_session_user()

    ⚠️ 前端此前调的是 `/api/government/dashboard`（只允许 government）→ super_admin
       恒 403，统计区长期空白。这里给 admin 自己的口径。
    ⚠️ 只输出真实可算的项：在线人数 / 日活 / 增长趋势 / 平均审核时长一律不下发 ——
       没有在线状态表、没有埋点、没有访问日志，凑出来的数字就是编造。
        成功案例正文不落库，条数从 domain_data.resources.cases_data 取（与审核详情同一来源）。
    """
    user = get_session_user()
    ov = database.get_admin_overview()
    try:
        from domain_data.resources import cases_data
        ov['content']['cases'] = len(cases_data.get_cases())
    except Exception:
        # 案例模块取不到就置 None，前端该卡不渲染，绝不补 0
        ov['content']['cases'] = None
    return jsonify({"success": True, "overview": ov})


@admin_bp.route('/api/admin/users', methods=['GET'])
@require_capability('user.manage')
def admin_get_users():
    user = get_session_user()
    search = request.args.get('search', '')
    role_filter = request.args.get('role', '')
    users = database.get_all_users(search=search or None, role=role_filter or None)

    # 逐条算出「能不能删」。
    # ⚠️ 规则只放后端 —— 前端照 can_delete 渲染，不再自己判断，
    #    否则「界面藏了按钮、接口照样能删」等于没拦。
    me = user['username']
    super_admin_count = database.count_super_admins()
    for u in users:
        # password_hash 绝不下发给前端（它是 SELECT * 带出来的）
        u.pop('password_hash', None)
        rel = database.count_user_relations(u['username'])
        u['relation_count'] = rel['total']
        u['relations'] = rel['items']
        if u['username'] == me:
            u['can_delete'] = False
            u['block_reason'] = '当前登录账号，不能删除自己'
        elif u.get('role') == 'super_admin' and super_admin_count <= 1:
            u['can_delete'] = False
            u['block_reason'] = '系统必须保留至少一个超级管理员'
        elif rel['total'] > 0:
            u['can_delete'] = False
            u['block_reason'] = '有 %d 条关联业务数据，请改用「停用」' % rel['total']
        else:
            u['can_delete'] = True
            u['block_reason'] = ''
        # 自己也不能停用（停了就把自己锁在门外）
        u['can_suspend'] = (u['username'] != me)
    return jsonify({"success": True, "users": users})


@admin_bp.route('/api/admin/users/<user_id>', methods=['PUT'])
@require_capability('user.manage')
def admin_update_user(user_id):
    user = get_session_user()
    data = request.get_json(silent=True) or {}
    target = database.get_user_by_id(user_id)
    if not target:
        return jsonify({"success": False, "message": "用户不存在"}), 404

    # 末位 super_admin 不能被降级。
    # ⚠️ 这条守卫放在 PUT 而不是 DELETE 才有意义：DELETE 要求操作者本人就是
    #    super_admin，于是 count_super_admins() 恒 >= 1，「最后一个超管」只可能是
    #    操作者自己，而自删已被前面拦掉 —— DELETE 里那条守卫实际不可触发。
    #    真正能把全站最后一个超管搞没的路径是**改角色**：把 admin_demo 的 role
    #    从 super_admin 改成别的，此后没有任何账号能进管理端，且无法自恢复。
    new_role = data.get('role')
    if (new_role is not None and new_role != 'super_admin'
            and target.get('role') == 'super_admin'
            and database.count_super_admins() <= 1):
        return jsonify({
            "success": False,
            "message": "系统必须保留至少一个超级管理员，不能把最后一个超级管理员改成其他角色"}), 400

    ok = database.update_user_by_admin(user_id,
        name=data.get('name'), role=new_role, status=data.get('status'),
        phone=data.get('phone'), email=data.get('email'))
    if not ok:
        return jsonify({"success": False, "message": "用户不存在"}), 404
    return jsonify({"success": True, "message": "更新成功"})


@admin_bp.route('/api/admin/users/<user_id>/status', methods=['POST'])
@require_capability('user.manage')
def admin_set_user_status(user_id):
    """启用 / 停用账号 —— **删除的替代方案**（2026-10-08）。
    user = get_session_user()

    删用户会留下跨表孤儿（students.user_id 是名册收件人与证书归属的唯一依据），
    所以凡是有业务数据的账号一律走「停用」：登录接口本来就认 status='suspended'，
    停用后本人进不来，但所有历史数据完整保留，随时可以恢复。
    """
    user = get_session_user()
    if user_id == user['username']:
        return jsonify({"success": False, "message": "不能停用当前登录的账号"}), 400
    data = request.get_json(silent=True) or {}
    status = data.get('status', '')
    if status not in ('active', 'suspended'):
        return jsonify({"success": False, "message": "状态只能是 active 或 suspended"}), 400
    n = database.set_user_status(user_id, status)
    if n <= 0:
        return jsonify({"success": False, "message": "用户不存在"}), 404
    return jsonify({"success": True,
                    "message": "已停用，该账号无法登录" if status == 'suspended' else "已启用"})


@admin_bp.route('/api/admin/users/<user_id>', methods=['DELETE'])
@require_capability('user.manage')
def admin_delete_user(user_id):
    """删除用户。四道关依次拦：自删 / 末位超管 / 关联数据 / 不存在。
    user = get_session_user()

    ⚠️ 2026-10-08 之前本路由无条件返回 200「删除成功」——删一个不存在的人
       也照样报成功，且能把自己删掉（删完全站再无 super_admin，会话立即失效、
       不可自恢复）。现在逐条校验，并把 `delete_user_by_admin()` 的返回值
       （真实影响行数）作为最终判据。
    """
    user = get_session_user()

    if user_id == user['username']:
        return jsonify({"success": False, "message": "不能删除当前登录的账号"}), 400

    target = database.get_user_by_id(user_id)
    if not target:
        return jsonify({"success": False, "message": "用户不存在"}), 404

    if target.get('role') == 'super_admin' and database.count_super_admins() <= 1:
        return jsonify({"success": False, "message": "系统必须保留至少一个超级管理员"}), 400

    rel = database.count_user_relations(user_id)
    if rel['total'] > 0:
        return jsonify({
            "success": False,
            "message": "该账号有 %d 条关联业务数据，不能删除。请改用「停用」。" % rel['total'],
            "relations": rel['items'],
            "relation_total": rel['total'],
        }), 409

    n = database.delete_user_by_admin(user_id)
    if n <= 0:
        return jsonify({"success": False, "message": "用户不存在"}), 404
    return jsonify({"success": True, "message": "删除成功"})


# ---- 内容审核 ----

@admin_bp.route('/api/admin/reviews', methods=['GET'])
@require_capability('review.moderate')
def admin_get_reviews():
    user = get_session_user()
    content_type = request.args.get('content_type', '')
    ct = content_type or None
    # status 支持 pending / approved / rejected / all；默认仍是 pending ——
    # 仪表盘「待审核 N 项」依赖这个默认值，不能改。
    status = request.args.get('status', '') or 'pending'
    if status not in ('pending', 'approved', 'rejected', 'all'):
        status = 'pending'
    # 排序：modified（默认，按最后修改时间倒序）/ created（按提交时间倒序）。
    # 与 status 一样做白名单校验，非法值回落默认，前端乱传参打不飞排序。
    sort = request.args.get('sort', '') or 'modified'
    if sort not in ('modified', 'created'):
        sort = 'modified'
    reviews = database.get_reviews_by_status(None if status == 'all' else status, ct, sort)

    # 关联审核内容详情
    enriched = []
    for r in reviews:
        rd = dict(r)
        rd['detail'] = None
        ctype, cid = r['content_type'], r['content_id']
        if ctype == 'procurement':
            # 求购已在 2026-10-06 随「供应链求购不做」整块下线。
            # 历史遗留的待审求购不再下发给管理端 —— 否则审核列表里会出现
            # 「看不到内容、界面也没有处理入口」的孤儿卡片。
            continue
        if ctype == 'course':
            rd['detail'] = database.get_course(cid)
        elif ctype == 'job':
            rd['detail'] = database.get_job_by_id(cid)
        elif ctype == 'model_3d':
            conn = database.get_connection()
            row = conn.execute("SELECT * FROM models_3d WHERE id=?", (cid,)).fetchone()
            conn.close()
            rd['detail'] = dict(row) if row else None
        elif ctype == 'success_case':
            # 案例正文不落库（内容在 domain_data.resources.cases_data），详情直接取数据模块
            from domain_data.resources import cases_data
            rd['detail'] = cases_data.get_case(cid)
        # 「自提自审」如实标注：提交者与审核人是同一个人时，这条审核记录
        # 不含任何第三方把关，界面必须标出来，不能被当成「已审核」背书。
        # （平台预置内容的 5 条 success_case 就是这种情况，数据本身是真实的，
        #   只是提交与审核都记在 admin_demo 名下 —— 2026-10-08）
        rd['is_self_reviewed'] = bool(r.get('submitter_id') and r.get('reviewed_by')
                                      and r['submitter_id'] == r['reviewed_by'])
        enriched.append(rd)
    counts = database.count_reviews_by_status(ct)
    return jsonify({"success": True, "reviews": enriched, "counts": counts, "status": status})


@admin_bp.route('/api/admin/reviews/<int:review_id>/approve', methods=['POST'])
@require_capability('review.moderate')
def admin_approve_review(review_id):
    user = get_session_user()
    database.approve_review(review_id, user['username'])
    return jsonify({"success": True, "message": "已审核通过"})


@admin_bp.route('/api/admin/reviews/<int:review_id>/reject', methods=['POST'])
@require_capability('review.moderate')
def admin_reject_review(review_id):
    user = get_session_user()
    data = request.get_json()
    comment = data.get('comment', '')
    database.reject_review(review_id, user['username'], comment)
    return jsonify({"success": True, "message": "已驳回"})


@admin_bp.route('/api/admin/reviews/<int:review_id>/revoke', methods=['POST'])
@require_capability('review.moderate')
def admin_revoke_review(review_id):
    """撤销审核：把已通过 / 已驳回的记录退回「待审核」，可重新处理。
    user = get_session_user()

    2026-10-08 新增（管理端「内容审核」要能回看并纠正历史）。
    与 approve / reject 走同一套对称回写规则，目标表的 review_status 一并退回
    pending，不会出现「审核表已撤销、岗位却还挂着 approved」的不一致。
    """
    user = get_session_user()
    result = database.revoke_review(review_id)
    if result == 'not_found':
        return jsonify({"success": False, "message": "审核记录不存在"}), 404
    if result == 'not_reviewed':
        return jsonify({"success": False, "message": "该记录本就处于待审核状态"}), 400
    return jsonify({"success": True, "message": "已撤销，退回待审核"})


# ---- 系统公告管理 ----

@admin_bp.route('/api/admin/system-announcements', methods=['GET'])
@require_capability('announcement.manage')
def admin_get_system_announcements():
    user = get_session_user()
    anns = database.get_system_announcements(active_only=False)
    return jsonify({"success": True, "announcements": anns})


@admin_bp.route('/api/admin/system-announcements', methods=['POST'])
@require_capability('announcement.manage')
def admin_add_system_announcement():
    user = get_session_user()
    data = request.get_json()
    ann_id = database.add_system_announcement(
        data.get('title', ''), data.get('content', ''),
        data.get('is_pinned', 0), user['username'])
    return jsonify({"success": True, "id": ann_id, "message": "发布成功"})


@admin_bp.route('/api/admin/system-announcements/<int:ann_id>', methods=['DELETE'])
@require_capability('announcement.manage')
def admin_delete_system_announcement(ann_id):
    user = get_session_user()
    database.delete_system_announcement(ann_id)
    return jsonify({"success": True, "message": "已删除"})


# ---- 内容监管 ----

@admin_bp.route('/api/admin/comments/<int:comment_id>', methods=['DELETE'])
@require_capability('community.manage')
def admin_delete_comment(comment_id):
    user = get_session_user()
    database.soft_delete_comment(comment_id, user['username'])
    return jsonify({"success": True, "message": "已删除违规评论"})


@admin_bp.route('/api/admin/discussions/<int:disc_id>', methods=['DELETE'])
@require_capability('community.manage')
def admin_delete_discussion(disc_id):
    user = get_session_user()
    database.soft_delete_discussion(disc_id)
    return jsonify({"success": True, "message": "已删除违规帖子"})
