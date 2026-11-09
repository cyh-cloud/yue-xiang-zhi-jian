# -*- coding: utf-8 -*-
"""企业资质认证的审核侧接口（超级管理员）。

为什么归超管而不是运营：`core.permissions` 把 `review.moderate` 只给了 super_admin，
且 tests/test_permissions.py 里有一条「运营不能审核」的矩阵断言锁着。资质认证属于
审核类动作，跟内容审核同一条线，不在这里给运营开口子。

三条边界：

1. 证件照只经本文件的鉴权接口取回，接口要求 review.moderate；
2. 驳回必须写理由（审核意见为空时直接 400），否则企业收到「已驳回」却不知道改什么；
3. 裁定只改状态与审核留痕，不改企业提交的任何字段。
"""

import os

from flask import jsonify, request, send_file

from core.permissions import require_capability
from core.session import get_session_user
from db_domains import notifications
from db_domains import qualifications
from db_domains import users as users_db
from domains.admin.routes import admin_bp
from shared.credit_code import mask as mask_credit_code
from shared.enterprise_limits import (
    QUALIFICATION_LICENSE_DIR,
    QUALIFICATION_STATUS_LABELS,
)

# 驳回理由的下拉模板。企业端只看到最终文本，模板在这里统一，避免每人写一套。
REJECT_REASONS = (
    '营业执照照片不清晰，请重新拍摄或扫描后上传',
    '企业名称与营业执照不一致',
    '统一社会信用代码与营业执照不一致',
    '经营范围与本平台业务不符',
)


def _review_view(record):
    """审核队列的一行：企业提交的内容 + 申请人账号信息。

    ⚠️ 必须用 get_user_by_id（它按 username 查且 SELECT *），不能用
    get_user_by_username：后者只取 6 个字段，没有 company_name 与 phone，
    会让「账号公司名」恒为空、「名称是否一致」恒为不一致。
    """
    user = users_db.get_user_by_id(record['user_id']) or {}
    return {
        'id': record['id'],
        'user_id': record['user_id'],
        'applicant_name': user.get('name', ''),
        'applicant_phone': user.get('phone', ''),
        'account_company_name': user.get('company_name', ''),
        'company_name': record['company_name'],
        'credit_code_masked': mask_credit_code(record['credit_code']),
        'legal_person': record['legal_person'],
        'contact_phone': record['contact_phone'],
        'address': record['address'],
        'industry': record['industry'],
        'company_size': record['company_size'],
        'status': record['status'],
        'status_label': QUALIFICATION_STATUS_LABELS.get(record['status'],
                                                        record['status']),
        'review_comment': record['review_comment'],
        'reviewed_by': record['reviewed_by'],
        'submitted_at': record['submitted_at'],
        'reviewed_at': record['reviewed_at'] or '',
        'expires_at': record['expires_at'] or '',
        'has_license': bool(record['license_file']),
        'license_name': record['license_name'],
        'name_matches_account': (
            (record['company_name'] or '').strip()
            == (user.get('company_name') or '').strip()
        ),
    }


@admin_bp.route('/api/admin/qualifications', methods=['GET'])
@require_capability('review.moderate')
def admin_list_qualifications():
    status = (request.args.get('status') or 'pending').strip()
    if status not in ('pending', 'approved', 'rejected', 'all'):
        return jsonify({"success": False, "code": "bad_request",
                        "message": "status 仅支持 pending / approved / rejected / all"}), 400
    rows = qualifications.list_by_status(None if status == 'all' else status)
    return jsonify({
        "success": True,
        "status": status,
        "pending_count": qualifications.count_pending(),
        "items": [_review_view(row) for row in rows],
        "reject_reasons": list(REJECT_REASONS),
    })


@admin_bp.route('/api/admin/qualifications/<int:qualification_id>/license',
                methods=['GET'])
@require_capability('review.moderate')
def admin_get_qualification_license(qualification_id):
    record = qualifications.get_by_id(qualification_id)
    if not record or not record['license_file']:
        return jsonify({"success": False, "code": "not_found",
                        "message": "该申请没有营业执照文件"}), 404
    path = os.path.join(QUALIFICATION_LICENSE_DIR,
                        os.path.basename(record['license_file']))
    if not os.path.isfile(path):
        return jsonify({"success": False, "code": "not_found",
                        "message": "文件已不存在"}), 404
    return send_file(path, as_attachment=False,
                     download_name=record['license_name'] or 'license')


@admin_bp.route('/api/admin/qualifications/<int:qualification_id>/review',
                methods=['POST'])
@require_capability('review.moderate')
def admin_review_qualification(qualification_id):
    data = request.get_json(silent=True) or {}
    status = (data.get('status') or '').strip()
    comment = (data.get('comment') or '').strip()
    if status not in ('approved', 'rejected'):
        return jsonify({"success": False, "code": "bad_request",
                        "message": "审核结果仅支持 approved 或 rejected"}), 400
    if status == 'rejected' and not comment:
        return jsonify({"success": False, "code": "bad_request",
                        "message": "驳回必须填写审核意见"}), 400

    record = qualifications.get_by_id(qualification_id)
    if record is None:
        return jsonify({"success": False, "code": "not_found",
                        "message": "资质申请不存在"}), 404
    if record['status'] != 'pending':
        return jsonify({"success": False, "code": "conflict",
                        "message": "该申请已处理过，不能重复裁定"}), 409

    # 通过前再查一次信用代码占用：提交时查过一次，但两个账号可能并发提交，
    # 各自提交时都还没有对方的 pending 记录。
    if status == 'approved':
        owner = qualifications.find_credit_code_owner(
            record['credit_code'], record['user_id'])
        if owner:
            return jsonify({
                "success": False, "code": "credit_code_taken",
                "message": "该统一社会信用代码已由账号 %s 使用，不能重复认证" % owner
            }), 409

    reviewer = get_session_user()['username']
    qualifications.review(qualification_id, status, reviewer=reviewer,
                          comment=comment)

    if status == 'approved':
        # 认证通过后把执照上的公司名回写到账号：岗位列表展示的是 users.company_name，
        # 不同步就会出现「已认证，但岗位挂的是注册时随手填的名字」。
        # 只覆盖企业名称一个字段，其余资料仍是企业自己维护的。
        users_db.update_user_profile(record['user_id'],
                                     company_name=record['company_name'])

    # 审核结果写一条站内通知：不通知的话企业只能反复刷新页面猜结果。
    notifications.create_notification(
        record['user_id'],
        'qualification',
        '企业资质认证已通过' if status == 'approved' else '企业资质认证被驳回',
        '有效期至 %s' % (qualifications.get_by_id(qualification_id)['expires_at']
                       if status == 'approved' else (comment or '请补充材料后重新提交')),
        'qualification', qualification_id)

    return jsonify({
        "success": True,
        "message": "已通过认证" if status == 'approved' else "已驳回",
        "status": status,
    })
